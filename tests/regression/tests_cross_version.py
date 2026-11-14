"""Dynamic, property-based cross-version Redis database regression suite."""
from __future__ import annotations

from collections import OrderedDict
import os
from pathlib import Path
import re
import selectors
import subprocess  # nosec B404
import tempfile
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Sequence, Tuple, Type, cast
import unittest

from hypothesis import HealthCheck, given, settings, strategies as st
from redis import StrictRedis

from ipc_codec import CustomerAccount, Rot13Token, assert_deep_equal_and_typed, dumps_ipc, loads_ipc
from strategies import (
    assert_strategy_registry_complete,
    custom_extends_strategy,
    nested_value_strategy,
    per_type_dict_strategy,
    stateful_steps_strategy,
    string_key_strategy,
    typed_keys_dict_strategy,
)
from version_env import IsolatedEnvPool, ResolvedVersion, discover_default_pairs, resolve_version_spec


WORKER_PATH = Path(__file__).resolve().parent / "worker.py"
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_CROSS_VERSION_DB", "13"))
MAX_EXAMPLES = int(os.environ.get("CROSS_VERSION_EXAMPLES", "15"))
FORWARD_ONLY = os.environ.get("CROSS_VERSION_FORWARD_ONLY", "0") == "1"
USE_UV = os.environ.get("USE_UV", "true").lower() not in ("false", "0", "no", "n", "f")


_NO_LIFO = object()


class WorkerRPCError(AssertionError):
    """Raised when an isolated version worker reports an error or times out."""


def _scrubbed_worker_env() -> Dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONUNBUFFERED"] = "1"
    return env


class WorkerClient:
    """Persistent line-framed IPC client speaking to an isolated venv worker subprocess."""

    def __init__(self, label: str, venv_python: Path, timeout: float = 20.0) -> None:
        """Start an isolated worker process for ``venv_python``.

        Args:
            label (str): Human-readable version label for error messages.
            venv_python (Path): Path to the isolated venv ``python`` binary.
            timeout (float): Per-call read timeout in seconds.
        """
        self.label = label
        self.venv_python = venv_python
        self.venv_root = venv_python.parents[1].resolve()
        self.timeout = timeout
        self._proc = subprocess.Popen(  # nosec B603  # pylint: disable=consider-using-with
            [str(venv_python), "-u", str(WORKER_PATH), str(self.venv_root)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=_scrubbed_worker_env(),
        )

    def call(self, action: str, **kwargs: Any) -> Any:
        """Execute an IPC action in the worker and return its decoded result.

        Args:
            action (str): Worker action name.
            **kwargs (Any): Action parameters serialized via ``ipc_codec``.

        Raises:
            WorkerRPCError: If the worker times out, exits unexpectedly, or raises an exception.

        Returns:
            Any: Decoded ``result`` object returned by the worker.
        """
        if self._proc.stdin is None or self._proc.stdout is None:
            raise WorkerRPCError(f"[{self.label}] worker stdio pipes are closed")
        payload = {"action": action, "host": REDIS_HOST, "port": REDIS_PORT, "db": REDIS_DB, **kwargs}
        self._proc.stdin.write(dumps_ipc(payload) + "\n")
        self._proc.stdin.flush()

        line = self._read_line_with_timeout()
        resp = loads_ipc(line)
        if not resp.get("ok"):
            raise WorkerRPCError(
                f"[{self.label}] {action} failed ({resp.get('error_type')}): {resp.get('error')}\n"
                f"{resp.get('traceback', '')}"
            )
        return resp["result"]

    def _read_line_with_timeout(self) -> str:
        assert self._proc.stdout is not None  # nosec B101
        sel = selectors.DefaultSelector()
        try:
            sel.register(self._proc.stdout, selectors.EVENT_READ)
            events = sel.select(timeout=self.timeout)
        finally:
            sel.close()
        if not events:
            self.close()
            raise WorkerRPCError(f"[{self.label}] worker timed out after {self.timeout}s")
        line = self._proc.stdout.readline()
        if not line:
            stderr_out = self._proc.stderr.read() if self._proc.stderr is not None else ""
            raise WorkerRPCError(f"[{self.label}] worker exited unexpectedly:\n{stderr_out}")
        return line

    def close(self) -> None:
        """Terminate and clean up the worker subprocess and its stdio pipes."""
        if self._proc.stdin is not None and not self._proc.stdin.closed:
            self._proc.stdin.close()
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)
        if self._proc.stdout is not None and not self._proc.stdout.closed:
            self._proc.stdout.close()
        if self._proc.stderr is not None and not self._proc.stderr.closed:
            self._proc.stderr.close()


