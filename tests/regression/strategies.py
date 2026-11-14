"""Dynamic Hypothesis strategies mapped to every type in RedisDict.decoding_registry."""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Sequence, Set, Tuple

from hypothesis import strategies as st

from ipc_codec import CustomerAccount, Rot13Token


_TZ_STRATEGY: st.SearchStrategy[Any] = st.one_of(
    st.none(),
    st.just(timezone.utc),
    st.builds(lambda mins: timezone(timedelta(minutes=mins)), st.integers(min_value=-720, max_value=720)),
)

_SAFE_INT: st.SearchStrategy[int] = st.integers(min_value=-(10**30), max_value=10**30)
_FINITE_FLOAT: st.SearchStrategy[float] = st.floats(allow_nan=False, allow_infinity=False, width=64)
_SAFE_TEXT: st.SearchStrategy[str] = st.one_of(
    st.text(max_size=48),
    st.sampled_from(
        [
            "",
            ":",
            "::",
            "str:lookalike",
            "int:42",
            "bool:True",
            "NoneType:None",
            "tuple:[1, 2]",
            "user:1001:profile",
            "\x1fescaped",
            "unicode:☃🚀éüñ",
        ]
    ),
)

_JSON_PRIMITIVE: st.SearchStrategy[Any] = st.one_of(
    st.none(),
    st.booleans(),
    _SAFE_INT,
    _FINITE_FLOAT,
    _SAFE_TEXT,
)

_PLAIN_JSON_TREE: st.SearchStrategy[Any] = st.recursive(
    _JSON_PRIMITIVE,
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(
            st.text(max_size=16).filter(lambda k: k != "__type__"),
            children,
            max_size=4,
        ),
    ),
    max_leaves=10,
)


def string_key_strategy() -> st.SearchStrategy[str]:
    """Generate adversarial and general string keys valid across all RedisDict versions.

    Includes empty strings, colons, hierarchical namespaces, type-prefix lookalikes
    (``int:42``, ``str:hello``, ``NoneType:None``), control-prefix strings, and Unicode.

    Returns:
        st.SearchStrategy[str]: Hypothesis strategy producing ``str`` keys.
    """
    return st.one_of(
        st.text(min_size=0, max_size=40),
        st.sampled_from(
            [
                "",
                ":",
                "a:b:c",
                "int:42",
                "str:hello",
                "float:3.14",
                "bool:False",
                "NoneType:None",
                "__type__",
                "\x1f",
                "\x1fint:99",
                "emoji:🔑:value",
            ]
        ),
    )


def _scalar_strategy_by_name() -> Dict[str, st.SearchStrategy[Any]]:
    return {
        "str": _SAFE_TEXT,
        "int": _SAFE_INT,
        "float": _FINITE_FLOAT,
        "bool": st.booleans(),
        "NoneType": st.none(),
        "bytes": st.binary(max_size=48),
        "Decimal": st.decimals(
            allow_nan=False,
            allow_infinity=False,
            min_value=Decimal("-1000000000"),
            max_value=Decimal("1000000000"),
            places=6,
        ),
        "complex": st.builds(complex, _FINITE_FLOAT, _FINITE_FLOAT),
        "UUID": st.uuids(),
        "date": st.dates(min_value=date(1900, 1, 1), max_value=date(2200, 12, 31)),
        "time": st.times(timezones=_TZ_STRATEGY),
        "datetime": st.datetimes(
            min_value=datetime(1900, 1, 1),
            max_value=datetime(2200, 12, 31),
            timezones=_TZ_STRATEGY,
        ),
        "timedelta": st.builds(
            lambda d, s, ms: timedelta(days=d, seconds=s, milliseconds=ms),
            st.integers(min_value=-3650, max_value=3650),
            st.integers(min_value=0, max_value=86399),
            st.integers(min_value=0, max_value=999),
        ),
    }


