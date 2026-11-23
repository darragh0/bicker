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
    from collections.abc import Collection, Sequence

    from bicker._style import Style


type HelpKey = Literal["-h", "--help"]

# Supported value types; bool is supported separately, for flags only
_SCALAR_TYPES: Final[tuple[type, ...]] = (str, int, float)
# Literal can't hold floats (PEP 586); each type maps to how its choices are styled
LITERAL_TYPES: Final[dict[type, Style]] = {str: Styles.STR_VALUE, int: Styles.INT_VALUE}


class Converter(Protocol):
    __name__: str

    def __call__(self, raw: str, /) -> object: ...


@dataclass(frozen=True, kw_only=True)
class _Declaration:
    """What `pos()`, `opt()` and `flag()` return; the type isn't known until `collect_fields`."""

    default: object
    short: str | None = None
    is_pos: bool = False
    custom_metavar: str | None = None
    description: str | None = None


@final
@dataclass(frozen=True, kw_only=True)
class Field(_Declaration):
    name: str
    typ: Converter

    @property
    def long_key(self) -> str:
        return f"--{self.name.replace('_', '-')}"

    @property
    def style(self) -> Style:
        if self.is_flag:
            return Styles.FLAG
        return Styles.POS if self.is_pos else Styles.OPT

    @property
    def is_flag(self) -> bool:
        return self.typ is bool

    @property
    def is_required(self) -> bool:
        return self.default is MISSING

    @property
    def is_list(self) -> bool:
        """Whether this takes many values: the rest of the positionals, or a repeated option."""
        return get_origin(self.typ) is list

    @property
    def value_typ(self) -> Converter:
        """The type of each value: `T` for `list[T]`, otherwise the field's own type."""
        if not self.is_list:
            return self.typ
        args: tuple[Converter, ...] = get_args(self.typ)
        return args[0]

    @property
    def choices(self) -> tuple[object, ...]:
        """The values of a `Literal` type, or `()` for any other type."""
        return get_args(self.value_typ) if get_origin(self.value_typ) is Literal else ()

    @property
    def metavar(self) -> str | None:
        """The help placeholder: the custom one if set, else `{a,b}` for choices or `NAME`."""
        if self.is_flag:
            return None
        if self.custom_metavar:
            return self.custom_metavar
        if self.choices:
            return "{" + ",".join(map(str, self.choices)) + "}"
        return self.name.upper()


# T only in the return type is intentional: it's inferred from the field's annotation
@overload
def pos[T](*, description: str | None = None) -> T: ...  # pyright: ignore[reportInvalidTypeVarUse]
@overload
def pos[T](default: T, *, description: str | None = None) -> T: ...
def pos(default: object = MISSING, *, description: str | None = None) -> object:
    return _Declaration(default=default, is_pos=True, description=description)


def opt[T](
    default: T,
    short: str | None = None,
    *,
    metavar: str | None = None,
    description: str | None = None,
) -> T:
    decl = _Declaration(
        default=default, short=short, custom_metavar=metavar, description=description
    )
    return cast("T", decl)


def flag(short: str | None = None, *, description: str | None = None) -> bool:
    return opt(default=False, short=short, description=description)


def collect_fields(spec: type[object], help_keys: Collection[HelpKey]) -> list[Field]:

    fields: list[Field] = []
    hints: dict[str, Converter] = get_type_hints(spec)

    for name, typ in hints.items():
        decl = getattr(spec, name, None)
        if not isinstance(decl, _Declaration):
            msg = f"{name!r} must be declared with pos(), opt() or flag()"
            raise TypeError(msg)

        field = Field(
            name=name,
            typ=typ,
            default=decl.default,
            short=decl.short,
            is_pos=decl.is_pos,
            custom_metavar=decl.custom_metavar,
            description=decl.description,
        )
        _check_type(field)
        fields.append(field)

    _check_shorts(fields)
    if help_keys:
        _check_help_clash(fields, help_keys)
    _check_positional_order(fields)

    return fields


def _check_type(field: Field) -> None:
    typ: object = field.value_typ
    supported = (
        (isinstance(typ, type) and typ in _SCALAR_TYPES)
        or (field.is_flag and not field.is_pos)
        or (field.choices and all(type(choice) in LITERAL_TYPES for choice in field.choices))
    )

    if not supported:
        scalars = ", ".join(t.__name__ for t in _SCALAR_TYPES)
        literals = "/".join(t.__name__ for t in LITERAL_TYPES)
        msg = (
            f"{field.name!r} has unsupported type {field.typ!r} "
            f"(supported: {scalars}, Literal of {literals}, a list of those, "
            "and bool for flags)"
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


def _check_help_clash(fields: Sequence[Field], help_keys: Collection[HelpKey]) -> None:
    for field in fields:
        if field.is_pos:
            continue
        for key in (field.long_key, field.short):
            if key in help_keys:
                msg = (
                    f"{field.name!r} uses {key!r}, which is reserved for help "
                    "-- free it with parse_args(..., help_keys=...)"
                )
                raise TypeError(msg)


def _check_positional_order(fields: Sequence[Field]) -> None:
    # False (required) sorts before True (optional)
    is_optional = [not field.is_required for field in fields if field.is_pos]

    if is_optional != sorted(is_optional):
        msg = "required positionals must precede optional ones"
        raise TypeError(msg)

    # A list positional takes all remaining values, so nothing can come after it
    pos_fields = [field for field in fields if field.is_pos]
    if any(field.is_list for field in pos_fields[:-1]):
        msg = "only the last positional can be a list"
        raise TypeError(msg)
