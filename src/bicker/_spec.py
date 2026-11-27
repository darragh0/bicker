from __future__ import annotations

import re
from collections import Counter
from dataclasses import MISSING, dataclass
from inspect import cleandoc
from types import GenericAlias, NoneType, UnionType
from typing import (
    TYPE_CHECKING,
    Final,
    Literal,
    TypeAliasType,
    cast,
    final,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from bicker._style import Styles

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from bicker._style import Style


type HelpKey = Literal["-h", "--help"]
type VersionKey = Literal["-V", "--version"]

# How many values a list field takes: exactly `n`, or `(min, max)` with `None` for no max
type Nargs = int | tuple[int, int | None]

_SHORT_KEY: Final = re.compile(r"-[A-Za-z0-9]")
_LONG_KEY: Final = re.compile(r"--[A-Za-z0-9][A-Za-z0-9-]*")

# Where a class name gets a dash in its command name: `RunTests` -> `run-tests`, `HTTPGet` ->
# `http-get`
_WORD_BOUNDARY: Final = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

# Supported value types; bool is supported separately, for flags only
_SCALAR_TYPES: Final = (str, int, float)

# Literal can't hold floats (PEP 586); each type maps to how its choices are styled
LITERAL_TYPES: Final[Mapping[type, Style]] = {str: Styles.STR_VALUE, int: Styles.INT_VALUE}


# Compared by identity (eq=False), so fields can be dict keys even with a list default
@dataclass(frozen=True, kw_only=True, eq=False)
class _Declaration:
    """What `pos()`, `opt()` and `flag()` return; the type isn't known until `collect_fields`."""

    # MISSING for a required argument
    default: object
    short: str | None = None
    custom_long: str | None = None
    is_pos: bool = False
    custom_metavar: str | None = None
    description: str | None = None
    nargs: Nargs | None = None
    # The help heading an option is listed under
    group: str = "Options"


@final
@dataclass(frozen=True, kw_only=True, eq=False)
class Field(_Declaration):
    name: str
    # The type values are parsed as, e.g. `int` (for `int | None`), `list[str]` or `Literal["a"]`
    typ: object

    @property
    def long_key(self) -> str:
        """The custom long key if set, else derived from the name: `dry_run` -> `--dry-run`."""
        return self.custom_long or f"--{self.name.replace('_', '-')}"

    @property
    def keys(self) -> tuple[str, ...]:
        """An option's keys, short first, e.g. `("-c", "--count")`."""
        return (self.short, self.long_key) if self.short else (self.long_key,)

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
        if self.is_list:
            return self.nargs_range[0] > 0
        return self.default is MISSING

    @property
    def nargs_range(self) -> tuple[int, int | None]:
        """`(min, max)` values for a list; defaults to 1+ without a default, 0+ with one."""
        if isinstance(self.nargs, int):
            return (self.nargs, self.nargs)
        if self.nargs is not None:
            return self.nargs
        return (1 if self.default is MISSING else 0, None)

    @property
    def is_list(self) -> bool:
        """Whether this takes many values: the rest of the positionals, or a repeated option."""
        return get_origin(self.typ) is list

    @property
    def value_typ(self) -> object:
        """The type of each value: `T` for `list[T]`, otherwise the field's own type."""
        if not self.is_list:
            return self.typ
        args: tuple[object, ...] = get_args(self.typ)
        return args[0]

    @property
    def scalar_typ(self) -> type[str | int | float] | None:
        """The value type if it's `str`, `int` or `float`, else `None` (e.g. for a `Literal`)."""
        typ = self.value_typ
        return typ if isinstance(typ, type) and typ in _SCALAR_TYPES else None

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


@final
@dataclass(frozen=True, kw_only=True, eq=False)
class Spec:
    """A class of declarations, as read by `collect_spec`: the program, or one of its commands."""

    cls: type[object]
    options: tuple[Field, ...]
    positionals: tuple[Field, ...]
    # The `cmd()` attribute's name, and its commands by name; `None` and empty without one
    command_attr: str | None
    commands: Mapping[str, Spec]

    @property
    def name(self) -> str:
        """The command name: the class name in kebab-case, e.g. `RunTests` -> `run-tests`."""
        return _WORD_BOUNDARY.sub("-", self.cls.__name__).lower()

    @property
    def description(self) -> str | None:
        """The class docstring, without its indentation."""
        return cleandoc(self.cls.__doc__) if self.cls.__doc__ else None


@final
class _CommandDeclaration:
    """What `cmd()` returns; the commands are read from the field's annotation."""


# T only in the return type is intentional: it's inferred from the field's annotation
@overload
def pos[T](*, description: str | None = None, nargs: Nargs | None = None) -> T: ...  # type: ignore[type-var]  # pyright: ignore[reportInvalidTypeVarUse]
@overload
def pos[T](default: T, *, description: str | None = None, nargs: Nargs | None = None) -> T: ...
def pos(
    default: object = MISSING,
    *,
    description: str | None = None,
    nargs: Nargs | None = None,
) -> object:
    """Declare a positional argument.

    Positionals are matched in the order they're declared. Positionals with a `default` are
    optional and must come after required ones. Annotate the field as `list[T]` to take several
    values; unless `nargs` fixes the count, it must be the last positional.

    Args:
        default: The value used when the positional isn't given. Omit it to make the
            positional required.
        description: The help text for this positional.
        nargs: How many values a `list[T]` positional takes: exactly `n`, or `(min, max)` with
            `None` for no max. Defaults to at least 1, or at least 0 when `default` is given.

    Returns:
        A placeholder that `parse_args` replaces with the parsed value.
    """
    return _Declaration(default=default, is_pos=True, description=description, nargs=nargs)


@overload
def opt[T](
    *,
    required: Literal[True],
    short: str | None = None,
    long: str | None = None,
    description: str | None = None,
    metavar: str | None = None,
    nargs: Nargs | None = None,
    group: str = "Options",
) -> T: ...  # type: ignore[type-var]  # pyright: ignore[reportInvalidTypeVarUse]
@overload
def opt[T](
    default: T,
    *,
    short: str | None = None,
    long: str | None = None,
    description: str | None = None,
    metavar: str | None = None,
    nargs: Nargs | None = None,
    group: str = "Options",
) -> T: ...
@overload
def opt[T](
    *,
    short: str | None = None,
    long: str | None = None,
    description: str | None = None,
    metavar: str | None = None,
    nargs: Nargs | None = None,
    group: str = "Options",
) -> T | None: ...
def opt(
    default: object = None,
    *,
    required: bool = False,
    short: str | None = None,
    long: str | None = None,
    description: str | None = None,
    metavar: str | None = None,
    nargs: Nargs | None = None,
    group: str = "Options",
) -> object:
    """Declare an option that takes a value.

    Annotate the field as `list[T]` to make the option repeatable: each use adds one value.

    Args:
        default: The value used when the option isn't given. Defaults to `None`, so annotate
            the field as `T | None`. For a `list[T]` option, given values replace the
            default rather than extend it.
        required: Whether the option must be given. A required option has no default.
        short: A short key like `-c`: a dash plus one letter or digit.
        long: A long key like `--count`. Defaults to the field name, e.g. `--dry-run` for
            `dry_run`.
        description: The help text for this option.
        metavar: The value's placeholder in help. Defaults to `{a,b}` for a `Literal`, and
            the field name in uppercase otherwise.
        nargs: How many times a `list[T]` option can be given: exactly `n`, or `(min, max)`
            with `None` for no max. Defaults to any number, or at least 1 when `required`.
        group: The help heading to list this option under.

    Returns:
        A placeholder that `parse_args` replaces with the parsed value.
    """
    return _Declaration(
        default=MISSING if required else default,
        short=short,
        custom_long=long,
        custom_metavar=metavar,
        description=description,
        nargs=nargs,
        group=group,
    )


def flag(
    *,
    short: str | None = None,
    long: str | None = None,
    description: str | None = None,
    group: str = "Options",
) -> bool:
    """Declare a flag: a `bool` option without a value. Defaults to `False` unless flag is given.

    Args:
        short: A short key like `-v`: a dash plus one letter or digit.
        long: A long key like `--verbose`. Defaults to the field name, e.g. `--dry-run` for
            `dry_run`.
        description: The help text for this flag.
        group: The help heading to list this flag under.

    Returns:
        A placeholder that `parse_args` replaces with the parsed value.
    """
    return opt(default=False, short=short, long=long, description=description, group=group)


def cmd[T]() -> T:  # type: ignore[type-var]  # pyright: ignore[reportInvalidTypeVarUse]
    """Declare the command, annotated with one class per command, e.g. `command: Build | Test`.

    Each class declares its command's arguments, like the class passed to `parse_args`, and
    its docstring is the command's help text. A command's name is its class name in kebab-case,
    e.g. `run-tests` for `RunTests`. Options declared next to `cmd()` can be given before or
    after the command. A class with a command can't have positionals.

    Returns:
        A placeholder that `parse_args` replaces with an instance of the given command's class.
    """
    return cast("T", _CommandDeclaration())


def collect_spec(
    cls: type[object],
    reserved: Mapping[str, str],
    inherited: Sequence[Field] = (),
) -> Spec:
    """Read `cls`'s declarations, checking none use a `reserved` key (mapped to its setting).

    `inherited` holds the options declared above a command, which its keys mustn't clash with.
    """
    fields: list[Field] = []
    command_attr: str | None = None
    command_classes: tuple[type[object], ...] = ()
    hints: dict[str, object] = get_type_hints(cls)

    for name, typ in hints.items():
        decl = getattr(cls, name, None)
        if isinstance(decl, _Declaration):
            fields.append(_field(name, typ, decl))
        elif not isinstance(decl, _CommandDeclaration):
            msg = f"{name!r} must be declared with pos(), opt(), flag() or cmd()"
            raise TypeError(msg)
        elif command_attr:
            msg = f"{cls.__name__} has more than one cmd()"
            raise TypeError(msg)
        else:
            command_attr, command_classes = name, _command_classes(name, typ)

    options = tuple(field for field in fields if not field.is_pos)
    positionals = tuple(field for field in fields if field.is_pos)
    _check_keys([*inherited, *options])
    _check_reserved(options, reserved)
    _check_positional_order(positionals)
    if command_attr and positionals:
        msg = f"{cls.__name__} has a cmd(), so it can't have positionals"
        raise TypeError(msg)

    commands: dict[str, Spec] = {}
    for command_cls in command_classes:
        command = collect_spec(command_cls, reserved, [*inherited, *options])
        if command.name in commands:
            msg = f"command name {command.name!r} used more than once"
            raise TypeError(msg)
        commands[command.name] = command

    return Spec(
        cls=cls,
        options=options,
        positionals=positionals,
        command_attr=command_attr,
        commands=commands,
    )


def _field(name: str, typ: object, decl: _Declaration) -> Field:
    field = Field(
        name=name,
        typ=_parsed_type(typ),
        default=decl.default,
        short=decl.short,
        custom_long=decl.custom_long,
        is_pos=decl.is_pos,
        custom_metavar=decl.custom_metavar,
        description=decl.description,
        nargs=decl.nargs,
        group=decl.group,
    )
    _check_type(field)
    _check_nargs(field)
    return field


def _command_classes(name: str, typ: object) -> tuple[type[object], ...]:
    """Get the classes in a `cmd()` annotation: one class, or a union of several."""
    typ = _expand_aliases(typ)
    members: tuple[object, ...] = get_args(typ) if get_origin(typ) is UnionType else (typ,)
    classes = tuple(m for m in members if isinstance(m, type) and m is not NoneType)
    if len(classes) != len(members):
        msg = f"{name!r} must be annotated with a class or a union of classes"
        raise TypeError(msg)
    return classes


def _parsed_type(typ: object) -> object:
    """Get the type to parse values as: `T` for `T | None`, with `type X = ...` aliases expanded."""
    typ = _expand_aliases(typ)
    if get_origin(typ) is UnionType:
        args: tuple[object, ...] = get_args(typ)
        # Only `T | None` has one non-None member; `int | str` stays unsupported
        if len(non_none := [arg for arg in args if arg is not NoneType]) == 1:
            typ = _expand_aliases(non_none[0])
    return typ


def _expand_aliases(typ: object) -> object:
    """Replace `type X = ...` aliases with what they stand for, including inside `list[X]`."""
    while isinstance(typ, TypeAliasType):
        typ = cast("object", typ.__value__)
    if get_origin(typ) is list:
        args: tuple[object, ...] = get_args(typ)
        return GenericAlias(list, (_expand_aliases(args[0]),))
    return typ


def _check_type(field: Field) -> None:
    supported = (
        field.scalar_typ is not None
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


def _check_nargs(field: Field) -> None:
    if field.nargs is None:
        return
    if not field.is_list:
        msg = f"{field.name!r} has nargs but isn't a list"
        raise TypeError(msg)

    low, high = field.nargs_range
    if low < 0 or (high is not None and high < max(low, 1)):
        msg = f"{field.name!r} has invalid nargs {field.nargs!r}"
        raise TypeError(msg)


def _check_keys(fields: Sequence[Field]) -> None:
    for field in fields:
        if field.short is not None and not _SHORT_KEY.fullmatch(field.short):
            msg = (
                f"{field.name!r} has invalid short {field.short!r} "
                "(expected '-' plus one letter or digit)"
            )
            raise TypeError(msg)
        if field.custom_long is not None and not _LONG_KEY.fullmatch(field.custom_long):
            msg = (
                f"{field.name!r} has invalid long {field.custom_long!r} "
                "(expected '--' plus letters, digits or '-')"
            )
            raise TypeError(msg)

    counts = Counter(key for field in fields for key in field.keys)
    if duplicates := [key for key, count in counts.items() if count > 1]:
        msg = f"option keys used more than once: {', '.join(duplicates)}"
        raise TypeError(msg)


def _check_reserved(fields: Sequence[Field], reserved: Mapping[str, str]) -> None:
    for field in fields:
        for key in field.keys:
            if setting := reserved.get(key):
                msg = (
                    f"{field.name!r} uses {key!r}, which is reserved by {setting} "
                    f"-- free it with parse_args(..., {setting}=...)"
                )
                raise TypeError(msg)


def _check_positional_order(fields: Sequence[Field]) -> None:
    # False (required) sorts before True (optional)
    is_optional = [not field.is_required for field in fields if field.is_pos]

    if is_optional != sorted(is_optional):
        msg = "required positionals must precede optional ones"
        raise TypeError(msg)

    # A variable-count list takes the remaining values, so nothing can follow it;
    # a fixed-count list (nargs=N) can go anywhere
    pos_fields = [field for field in fields if field.is_pos]
    if any(field.is_list and len(set(field.nargs_range)) > 1 for field in pos_fields[:-1]):
        msg = "only the last positional can take a variable number of values (use nargs=N)"
        raise TypeError(msg)
