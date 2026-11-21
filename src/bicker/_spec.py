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
    get_type_hints,
    overload,
)

from bicker._style import Styles

if TYPE_CHECKING:
    from collections.abc import Sequence

    from bicker._style import Style


# Supported value types; bool is supported separately, for flags only
_SCALAR_TYPES: Final[tuple[type, ...]] = (str, int, float)
# Literal can't hold floats (PEP 586); each type maps to how its choices are styled
LITERAL_TYPES: Final[dict[type, Style]] = {str: Styles.STR, int: Styles.INT}


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
    name: str
    tp: Converter

    @property
    def long_key(self) -> str:
        return f"--{self.name.replace('_', '-')}"

    @property
    def label_style(self) -> Style:
        return Styles.POS if self.is_pos else Styles.OPT

    @property
    def is_flag(self) -> bool:
        return self.tp is bool

    @property
    def is_required(self) -> bool:
        return self.default is MISSING

    @property
    def choices(self) -> tuple[object, ...]:
        """The values of a `Literal` type, or `()` for any other type."""
        return get_args(self.tp) if get_origin(self.tp) is Literal else ()


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


def collect_fields(spec: type[object]) -> list[Field]:

    fields: list[Field] = []
    hints: dict[str, Converter] = get_type_hints(spec)

    for name, tp in hints.items():
        decl = getattr(spec, name, None)
        if not isinstance(decl, _Declaration):
            msg = f"{name!r} must be declared with pos(), opt() or flag()"
            raise TypeError(msg)

        field = Field(name=name, tp=tp, default=decl.default, short=decl.short, is_pos=decl.is_pos)
        _check_type(field)
        fields.append(field)

    _check_shorts(fields)
    _check_positional_order(fields)

    return fields


def _check_type(field: Field) -> None:
    tp: object = field.tp
    supported = (
        (isinstance(tp, type) and tp in _SCALAR_TYPES)
        or (field.is_flag and not field.is_pos)
        or (field.choices and all(type(choice) in LITERAL_TYPES for choice in field.choices))
    )

    if not supported:
        scalars = ", ".join(t.__name__ for t in _SCALAR_TYPES)
        literals = "/".join(t.__name__ for t in LITERAL_TYPES)
        msg = (
            f"{field.name!r} has unsupported type {tp!r} "
            f"(supported: {scalars}, Literal of {literals}, and bool for flags)"
        )
        raise TypeError(msg)


def _check_shorts(fields: Sequence[Field]) -> None:
    for field in fields:
        if field.short is not None and not re.fullmatch(r"-[A-Za-z0-9]", field.short):
            msg = (
                f"{field.name!r} has invalid short {field.short!r} "
                "(expected '-' plus one letter or digit)"
            )
            raise TypeError(msg)

    counts = Counter(field.short for field in fields if field.short)
    if duplicates := [short for short, count in counts.items() if count > 1]:
        msg = f"short options used more than once: {', '.join(duplicates)}"
        raise TypeError(msg)


def _check_positional_order(fields: Sequence[Field]) -> None:
    # False (required) sorts before True (optional)
    is_optional = [not field.is_required for field in fields if field.is_pos]

    if is_optional != sorted(is_optional):
        msg = "required positionals must precede optional ones"
        raise TypeError(msg)