def _hashable_leaf_strategy(allowed_types: FrozenSet[str]) -> st.SearchStrategy[Any]:
    scalars = _scalar_strategy_by_name()
    parts = [strat for name, strat in scalars.items() if name in allowed_types]
    return st.one_of(*parts) if parts else _SAFE_TEXT


def nested_value_strategy(
    allowed_types: Iterable[str],
    allow_tagged_containers: bool = True,
) -> st.SearchStrategy[Any]:
    """Build a recursive Hypothesis value strategy restricted to ``allowed_types``.

    Args:
        allowed_types (Iterable[str]): Names of ``decoding_registry`` types supported by the writer/reader.
        allow_tagged_containers (bool): Whether nested ``tuple``/``set``/``frozenset`` and ``__type__``
            dicts inside JSON containers are supported by all participating versions.

    Returns:
        st.SearchStrategy[Any]: Recursive Hypothesis strategy for cross-version values.
    """
    allowed = frozenset(allowed_types)
    scalars = _scalar_strategy_by_name()
    leaf_parts = [strat for name, strat in scalars.items() if name in allowed]
    base_leaf = st.one_of(*leaf_parts) if leaf_parts else _SAFE_TEXT
    hashable_leaf = _hashable_leaf_strategy(allowed)

    if not allow_tagged_containers:
        return _legacy_container_strategy(allowed, base_leaf)

    hashable_nested: st.SearchStrategy[Any] = st.one_of(
        hashable_leaf,
        st.tuples(hashable_leaf, hashable_leaf),
        st.frozensets(hashable_leaf, max_size=3),
    )

    def _extend(children: st.SearchStrategy[Any]) -> st.SearchStrategy[Any]:
        branches: List[st.SearchStrategy[Any]] = []
        if "list" in allowed:
            branches.append(st.lists(children, max_size=4))
        if "tuple" in allowed:
            branches.append(st.lists(children, max_size=4).map(tuple))
        if "dict" in allowed:
            branches.append(st.dictionaries(string_key_strategy(), children, max_size=4))
            branches.append(
                st.dictionaries(
                    st.one_of(st.just("__type__"), _SAFE_INT, st.tuples(_SAFE_TEXT, _SAFE_INT)),
                    children,
                    max_size=3,
                )
            )
        if "set" in allowed:
            branches.append(st.sets(hashable_nested, max_size=4))
        if "frozenset" in allowed:
            branches.append(st.frozensets(hashable_nested, max_size=4))
        return st.one_of(*branches) if branches else children

    recursive_core = st.recursive(base_leaf, _extend, max_leaves=10)
    top_extras = _ordered_and_default_dict_strategies(allowed)
    return st.one_of(recursive_core, *top_extras) if top_extras else recursive_core


def _ordered_and_default_dict_strategies(allowed: FrozenSet[str]) -> List[st.SearchStrategy[Any]]:
    extras: List[st.SearchStrategy[Any]] = []
    if "OrderedDict" in allowed:
        extras.append(
            st.lists(
                st.tuples(st.text(min_size=1, max_size=16), _PLAIN_JSON_TREE),
                max_size=5,
                unique_by=lambda kv: kv[0],
            ).map(OrderedDict)
        )
    if "defaultdict" in allowed:
        extras.append(
            st.dictionaries(st.text(min_size=1, max_size=16), _PLAIN_JSON_TREE, max_size=5).map(
                lambda d: defaultdict(type(None), d)
            )
        )
    return extras


def _legacy_container_strategy(
    allowed: FrozenSet[str],
    base_leaf: st.SearchStrategy[Any],
) -> st.SearchStrategy[Any]:
    parts: List[st.SearchStrategy[Any]] = [base_leaf]
    safe_str_key = st.text(max_size=16).filter(lambda k: k != "__type__")
    if "list" in allowed:
        parts.append(st.lists(base_leaf, max_size=4))
    if "dict" in allowed:
        parts.append(st.dictionaries(safe_str_key, base_leaf, max_size=4))
    if "tuple" in allowed:
        parts.append(st.lists(_JSON_PRIMITIVE, max_size=4).map(tuple))
    if "set" in allowed:
        parts.append(st.sets(_JSON_PRIMITIVE, max_size=4))
    if "frozenset" in allowed:
        parts.append(st.frozensets(_JSON_PRIMITIVE, max_size=4))
    parts.extend(_ordered_and_default_dict_strategies(allowed))
    return st.one_of(*parts)