class _SessionResources:
    """Shared lazy session pool so isolated venvs are built at most once per version per test run."""

    def __init__(self) -> None:
        self._tmp: Optional[tempfile.TemporaryDirectory[str]] = None
        self._pool: Optional[IsolatedEnvPool] = None

    def get_pool(self) -> IsolatedEnvPool:
        """Return or initialize the session ``IsolatedEnvPool``.

        Returns:
            IsolatedEnvPool: Shared environment pool.
        """
        if self._pool is None:
            self._tmp = tempfile.TemporaryDirectory(  # pylint: disable=consider-using-with
                prefix="redis_dict_xver_",
            )
            self._pool = IsolatedEnvPool(Path(self._tmp.name), use_uv=USE_UV)
        return self._pool

    def cleanup(self) -> None:
        """Remove temporary isolated virtual environments at process exit."""
        if self._tmp is not None:
            self._tmp.cleanup()
            self._tmp = None
            self._pool = None


_SESSION = _SessionResources()


def tearDownModule() -> None:  # pylint: disable=invalid-name
    """Clean up temporary cross-version virtual environments after module finishes."""
    _SESSION.cleanup()


def _configured_pairs() -> List[Tuple[ResolvedVersion, ResolvedVersion]]:
    raw_pairs = os.environ.get("CROSS_VERSION_PAIRS", "").strip()
    if raw_pairs:
        parsed: List[Tuple[ResolvedVersion, ResolvedVersion]] = []
        for token in raw_pairs.split(",,"):
            part = token.strip()
            if not part:
                continue
            prev_spec, next_spec = part.split("::", 1)
            parsed.append((resolve_version_spec(prev_spec), resolve_version_spec(next_spec)))
        return parsed

    prev_env = os.environ.get("PREV_REF", "").strip()
    next_env = os.environ.get("NEXT_REF", "").strip()
    if prev_env or next_env:
        return [
            (
                resolve_version_spec(prev_env or "origin/main"),
                resolve_version_spec(next_env or "WORKTREE"),
            )
        ]
    return discover_default_pairs()


def _sanitize_identifier(raw: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "_", raw).strip("_")


def _ref_set(ref_map: Dict[Any, Any], arg: Any) -> Tuple[bool, Any]:
    ref_map[arg[0]] = arg[1]
    return True, None


def _ref_setdefault(ref_map: Dict[Any, Any], arg: Any) -> Tuple[bool, Any]:
    return True, ref_map.setdefault(arg[0], arg[1])


def _ref_update(ref_map: Dict[Any, Any], arg: Any) -> Tuple[bool, Any]:
    ref_map.update(arg)
    return True, None


def _ref_pop(ref_map: Dict[Any, Any], key: Any) -> Tuple[bool, Any]:
    if key in ref_map:
        return True, ref_map.pop(key)
    return False, None


def _ref_delete(ref_map: Dict[Any, Any], key: Any) -> Tuple[bool, Any]:
    if key in ref_map:
        del ref_map[key]
        return True, None
    return False, None


def _ref_popitem(ref_map: Dict[Any, Any], _arg: Any) -> Tuple[bool, Any]:
    if not ref_map:
        return False, None
    return True, ("any", None)


