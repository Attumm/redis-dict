"""Isolated version worker executing RedisDict operations in a pinned virtual environment."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import timedelta
import importlib.metadata
import inspect
from pathlib import Path
import sys
import traceback
from typing import Any, Callable, Dict, List, Tuple

from ipc_codec import CustomerAccount, Rot13Token, assert_deep_equal_and_typed, dumps_ipc, loads_ipc
import redis_dict
from redis_dict import RedisDict


SHARED_AES_KEY = b"\x42" * 32
MISSING_SENTINEL_KEY = "__missing_cross_version_sentinel__"


def _verify_isolated_import(expected_prefix: str) -> str:
    module_file = getattr(redis_dict, "__file__", None)
    if module_file is None:
        raise RuntimeError("redis_dict.__file__ is None")
    resolved_file = Path(module_file).resolve()
    resolved_prefix = Path(expected_prefix).resolve()
    if resolved_prefix not in resolved_file.parents:
        raise RuntimeError(
            f"Import isolation violation: redis_dict imported from {resolved_file}, "
            f"outside isolated venv {resolved_prefix}"
        )
    return str(resolved_file)


def _register_custom_types(target: Any) -> None:
    target.extends_type(CustomerAccount)
    target.extends_type(Rot13Token, Rot13Token.encode_rot13, Rot13Token.decode_rot13)


def _get_dict_class(name: str) -> Any:
    if not hasattr(redis_dict, name):
        raise RuntimeError(f"{name} not available in this version")
    return getattr(redis_dict, name)


def _make_sync_dict(req: Dict[str, Any]) -> Any:
    mode = str(req.get("mode", "redis_dict"))
    conn_kwargs: Dict[str, Any] = {
        "namespace": str(req["namespace"]),
        "host": str(req["host"]),
        "port": int(req["port"]),
        "db": int(req["db"]),
    }
    if req.get("preserve_expiration"):
        conn_kwargs["preserve_expiration"] = True
    if mode == "python_redis_dict":
        inst: Any = _get_dict_class("PythonRedisDict")(**conn_kwargs)
    elif mode == "encrypted":
        inst = _get_dict_class("EncryptedRedisDict")(key=SHARED_AES_KEY, **conn_kwargs)
    else:
        inst = RedisDict(**conn_kwargs)
    if mode in ("extends_type", "stateful"):
        _register_custom_types(inst)
    if req.get("register_custom_types"):
        _register_custom_types(inst)
    return inst


def _probe_capability(fn: Callable[[], bool]) -> bool:
    try:
        return fn()
    except Exception:  # pylint: disable=broad-exception-caught
        return False


def _handle_introspect(req: Dict[str, Any], expected_prefix: str) -> Dict[str, Any]:
    file_path = _verify_isolated_import(expected_prefix)
    try:
        dist_ver = importlib.metadata.version("redis-dict")
    except importlib.metadata.PackageNotFoundError:
        dist_ver = str(getattr(redis_dict, "__version__", "unknown"))

    probe_ns = f"cv_probe_{abs(hash(expected_prefix)) % 100000}"
    probe = RedisDict(
        namespace=probe_ns,
        host=str(req["host"]),
        port=int(req["port"]),
        db=int(req["db"]),
    )
    decoding_types = sorted(probe.decoding_registry.keys())

    def _check_nested_tags() -> bool:
        probe.clear()
        probe["nested"] = [(1, 2)]
        val = probe["nested"]
        probe.clear()
        return isinstance(val, list) and len(val) == 1 and isinstance(next(iter(val)), tuple)

    def _check_typed_keys() -> bool:
        probe.clear()
        probe[42] = "forty_two"  # type: ignore[index]
        keys: List[Any] = list(probe.keys())
        val: Any = probe[42]  # type: ignore[index]
        probe.clear()
        is_exact_int = isinstance(keys[0], int) and not isinstance(keys[0], bool) if keys else False
        return len(keys) == 1 and is_exact_int and keys[0] == 42 and val == "forty_two"

    def _check_nested_extends() -> bool:
        custom_probe = RedisDict(
            namespace=f"{probe_ns}_ext",
            host=str(req["host"]),
            port=int(req["port"]),
            db=int(req["db"]),
        )
        _register_custom_types(custom_probe)
        custom_probe.clear()
        custom_probe["acct_list"] = [CustomerAccount(7, "ada")]
        val = custom_probe["acct_list"]
        custom_probe.clear()
        return isinstance(val, list) and len(val) == 1 and next(iter(val)) == CustomerAccount(7, "ada")

    classes = [
        name
        for name in ("RedisDict", "PythonRedisDict", "AsyncRedisDict", "EncryptedRedisDict")
        if hasattr(redis_dict, name)
    ]

    init_params = inspect.signature(RedisDict.__init__).parameters
    return {
        "version": dist_ver,
        "file": file_path,
        "classes": classes,
        "decoding_types": decoding_types,
        "supports_nested_tagged_containers": _probe_capability(_check_nested_tags),
        "supports_typed_keys": _probe_capability(_check_typed_keys),
        "supports_nested_extends_type": _probe_capability(_check_nested_extends),
        "supports_preserve_expiration": "preserve_expiration" in init_params,
    }


async def _async_seed(req: Dict[str, Any], items: List[Tuple[Any, Any]]) -> Dict[Any, Any]:
    async_cls = _get_dict_class("AsyncRedisDict")
    async with async_cls(
        namespace=str(req["namespace"]),
        host=str(req["host"]),
        port=int(req["port"]),
        db=int(req["db"]),
    ) as ad:
        if req.get("clear_first", True):
            await ad.clear()
        for k, v in items:
            await ad.set_item(k, v)
        return dict(await ad.to_dict())


async def _async_verify(req: Dict[str, Any], expected: Dict[Any, Any]) -> int:
    async_cls = _get_dict_class("AsyncRedisDict")
    async with async_cls(
        namespace=str(req["namespace"]),
        host=str(req["host"]),
        port=int(req["port"]),
        db=int(req["db"]),
    ) as ad:
        count = await ad.len()
        if count != len(expected):
            raise AssertionError(f"AsyncRedisDict.len() {count} != {len(expected)}")
        if await ad.contains(MISSING_SENTINEL_KEY):
            raise AssertionError("AsyncRedisDict.contains() matched missing sentinel")
        keys_seen = [k async for k in ad.keys()]
        if len(keys_seen) != len(expected):
            raise AssertionError(f"AsyncRedisDict.keys() length {len(keys_seen)} != {len(expected)}")
        for exp_k, exp_v in expected.items():
            if not await ad.contains(exp_k):
                raise AssertionError(f"AsyncRedisDict missing expected key {exp_k!r}")
            assert_deep_equal_and_typed(await ad.get_item(exp_k), exp_v, f"async[{exp_k!r}]")
        assert_deep_equal_and_typed(await ad.to_dict(), expected, "async.to_dict()")
        return int(count)


def _handle_seed_dict(req: Dict[str, Any]) -> Any:
    payload = req["data"]
    items = list(payload.items())
    if req.get("mode") == "async":
        return asyncio.run(_async_seed(req, items))

    target = _make_sync_dict(req)
    if req.get("clear_first", True):
        target.clear()
    if len(items) > 25 and req.get("mode") == "redis_dict":
        with target.pipeline():
            for key, val in items:
                target[key] = val
    else:
        for key, val in items:
            target[key] = val

    if req.get("mode") == "python_redis_dict":
        return OrderedDict((key, target[key]) for key, _ in items)
    return dict(target.items())


def _ordered_reader_is_exact(target: Any, expected: Any) -> bool:
    iter_fn = getattr(type(target), "_insertion_order_iter", None)
    if iter_fn is None or "zscan" not in inspect.getsource(iter_fn):
        return True
    ns = str(getattr(target, "namespace", ""))
    delim = str(getattr(target, "namespace_delimiter", ":"))
    prefix_len = len(f"{ns}{delim}".encode("utf-8"))
    return len(expected) <= 128 and all(prefix_len + len(str(k).encode("utf-8")) <= 64 for k in expected)


def _verify_sync_read_surface(target: Any, expected: Any, is_ordered: bool) -> None:
    if len(target) != len(expected):
        raise AssertionError(f"len(target) {len(target)} != {len(expected)}")
    if MISSING_SENTINEL_KEY in target:
        raise AssertionError("Missing sentinel unexpectedly reported in target")
    if target.get(MISSING_SENTINEL_KEY, "fallback_val") != "fallback_val":
        raise AssertionError("target.get() failed default fallback for missing key")

    for exp_k, exp_v in expected.items():
        if exp_k not in target:
            raise AssertionError(f"Expected key {exp_k!r} not found in {target.namespace!r}")
        assert_deep_equal_and_typed(target[exp_k], exp_v, f"d[{exp_k!r}]")
        assert_deep_equal_and_typed(target.get(exp_k), exp_v, f"d.get({exp_k!r})")

    if is_ordered:
        assert_deep_equal_and_typed(OrderedDict(target.items()), OrderedDict(expected.items()), "ordered.items()")
        assert_deep_equal_and_typed(list(target.keys()), list(expected.keys()), "ordered.keys()")
        assert_deep_equal_and_typed(list(target.values()), list(expected.values()), "ordered.values()")
    else:
        assert_deep_equal_and_typed(dict(target.items()), dict(expected), "d.items()")
        assert_deep_equal_and_typed(target.to_dict(), dict(expected), "d.to_dict()")


def _handle_verify_dict(req: Dict[str, Any]) -> Dict[str, Any]:
    expected = req["expected"]
    if req.get("mode") == "async":
        verified_count = asyncio.run(_async_verify(req, expected))
        return {"verified": verified_count}

    target = _make_sync_dict(req)
    is_ordered = req.get("mode") == "python_redis_dict" and _ordered_reader_is_exact(target, expected)
    _verify_sync_read_surface(target, expected, is_ordered=is_ordered)
    return {"verified": len(expected)}


def _handle_mutate_and_drain(req: Dict[str, Any]) -> Dict[str, Any]:
    target = _make_sync_dict(req)
    initial_len = len(target)
    if initial_len == 0:
        return {"drained": 0}

    first_key = next(iter(target.keys()))
    overwrite_val = req["overwrite_value"]
    target[first_key] = overwrite_val
    if len(target) != initial_len:
        raise AssertionError(f"In-place overwrite changed len from {initial_len} to {len(target)}")
    assert_deep_equal_and_typed(target[first_key], overwrite_val, f"overwrite[{first_key!r}]")

    existing_res = target.setdefault(first_key, "should_not_replace")
    assert_deep_equal_and_typed(existing_res, overwrite_val, "setdefault(existing)")

    new_key = req["new_key"]
    new_val = req["new_value"]
    inserted_res = target.setdefault(new_key, new_val)
    assert_deep_equal_and_typed(inserted_res, new_val, "setdefault(new)")
    del target[new_key]
    if new_key in target or len(target) != initial_len:
        raise AssertionError(f"Delete of {new_key!r} left residual entry or wrong length")

    popped_val = target.pop(first_key)
    assert_deep_equal_and_typed(popped_val, overwrite_val, f"pop({first_key!r})")
    if first_key in target:
        raise AssertionError(f"Popped key {first_key!r} still present")

    remaining_expected = initial_len - 1
    drained = 0
    max_iters = remaining_expected + 5
    while len(target) > 0:
        if drained >= max_iters:
            raise AssertionError(f"popitem() drain exceeded {max_iters} iterations without emptying namespace")
        target.popitem()
        drained += 1
    if drained != remaining_expected:
        raise AssertionError(f"popitem() drained {drained} items, expected {remaining_expected}")
    return {"drained": drained + 1}


def _handle_seed_features(req: Dict[str, Any]) -> Dict[str, Any]:
    target = _make_sync_dict(req)
    target.clear()
    chain_path: List[str] = list(req["chain_path"])
    chain_val = req["chain_value"]
    target.chain_set(chain_path, chain_val)

    prefix = str(req["multi_prefix"])
    multi_map: Dict[str, Any] = dict(req["multi_values"])
    for sub_k, sub_v in multi_map.items():
        target[f"{prefix}:{sub_k}"] = sub_v

    ttl_key = str(req["ttl_key"])
    ttl_val = req["ttl_value"]
    with target.expire_at(timedelta(seconds=120)):
        target[ttl_key] = ttl_val

    return {
        "chain_ground_truth": target.chain_get(chain_path),
        "multi_ground_truth": target.multi_dict(prefix),
        "ttl_ground_truth": target[ttl_key],
    }


def _handle_verify_features(req: Dict[str, Any]) -> Dict[str, Any]:
    target = _make_sync_dict(req)
    chain_path: List[str] = list(req["chain_path"])
    assert_deep_equal_and_typed(target.chain_get(chain_path), req["chain_ground_truth"], "chain_get")

    prefix = str(req["multi_prefix"])
    assert_deep_equal_and_typed(target.multi_dict(prefix), req["multi_ground_truth"], "multi_dict")
    multi_vals = target.multi_get(prefix)
    if len(multi_vals) != len(req["multi_ground_truth"]):
        raise AssertionError(f"multi_get count {len(multi_vals)} != {len(req['multi_ground_truth'])}")

    ttl_key = str(req["ttl_key"])
    assert_deep_equal_and_typed(target[ttl_key], req["ttl_ground_truth"], "ttl_value")
    ttl_before = target.get_ttl(ttl_key)
    if ttl_before is None or ttl_before <= 0:
        raise AssertionError(f"Expected positive TTL on {ttl_key!r}, got {ttl_before!r}")

    if req.get("check_preserve_expiration"):
        pres_target = _make_sync_dict({**req, "preserve_expiration": True})
        pres_target[ttl_key] = req["ttl_updated_value"]
        ttl_after = pres_target.get_ttl(ttl_key)
        if ttl_after is None or ttl_after <= 0:
            raise AssertionError(f"preserve_expiration lost TTL on {ttl_key!r}: {ttl_after!r}")
        assert_deep_equal_and_typed(pres_target[ttl_key], req["ttl_updated_value"], "ttl_updated")

    target.multi_del(prefix)
    if target.multi_dict(prefix) != {}:
        raise AssertionError(f"multi_del({prefix!r}) left residual keys")
    target.chain_del(chain_path)
    del target[ttl_key]
    return {"ttl_before": ttl_before}


def _op_set(target: Any, arg: Any) -> Tuple[bool, Any]:
    key, val = arg
    target[key] = val
    return True, None


def _op_setdefault(target: Any, arg: Any) -> Tuple[bool, Any]:
    key, val = arg
    return True, target.setdefault(key, val)


def _op_update(target: Any, arg: Any) -> Tuple[bool, Any]:
    target.update(arg)
    return True, None


def _op_pop(target: Any, arg: Any) -> Tuple[bool, Any]:
    if arg in target:
        return True, target.pop(arg)
    return False, None


def _op_delete(target: Any, arg: Any) -> Tuple[bool, Any]:
    if arg in target:
        del target[arg]
        return True, None
    return False, None


def _op_popitem(target: Any, _: Any) -> Tuple[bool, Any]:
    if len(target) == 0:
        return False, None
    return True, target.popitem()


def _op_clear(target: Any, _: Any) -> Tuple[bool, Any]:
    target.clear()
    return True, None


def _op_snapshot(_target: Any, _: Any) -> Tuple[bool, Any]:
    return True, None


_STEP_HANDLERS: Dict[str, Callable[[Any, Any], Tuple[bool, Any]]] = {
    "set": _op_set,
    "setdefault": _op_setdefault,
    "update": _op_update,
    "pop": _op_pop,
    "delete": _op_delete,
    "popitem": _op_popitem,
    "clear": _op_clear,
    "snapshot": _op_snapshot,
}


def _apply_step_op(target: Any, op: str, arg: Any) -> Tuple[bool, Any]:
    handler = _STEP_HANDLERS.get(op)
    if handler is None:
        raise ValueError(f"Unknown stateful op: {op!r}")
    return handler(target, arg)


def _handle_exec_step(req: Dict[str, Any]) -> Dict[str, Any]:
    is_ordered = bool(req.get("ordered", False))
    mode = "python_redis_dict" if is_ordered else "redis_dict"
    target = _make_sync_dict({**req, "mode": mode, "register_custom_types": True})
    found, res = _apply_step_op(target, str(req["op"]), req.get("arg"))
    snap: Any = OrderedDict(target.items()) if is_ordered else dict(target.items())
    return {"found": found, "result": res, "snapshot": snap}


_ACTION_HANDLERS: Dict[str, Callable[[Dict[str, Any]], Any]] = {
    "seed_dict": _handle_seed_dict,
    "verify_dict": _handle_verify_dict,
    "mutate_and_drain": _handle_mutate_and_drain,
    "seed_features": _handle_seed_features,
    "verify_features": _handle_verify_features,
    "exec_step": _handle_exec_step,
}


def _dispatch(req: Dict[str, Any], expected_prefix: str) -> Any:
    action = str(req["action"])
    if action == "introspect":
        return _handle_introspect(req, expected_prefix)
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"Unsupported worker action: {action!r}")
    return handler(req)


def main() -> int:
    """Run persistent line-framed IPC worker loop until stdin closes.

    Returns:
        int: Process exit status code.
    """
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: worker.py <expected_venv_prefix>\n")
        return 2
    expected_prefix = sys.argv[1]
    _verify_isolated_import(expected_prefix)

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            req = loads_ipc(line)
            if req.get("action") == "ping":
                resp: Dict[str, Any] = {"ok": True, "result": "pong"}
            else:
                resp = {"ok": True, "result": _dispatch(req, expected_prefix)}
        except Exception as exc:  # pylint: disable=broad-exception-caught
            resp = {
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        sys.stdout.write(dumps_ipc(resp) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