def strategy_map_for_registry(
    allow_tagged_containers: bool = True,
) -> Dict[str, Callable[[], st.SearchStrategy[Any]]]:
    """Return a factory mapping every built-in ``decoding_registry`` type name to a Hypothesis strategy.

    Args:
        allow_tagged_containers (bool): Whether nested tagged containers are enabled for container types.

    Returns:
        Dict[str, Callable[[], st.SearchStrategy[Any]]]: Mapping of type name to strategy factory.
    """
    scalars = _scalar_strategy_by_name()
    all_names = frozenset(
        [*scalars.keys(), "list", "dict", "tuple", "set", "frozenset", "OrderedDict", "defaultdict"]
    )
    child_strat = nested_value_strategy(all_names, allow_tagged_containers=allow_tagged_containers)
    elem_strat = _hashable_leaf_strategy(all_names) if allow_tagged_containers else _JSON_PRIMITIVE
    mapping: Dict[str, Callable[[], st.SearchStrategy[Any]]] = {
        name: (lambda s=strat: s) for name, strat in scalars.items()  # type: ignore[misc]
    }
    mapping["list"] = lambda: st.lists(child_strat if allow_tagged_containers else _PLAIN_JSON_TREE, max_size=4)
    mapping["dict"] = lambda: st.dictionaries(
        st.text(min_size=1, max_size=16).filter(lambda k: k != "__type__"),
        child_strat if allow_tagged_containers else _PLAIN_JSON_TREE,
        max_size=4,
    )
    mapping["tuple"] = lambda: st.lists(
        child_strat if allow_tagged_containers else _JSON_PRIMITIVE,
        max_size=4,
    ).map(tuple)
    mapping["set"] = lambda: st.sets(elem_strat, max_size=4)
    mapping["frozenset"] = lambda: st.frozensets(elem_strat, max_size=4)
    mapping["OrderedDict"] = lambda: st.lists(
        st.tuples(st.text(min_size=1, max_size=16), _PLAIN_JSON_TREE),
        min_size=0,
        max_size=5,
        unique_by=lambda kv: kv[0],
    ).map(OrderedDict)
    mapping["defaultdict"] = lambda: st.dictionaries(
        st.text(min_size=1, max_size=16),
        _PLAIN_JSON_TREE,
        max_size=5,
    ).map(lambda d: defaultdict(type(None), d))
    return mapping


def assert_strategy_registry_complete(registry_type_names: Iterable[str]) -> None:
    """Assert that every type in a version's ``decoding_registry`` has a dedicated Hypothesis strategy.

    Args:
        registry_type_names (Iterable[str]): Type names reported by a worker's ``RedisDict.decoding_registry``.

    Raises:
        AssertionError: If any ``decoding_registry`` type lacks a registered Hypothesis strategy.
    """
    known: Set[str] = set(strategy_map_for_registry(allow_tagged_containers=True).keys())
    required: Set[str] = set(registry_type_names)
    missing = sorted(required - known)
    if missing:
        raise AssertionError(
            f"Missing Hypothesis cross-version strategies for decoding_registry types: {missing}"
        )


