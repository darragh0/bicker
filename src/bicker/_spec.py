import re
from collections import Counter
from dataclasses import MISSING, dataclass
from typing import (
    TYPE_CHECKING,
    Final,
    Literal,
    Protocol,
    cast,
    final,
    get_args,
    get_origin,
    overload,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


# Supported value types; bool is supported separately, for flags only
_SCALAR_TYPES: Final[tuple[type, ...]] = (str, int, float)
_LITERAL_TYPES: Final[tuple[type, ...]] = (str, int)


class Converter(Protocol):
    __name__: str

    def __call__(self, raw: str, /) -> object: ...


@dataclass(frozen=True, kw_only=True)
class _Declaration:
    """What `pos()`, `opt()` and `flag()` return; the type isn't known until `collect_fields`."""

    default: object
    short: str | None = None
    is_pos: bool = False


@final
@dataclass(frozen=True, kw_only=True)
class Field(_Declaration):
    tp: Converter

    @property
    def is_flag(self) -> bool:
        return self.tp is bool


# T only in the return type is intentional: it's inferred from the field's annotation
@overload
def pos[T]() -> T: ...  # pyright: ignore[reportInvalidTypeVarUse]
@overload
def pos[T](default: T) -> T: ...
def pos(default: object = MISSING) -> object:
    return _Declaration(default=default, is_pos=True)


def opt[T](default: T, short: str | None = None) -> T:
    return cast("T", _Declaration(default=default, short=short))


def flag(short: str | None = None) -> bool:
    return opt(default=False, short=short)


def collect_fields(spec: type[object], hints: Mapping[str, Converter]) -> dict[str, Field]:
    fields: dict[str, Field] = {}

    for name, tp in hints.items():
        decl = getattr(spec, name, None)
        if not isinstance(decl, _Declaration):
            msg = f"{name!r} must be declared with pos(), opt() or flag()"
            raise TypeError(msg)

        field = Field(default=decl.default, short=decl.short, is_pos=decl.is_pos, tp=tp)
        _check_type(name, field)
        fields[name] = field

    _check_shorts(fields)
    _check_positional_order(fields)
    return fields


def _check_type(name: str, field: Field) -> None:
    tp: object = field.tp
    literal_args: tuple[object, ...] = get_args(tp) if get_origin(tp) is Literal else ()
    supported = (
        (isinstance(tp, type) and tp in _SCALAR_TYPES)
        or (field.is_flag and not field.is_pos)
        or (literal_args and all(type(arg) in _LITERAL_TYPES for arg in literal_args))
    )

    if not supported:
        scalars = ", ".join(t.__name__ for t in _SCALAR_TYPES)
        literals = "/".join(t.__name__ for t in _LITERAL_TYPES)
        msg = (
            f"{name!r} has unsupported type {tp!r} "
            f"(supported: {scalars}, Literal of {literals}, and bool for flags)"
        )
        raise TypeError(msg)


def _check_shorts(fields: Mapping[str, Field]) -> None:
    for name, field in fields.items():
        if field.short is not None and not re.fullmatch(r"-[A-Za-z0-9]", field.short):
            msg = (
                f"{name!r} has invalid short {field.short!r} "
                "(expected '-' plus one letter or digit)"
            )
            raise TypeError(msg)

    counts = Counter(field.short for field in fields.values() if field.short)
    if duplicates := [short for short, count in counts.items() if count > 1]:
        msg = f"short options used more than once: {', '.join(duplicates)}"
        raise TypeError(msg)


def _check_positional_order(fields: Mapping[str, Field]) -> None:
    # False (required) sorts before True (optional)
    is_optional = [field.default is not MISSING for field in fields.values() if field.is_pos]

    if is_optional != sorted(is_optional):
        msg = "required positionals must precede optional ones"
        raise TypeError(msg)