_REF_HANDLERS = {
    "set": _ref_set,
    "setdefault": _ref_setdefault,
    "update": _ref_update,
    "pop": _ref_pop,
    "delete": _ref_delete,
    "popitem": _ref_popitem,
}


def _apply_ref_step(ref_map: Dict[Any, Any], op: str, arg: Any) -> Tuple[bool, Any]:
    handler = _REF_HANDLERS.get(op)
    if handler is None:
        raise ValueError(f"Unexpected reference op: {op!r}")
    return handler(ref_map, arg)


if TYPE_CHECKING:
    _PairTemplateBase = unittest.TestCase
else:
    _PairTemplateBase = object


class _CrossVersionPairMixin(_PairTemplateBase):
    """Parameterized cross-version test template instantiated once per ``(prev, next)`` pair."""

    prev_resolved: ClassVar[ResolvedVersion]
    next_resolved: ClassVar[ResolvedVersion]
    redis_client: ClassVar[StrictRedis[Any]]
    prev_worker: ClassVar[WorkerClient]
    next_worker: ClassVar[WorkerClient]
    prev_info: ClassVar[Dict[str, Any]]
    next_info: ClassVar[Dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        """Provision isolated virtual environments and persistent workers for both versions.

        Raises:
            Exception: Re-raises any worker introspection failure after closing worker pipes.
        """
        cls.redis_client = StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        cls.redis_client.ping()
        cls.redis_client.flushdb()

        pool = _SESSION.get_pool()
        prev_py = pool.get_python(cls.prev_resolved)
        next_py = pool.get_python(cls.next_resolved)
        cls.prev_worker = WorkerClient(cls.prev_resolved.label, prev_py)
        cls.next_worker = WorkerClient(cls.next_resolved.label, next_py)
        try:
            cls.prev_info = cls.prev_worker.call("introspect")
            cls.next_info = cls.next_worker.call("introspect")
        except Exception:
            cls.prev_worker.close()
            cls.next_worker.close()
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        """Shut down persistent workers and flush the dedicated cross-version Redis DB."""
        if hasattr(cls, "prev_worker"):
            cls.prev_worker.close()
        if hasattr(cls, "next_worker"):
            cls.next_worker.close()
        if hasattr(cls, "redis_client"):
            cls.redis_client.flushdb()

    def setUp(self) -> None:
        """Ensure a clean Redis database before each test method."""
        self.redis_client.flushdb()

    def tearDown(self) -> None:
        """Leave the Redis database clean after each test method."""
        self.redis_client.flushdb()

    def test_01_isolated_venvs_and_registry_completeness(self) -> None:
        """Verify isolated venv imports and complete Hypothesis coverage of decoding_registry."""
        assert_strategy_registry_complete(self.prev_info["decoding_types"])
        assert_strategy_registry_complete(self.next_info["decoding_types"])
        if self.prev_resolved.cache_key != self.next_resolved.cache_key:
            self.assertNotEqual(
                self.prev_info["file"],
                self.next_info["file"],
                "prev and next workers unexpectedly imported the same redis_dict module file",
            )

    def test_02_forward_upgrade_hypothesis_all_registry_types(self) -> None:
        """Seed variable multi-type & nested-container payloads in prev and verify/mutate in next."""
        prev_types: Sequence[str] = self.prev_info["decoding_types"]
        nested_ok = bool(self.prev_info["supports_nested_tagged_containers"])
        val_strat = nested_value_strategy(prev_types, allow_tagged_containers=nested_ok)

        @settings(
            max_examples=MAX_EXAMPLES,
            deadline=None,
            suppress_health_check=[HealthCheck.too_slow],
        )
        @given(
            payload=per_type_dict_strategy(prev_types, allow_tagged_containers=nested_ok),
            overwrite_val=val_strat,
            new_val=val_strat,
        )
        def _check(payload: Dict[str, Any], overwrite_val: Any, new_val: Any) -> None:
            self.redis_client.flushdb()
            ns = "cv_fwd"
            ground_truth = self.prev_worker.call("seed_dict", namespace=ns, mode="redis_dict", data=payload)
            self.next_worker.call("verify_dict", namespace=ns, mode="redis_dict", expected=ground_truth)
            self.next_worker.call(
                "mutate_and_drain",
                namespace=ns,
                mode="redis_dict",
                overwrite_value=overwrite_val,
                new_key="__cv_new_key__",
                new_value=new_val,
            )
            self.assertEqual(self.redis_client.dbsize(), 0)

        _check()  # pylint: disable=no-value-for-parameter

    def test_03_python_redis_dict_ordered_and_custom_extends_type(self) -> None:
        """Verify PythonRedisDict ZSET insertion order and custom extends_type across upgrade."""
        prev_types: Sequence[str] = self.prev_info["decoding_types"]
        nested_ok = bool(self.prev_info["supports_nested_tagged_containers"])
        nested_ext_ok = bool(
            self.prev_info["supports_nested_extends_type"]
            and self.next_info["supports_nested_extends_type"]
        )
        item_strat = st.lists(
            st.tuples(
                string_key_strategy(),
                nested_value_strategy(prev_types, allow_tagged_containers=nested_ok),
            ),
            min_size=2,
            max_size=12,
            unique_by=lambda kv: kv[0],
        ).map(OrderedDict)

        @settings(
            max_examples=MAX_EXAMPLES,
            deadline=None,
            suppress_health_check=[HealthCheck.too_slow],
        )
        @given(ordered_payload=item_strat, ext_payload=custom_extends_strategy())
        def _check(ordered_payload: OrderedDict[str, Any], ext_payload: Dict[str, Any]) -> None:
            self.redis_client.flushdb()
            if "PythonRedisDict" in self.prev_info["classes"] and "PythonRedisDict" in self.next_info["classes"]:
                ord_gt = self.prev_worker.call(
                    "seed_dict",
                    namespace="cv_ord",
                    mode="python_redis_dict",
                    data=ordered_payload,
                )
                self.next_worker.call(
                    "verify_dict",
                    namespace="cv_ord",
                    mode="python_redis_dict",
                    expected=ord_gt,
                )
                self.next_worker.call(
                    "mutate_and_drain",
                    namespace="cv_ord",
                    mode="python_redis_dict",
                    overwrite_value="updated_head",
                    new_key="__ord_temp__",
                    new_value=123,
                )

            if nested_ext_ok:
                ext_payload = {
                    **ext_payload,
                    "nested_custom": [CustomerAccount(99, "nested"), Rot13Token("inner:token")],
                }
            ext_gt = self.prev_worker.call("seed_dict", namespace="cv_ext", mode="extends_type", data=ext_payload)
            self.next_worker.call("verify_dict", namespace="cv_ext", mode="extends_type", expected=ext_gt)
            self.next_worker.call(
                "mutate_and_drain",
                namespace="cv_ext",
                mode="extends_type",
                overwrite_value=CustomerAccount(404, "mutated"),
                new_key="__ext_temp__",
                new_value=Rot13Token("ephemeral"),
            )
            self.assertEqual(self.redis_client.dbsize(), 0)

        _check()  # pylint: disable=no-value-for-parameter

    def test_04_large_scan_batches_chains_multi_and_ttl(self) -> None:
        """Verify multi-batch SCAN (>200 keys), chain_set/get, multi_dict/del, and TTL preservation."""
        prev_types: Sequence[str] = self.prev_info["decoding_types"]
        nested_ok = bool(self.prev_info["supports_nested_tagged_containers"])
        val_strat = nested_value_strategy(prev_types, allow_tagged_containers=nested_ok)

        @settings(max_examples=3, deadline=None, suppress_health_check=[HealthCheck.too_slow])
        @given(
            sample_vals=st.lists(val_strat, min_size=12, max_size=20),
            chain_val=val_strat,
            ttl_val=val_strat,
            ttl_updated=val_strat,
        )
        def _check(sample_vals: List[Any], chain_val: Any, ttl_val: Any, ttl_updated: Any) -> None:
            self.redis_client.flushdb()
            bulk = {f"batch:{idx:04d}": sample_vals[idx % len(sample_vals)] for idx in range(260)}
            bulk_gt = self.prev_worker.call("seed_dict", namespace="cv_bulk", mode="redis_dict", data=bulk)
            self.next_worker.call("verify_dict", namespace="cv_bulk", mode="redis_dict", expected=bulk_gt)

            feat_gt = self.prev_worker.call(
                "seed_features",
                namespace="cv_feat",
                mode="redis_dict",
                chain_path=["region", "eu", "cluster"],
                chain_value=chain_val,
                multi_prefix="acct",
                multi_values={"one": sample_vals[0], "two": sample_vals[1], "three": sample_vals[2]},
                ttl_key="session:token",
                ttl_value=ttl_val,
            )
            self.next_worker.call(
                "verify_features",
                namespace="cv_feat",
                mode="redis_dict",
                chain_path=["region", "eu", "cluster"],
                multi_prefix="acct",
                ttl_key="session:token",
                ttl_updated_value=ttl_updated,
                check_preserve_expiration=bool(self.next_info["supports_preserve_expiration"]),
                **feat_gt,
            )

        _check()  # pylint: disable=no-value-for-parameter

    def test_05_async_encrypted_and_typed_keys_capabilities(self) -> None:
        """Verify AsyncRedisDict, EncryptedRedisDict, and typed-keys wire compatibility."""
        prev_types: Sequence[str] = self.prev_info["decoding_types"]
        nested_ok = bool(self.prev_info["supports_nested_tagged_containers"])
        dict_strat = st.dictionaries(
            string_key_strategy(),
            nested_value_strategy(prev_types, allow_tagged_containers=nested_ok),
            min_size=2,
            max_size=8,
        )

        @settings(
            max_examples=MAX_EXAMPLES,
            deadline=None,
            suppress_health_check=[HealthCheck.too_slow],
        )
        @given(str_payload=dict_strat, typed_payload=typed_keys_dict_strategy())
        def _check(str_payload: Dict[str, Any], typed_payload: Dict[Any, Any]) -> None:
            self._verify_async_upgrade(str_payload)
            self._verify_encrypted_upgrade(str_payload)
            self._verify_typed_keys_upgrade(typed_payload)

        _check()  # pylint: disable=no-value-for-parameter

    def _verify_async_upgrade(self, payload: Dict[str, Any]) -> None:
        if "AsyncRedisDict" not in self.next_info["classes"]:
            return
        self.redis_client.flushdb()
        seed_mode = "async" if "AsyncRedisDict" in self.prev_info["classes"] else "redis_dict"
        gt = self.prev_worker.call("seed_dict", namespace="cv_async", mode=seed_mode, data=payload)
        self.next_worker.call("verify_dict", namespace="cv_async", mode="async", expected=gt)

    def _verify_encrypted_upgrade(self, payload: Dict[str, Any]) -> None:
        if "EncryptedRedisDict" not in self.prev_info["classes"]:
            return
        if "EncryptedRedisDict" not in self.next_info["classes"]:
            return
        self.redis_client.flushdb()
        gt = self.prev_worker.call("seed_dict", namespace="cv_enc", mode="encrypted", data=payload)
        for raw_k in self.redis_client.scan_iter(match="cv_enc:*"):
            raw_v = self.redis_client.get(raw_k) or ""
            self.assertNotIn("str:", raw_v)
            self.assertNotIn("dict:", raw_v)
        self.next_worker.call("verify_dict", namespace="cv_enc", mode="encrypted", expected=gt)

    def _verify_typed_keys_upgrade(self, typed_payload: Dict[Any, Any]) -> None:
        if not self.next_info["supports_typed_keys"]:
            return
        if not self.prev_info["supports_typed_keys"]:
            return
        self.redis_client.flushdb()
        gt = self.prev_worker.call(
            "seed_dict",
            namespace="cv_tkeys",
            mode="extends_type",
            data=typed_payload,
        )
        self.next_worker.call("verify_dict", namespace="cv_tkeys", mode="extends_type", expected=gt)
        self.next_worker.call(
            "mutate_and_drain",
            namespace="cv_tkeys",
            mode="extends_type",
            overwrite_value="overwritten",
            new_key=(999, "tuple_key"),
            new_value="temp_tuple_val",
        )
        self.assertEqual(self.redis_client.dbsize(), 0)

    def test_06_rolling_backward_wire_parity_and_stateful_interleaving(self) -> None:
        """Verify rolling backward reads (next -> prev), raw Redis parity, and stateful interleaving."""
        if FORWARD_ONLY:
            self.skipTest("CROSS_VERSION_FORWARD_ONLY=1 set; skipping rolling backward checks")
        if (
            self.next_info["supports_nested_tagged_containers"]
            and not self.prev_info["supports_nested_tagged_containers"]
        ):
            self.skipTest("Target version extends nested JSON tagging beyond historical baseline; forward-only pair")

        shared_types = sorted(set(self.prev_info["decoding_types"]) & set(self.next_info["decoding_types"]))
        shared_nested = bool(
            self.prev_info["supports_nested_tagged_containers"]
            and self.next_info["supports_nested_tagged_containers"]
        )
        self._assert_raw_wire_parity()

        @settings(
            max_examples=MAX_EXAMPLES,
            deadline=None,
            suppress_health_check=[HealthCheck.too_slow],
        )
        @given(
            rolling_payload=per_type_dict_strategy(shared_types, allow_tagged_containers=shared_nested),
            steps=stateful_steps_strategy(shared_types, allow_tagged_containers=shared_nested),
        )
        def _check(rolling_payload: Dict[str, Any], steps: List[Tuple[str, str, Any]]) -> None:
            self.redis_client.flushdb()
            next_gt = self.next_worker.call(
                "seed_dict",
                namespace="cv_roll",
                mode="redis_dict",
                data=rolling_payload,
            )
            self.prev_worker.call("verify_dict", namespace="cv_roll", mode="redis_dict", expected=next_gt)
            self.prev_worker.call(
                "mutate_and_drain",
                namespace="cv_roll",
                mode="redis_dict",
                overwrite_value="rolled_back_val",
                new_key="__roll_new__",
                new_value=42,
            )
            self._run_interleaved_steps(steps, ordered=False)
            if "PythonRedisDict" in self.prev_info["classes"] and "PythonRedisDict" in self.next_info["classes"]:
                self._run_interleaved_steps(steps, ordered=True)

        _check()  # pylint: disable=no-value-for-parameter

    def _assert_raw_wire_parity(self) -> None:
        self.redis_client.flushdb()
        deterministic_sample: Dict[str, Any] = {
            "plain_str": "hello:world",
            "lookalike": "int:42",
            "integer": -987654321,
            "flag": True,
            "nothing": None,
            "ordered": OrderedDict([("z", 1), ("a", 2), ("m", [True, "ok"])]),
        }
        self.prev_worker.call("seed_dict", namespace="wire_prev", mode="redis_dict", data=deterministic_sample)
        self.next_worker.call("seed_dict", namespace="wire_next", mode="redis_dict", data=deterministic_sample)
        for key in deterministic_sample:
            prev_raw_key = f"wire_prev:{key}"
            next_raw_key = f"wire_next:{key}"
            raw_redis = cast(Any, self.redis_client)
            self.assertEqual(raw_redis.type(prev_raw_key), raw_redis.type(next_raw_key))
            self.assertEqual(
                self.redis_client.get(prev_raw_key),
                self.redis_client.get(next_raw_key),
                f"Raw Redis wire mismatch for key {key!r}",
            )

    def _verify_step_result(
        self,
        op: str,
        out: Dict[str, Any],
        ref_ctx: Tuple[Any, Dict[Any, Any], Any],
    ) -> None:
        exp_res, ref_map, expected_lifo_key = ref_ctx
        if not out["found"]:
            return
        if op in ("setdefault", "pop"):
            assert_deep_equal_and_typed(out["result"], exp_res, f"step({op}).result")
        elif op == "popitem":
            popped_k, popped_v = out["result"]
            if expected_lifo_key is not _NO_LIFO:
                self.assertEqual(popped_k, expected_lifo_key)
            assert_deep_equal_and_typed(popped_v, ref_map.pop(popped_k), "step(popitem).val")

    def _run_interleaved_steps(self, steps: List[Tuple[str, str, Any]], ordered: bool) -> None:
        self.redis_client.flushdb()
        ns = "cv_state_ord" if ordered else "cv_state_std"
        ref_map: Dict[Any, Any] = {}
        last_ordered_keys: List[Any] = []
        for worker_name, op, arg in steps:
            actor = self.prev_worker if worker_name == "prev" else self.next_worker
            peer = self.next_worker if worker_name == "prev" else self.prev_worker
            out = actor.call("exec_step", namespace=ns, ordered=ordered, op=op, arg=arg)
            exp_found, exp_res = _apply_ref_step(ref_map, op, arg)
            self.assertEqual(out["found"], exp_found)
            self._verify_step_result(
                op,
                out,
                (exp_res, ref_map, last_ordered_keys[-1] if (ordered and last_ordered_keys) else _NO_LIFO),
            )
            assert_deep_equal_and_typed(dict(out["snapshot"]), ref_map, f"step({op}).ref_dict")
            peer_out = peer.call("exec_step", namespace=ns, ordered=ordered, op="snapshot", arg=None)
            assert_deep_equal_and_typed(peer_out["snapshot"], out["snapshot"], f"step({op}).peer_parity")
            if ordered:
                last_ordered_keys = list(out["snapshot"].keys())

        self.next_worker.call("exec_step", namespace=ns, ordered=ordered, op="clear", arg=None)
        self.assertEqual(self.redis_client.dbsize(), 0)


class TestCrossVersionFaultInjection(unittest.TestCase):
    """Negative fault-injection tests proving incompatible wire changes fail fast and deterministically."""

    redis_client: ClassVar[StrictRedis[Any]]
    worker: ClassVar[WorkerClient]

    @classmethod
    def setUpClass(cls) -> None:
        """Provision a worker on ``WORKTREE`` for deterministic wire-fault injection checks."""
        cls.redis_client = StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        cls.redis_client.ping()
        cls.redis_client.flushdb()
        worktree_ver = resolve_version_spec("WORKTREE")
        venv_py = _SESSION.get_pool().get_python(worktree_ver)
        cls.worker = WorkerClient("fault-worktree", venv_py, timeout=8.0)

    @classmethod
    def tearDownClass(cls) -> None:
        """Close the fault-injection worker and clean up Redis."""
        if hasattr(cls, "worker"):
            cls.worker.close()
        if hasattr(cls, "redis_client"):
            cls.redis_client.flushdb()

    def setUp(self) -> None:
        """Flush dedicated Redis DB before each fault-injection test."""
        self.redis_client.flushdb()

    def tearDown(self) -> None:
        """Flush dedicated Redis DB after each fault-injection test."""
        self.redis_client.flushdb()

    def test_unmapped_decoding_registry_type_fails_completeness_guard(self) -> None:
        """Verify adding a new decoding_registry type without a Hypothesis strategy fails loudly."""
        with self.assertRaisesRegex(AssertionError, "HypotheticalNewType"):
            assert_strategy_registry_complete(["str", "int", "HypotheticalNewType"])

    def test_fault_altered_key_wire_prefix_fails_fast(self) -> None:
        """Simulate changing ``ns:key`` to ``ns:str:key`` and assert verification fails immediately."""
        gt = self.worker.call(
            "seed_dict",
            namespace="fi_key",
            mode="redis_dict",
            data={"alpha": 100, "user:42": "active"},
        )
        cast(Any, self.redis_client).rename("fi_key:alpha", "fi_key:str:alpha")
        with self.assertRaisesRegex(WorkerRPCError, "alpha|typed keys mismatch"):
            self.worker.call("verify_dict", namespace="fi_key", mode="redis_dict", expected=gt)

    def test_fault_nested_type_degradation_and_ordered_dict_tag_corruption_fail_fast(self) -> None:
        """Simulate ``bool -> int`` / ``tuple -> list`` and ``OrderedDict`` ``__type__`` corruption."""
        gt = self.worker.call(
            "seed_dict",
            namespace="fi_val",
            mode="redis_dict",
            data={"nested": [(1, True)], "ord": OrderedDict([("first", 1), ("second", 2)])},
        )
        self.redis_client.set("fi_val:nested", "list:[[1, 1]]")
        with self.assertRaisesRegex(WorkerRPCError, "exact type mismatch"):
            self.worker.call("verify_dict", namespace="fi_val", mode="redis_dict", expected=gt)

        self.redis_client.set("fi_val:nested", 'list:[{"__type__": "tuple", "value": [1, true]}]')
        self.redis_client.set(
            "fi_val:ord",
            'OrderedDict:[{"__type__": "tuple", "value": ["first", 1]}]',
        )
        with self.assertRaises(WorkerRPCError):
            self.worker.call("verify_dict", namespace="fi_val", mode="redis_dict", expected=gt)

    def test_fault_corrupted_python_redis_dict_zset_order_fails_fast(self) -> None:
        """Simulate ZSET insertion-order score reversal in ``PythonRedisDict``."""
        if "PythonRedisDict" not in self.worker.call("introspect")["classes"]:
            self.skipTest("PythonRedisDict unavailable")
        gt = self.worker.call(
            "seed_dict",
            namespace="fi_zset",
            mode="python_redis_dict",
            data=OrderedDict([("first", "a"), ("second", "b")]),
        )
        self.redis_client.zadd("redis-dict-insertion-order-fi_zset", {"first": 99, "second": 1})
        with self.assertRaisesRegex(WorkerRPCError, "order"):
            self.worker.call("verify_dict", namespace="fi_zset", mode="python_redis_dict", expected=gt)

    def test_fault_orphaned_or_unpoppable_key_fails_bounded_drain(self) -> None:
        """Simulate a corrupted ZSET orphan entry so ``mutate_and_drain`` fails fast without hanging."""
        if "PythonRedisDict" not in self.worker.call("introspect")["classes"]:
            self.skipTest("PythonRedisDict unavailable")
        self.worker.call(
            "seed_dict",
            namespace="fi_drain",
            mode="python_redis_dict",
            data=OrderedDict([("k1", "v1"), ("k2", "v2")]),
        )
        self.redis_client.delete("fi_drain:k2")
        with self.assertRaises(WorkerRPCError):
            self.worker.call(
                "mutate_and_drain",
                namespace="fi_drain",
                mode="python_redis_dict",
                overwrite_value="v1_new",
                new_key="k3",
                new_value="v3",
            )


def _register_dynamic_pair_test_classes() -> None:
    pairs = _configured_pairs()
    for idx, (prev_ver, next_ver) in enumerate(pairs, start=1):
        cls_name = (
            f"TestCrossVersion_{idx:02d}_"
            f"{_sanitize_identifier(prev_ver.label)}_to_{_sanitize_identifier(next_ver.label)}"
        )
        dyn_cls: Type[unittest.TestCase] = type(
            cls_name,
            (_CrossVersionPairMixin, unittest.TestCase),
            {
                "__doc__": f"Cross-version database regression suite: {prev_ver.label} -> {next_ver.label}.",
                "prev_resolved": prev_ver,
                "next_resolved": next_ver,
            },
        )
        globals()[cls_name] = dyn_cls


_register_dynamic_pair_test_classes()


if __name__ == "__main__":
    unittest.main()