def per_type_dict_strategy(
    registry_type_names: Sequence[str],
    allow_tagged_containers: bool,
) -> st.SearchStrategy[Dict[str, Any]]:
    """Generate a dictionary containing at least one dynamic example per ``decoding_registry`` type plus extras.

    Args:
        registry_type_names (Sequence[str]): Supported ``decoding_registry`` type names.
        allow_tagged_containers (bool): Whether nested tagged containers are enabled.

    Returns:
        st.SearchStrategy[Dict[str, Any]]: Strategy producing ``Dict[str, Any]`` payloads.
    """
    assert_strategy_registry_complete(registry_type_names)
    factories = strategy_map_for_registry(allow_tagged_containers=allow_tagged_containers)
    typed_entries = st.fixed_dictionaries(
        {f"type:{name}": factories[name]() for name in registry_type_names}
    )
    extra_entries = st.dictionaries(
        string_key_strategy().filter(lambda k: not k.startswith("type:")),
        nested_value_strategy(registry_type_names, allow_tagged_containers=allow_tagged_containers),
        min_size=1,
        max_size=8,
    )
    return st.builds(lambda a, b: {**a, **b}, typed_entries, extra_entries)


def custom_extends_strategy() -> st.SearchStrategy[Dict[str, Any]]:
    """Generate variable ``extends_type`` values (domain objects and ``str`` subclasses).

    Returns:
        st.SearchStrategy[Dict[str, Any]]: Strategy mapping string keys to custom extendable objects.
    """
    account_strat = st.builds(
        CustomerAccount,
        st.integers(min_value=-100000, max_value=100000),
        st.text(max_size=24),
    )
    token_strat = st.builds(Rot13Token, st.text(max_size=24))
    return st.dictionaries(
        st.text(min_size=1, max_size=20),
        st.one_of(account_strat, token_strat),
        min_size=2,
        max_size=6,
    )


def typed_keys_dict_strategy() -> st.SearchStrategy[Dict[Any, Any]]:
    """Generate dictionaries with non-string hashable keys alongside lookalike string keys.

    Returns:
        st.SearchStrategy[Dict[Any, Any]]: Strategy mapping typed keys to nested values.
    """
    key_strat: st.SearchStrategy[Any] = st.one_of(
        string_key_strategy(),
        _SAFE_INT,
        _FINITE_FLOAT,
        st.booleans(),
        st.none(),
        st.uuids(),
        st.tuples(_SAFE_TEXT, _SAFE_INT),
        st.frozensets(_SAFE_INT, max_size=3),
        st.builds(Rot13Token, st.text(min_size=1, max_size=12)),
    )
    # Build via unique canonical freeze so True and 1 do not overwrite each other in Python's input dict
    return st.lists(
        st.tuples(key_strat, _PLAIN_JSON_TREE),
        min_size=2,
        max_size=8,
    ).map(dict)


def stateful_steps_strategy(
    allowed_types: Sequence[str],
    allow_tagged_containers: bool,
) -> st.SearchStrategy[List[Tuple[str, str, Any]]]:
    """Generate an interleaved sequence of ``(worker_target, op_name, arg)`` steps across two versions.

    Args:
        allowed_types (Sequence[str]): Intersection of ``decoding_registry`` types supported by both versions.
        allow_tagged_containers (bool): Whether both versions support nested tagged JSON containers.

    Returns:
        st.SearchStrategy[List[Tuple[str, str, Any]]]: Strategy producing stateful operation lists.
    """
    key_pool = st.sampled_from(["alpha", "beta:1", "int:42", "str:x", "", "unicode:🚀", "omega"])
    val_strat = nested_value_strategy(allowed_types, allow_tagged_containers=allow_tagged_containers)
    target_strat = st.sampled_from(["prev", "next"])
    op_strat: st.SearchStrategy[Tuple[str, Any]] = st.one_of(
        st.tuples(st.just("set"), st.tuples(key_pool, val_strat)),
        st.tuples(st.just("setdefault"), st.tuples(key_pool, val_strat)),
        st.tuples(
            st.just("update"),
            st.dictionaries(key_pool, val_strat, min_size=1, max_size=3),
        ),
        st.tuples(st.just("pop"), key_pool),
        st.tuples(st.just("delete"), key_pool),
        st.tuples(st.just("popitem"), st.none()),
    )
    return st.lists(
        st.builds(lambda tgt, op_pair: (tgt, op_pair[0], op_pair[1]), target_strat, op_strat),
        min_size=6,
        max_size=20,
    )
