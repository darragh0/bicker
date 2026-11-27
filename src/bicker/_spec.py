from __future__ import annotations

import re
from collections import Counter
from dataclasses import MISSING, dataclass
from enum import Enum
from inspect import cleandoc
from pathlib import Path
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
)

from bicker._declare import COMMAND_NAMES_ATTR, CommandDeclaration, CommandNames, Declaration
from bicker._style import Styles

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from bicker._style import Style


_SHORT_KEY: Final = re.compile(r"-[A-Za-z0-9]")
_LONG_KEY: Final = re.compile(r"--[A-Za-z0-9][A-Za-z0-9-]*")

_COMMAND_NAME: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")

# Where a class name gets a dash in its command name: `RunTests` -> `run-tests`, `HTTPGet` ->
# `http-get`
_WORD_BOUNDARY: Final = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

# Types built from a value's text, e.g. `int("3")`; bool is supported separately, for flags only
_SCALAR_TYPES: Final = (str, int, float, Path)


# Compared by identity (eq=False), so fields can be dict keys even with a list default
@final
@dataclass(frozen=True, kw_only=True, eq=False)
class Field:
    """A declared argument, with its name and type from the class."""

    name: str
    # The type values are parsed as, e.g. `int` (for `int | None`), `list[str]` or `Literal["a"]`
    typ: object
    decl: Declaration

    @property
    def long_key(self) -> str | None:
        """The custom long key if set, else derived from the name: `dry_run` -> `--dry-run`."""
        if self.decl.custom_long is False:
            return None
        return self.decl.custom_long or f"--{self.name.replace('_', '-')}"

    @property
    def keys(self) -> tuple[str, ...]:
        """An option's keys, short first, e.g. `("-c", "--count")`."""
        return tuple(key for key in (self.decl.short, self.long_key) if key)

    @property
    def label(self) -> str:
        """The key used in messages: the long key, or the short one for a short-only option."""
        return self.keys[-1]

    @property
    def style(self) -> Style:
        if self.is_flag:
            return Styles.FLAG
        return Styles.POS if self.decl.is_pos else Styles.OPT

    @property
    def is_flag(self) -> bool:
        return self.typ is bool

    @property
    def is_required(self) -> bool:
        if self.is_list:
            return self.nargs_range[0] > 0
        return self.decl.default is MISSING

    @property
    def nargs_range(self) -> tuple[int, int | None]:
        """`(min, max)` values for a list; defaults to 1+ without a default, 0+ with one."""
        if isinstance(self.decl.nargs, int):
            return (self.decl.nargs, self.decl.nargs)
        if self.decl.nargs is not None:
            return self.decl.nargs
        return (1 if self.decl.default is MISSING else 0, None)

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
    def converter(self) -> Callable[[str], object] | None:
        """What turns a value's text into its type: `parse=`/`each=`, or a type like `int`."""
        if custom := self.decl.parse or self.decl.each:
            return custom
        typ = self.value_typ
        return typ if isinstance(typ, type) and typ in _SCALAR_TYPES else None

    @property
    def choices(self) -> dict[str, object]:
        """The values of a `Literal` or `Enum` type, by their text; empty for any other type."""
        typ = self.value_typ
        if get_origin(typ) is Literal:
            values: tuple[object, ...] = get_args(typ)
        elif isinstance(typ, type) and issubclass(typ, Enum):
            values = tuple(typ)
        else:
            return {}
        return {as_text(value): value for value in values}

    @property
    def metavar(self) -> str | None:
        """The help placeholder: the custom one if set, else `{a,b}` for choices or `NAME`."""
        if self.is_flag:
            return None
        if self.decl.custom_metavar:
            return self.decl.custom_metavar
        if self.choices:
            return "{" + ",".join(self.choices) + "}"
        return self.name.upper()


@final
@dataclass(frozen=True, kw_only=True, eq=False)
class Spec:
    """A class of declarations, as read by `collect_spec`: the program, or one of its commands."""

    cls: type[object]
    # Set with `@command`; the name defaults to the class name in kebab-case
    name: str
    aliases: tuple[str, ...]
    options: tuple[Field, ...]
    positionals: tuple[Field, ...]
    # The `cmd()` attribute's name, and its commands by name; `None` and empty without one
    command_attr: str | None
    commands: Mapping[str, Spec]
    # False when the `cmd()` annotation includes `None`
    command_required: bool

    def find_command(self, word: str) -> Spec | None:
        """Get the command named or aliased `word`, if any."""
        return next((c for c in self.commands.values() if word in (c.name, *c.aliases)), None)

    @property
    def description(self) -> str | None:
        """The class docstring, without its indentation."""
        return cleandoc(self.cls.__doc__) if self.cls.__doc__ else None


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
    command_required = True
    hints: dict[str, object] = get_type_hints(cls)

    for name, typ in hints.items():
        decl = getattr(cls, name, None)
        if isinstance(decl, Declaration):
            fields.append(_field(name, typ, decl))
        elif not isinstance(decl, CommandDeclaration):
            msg = f"{name!r} must be declared with pos(), opt(), flag() or cmd()"
            raise TypeError(msg)
        elif command_attr:
            msg = f"{cls.__name__} has more than one cmd()"
            raise TypeError(msg)
        else:
            command_attr = name
            command_classes, command_required = _command_classes(name, typ)

    options = tuple(field for field in fields if not field.decl.is_pos)
    positionals = tuple(field for field in fields if field.decl.is_pos)
    _check_keys([*inherited, *options])
    _check_reserved(options, reserved)
    _check_positional_order(positionals)
    if command_attr and positionals:
        msg = f"{cls.__name__} has a cmd(), so it can't have positionals"
        raise TypeError(msg)

    commands: dict[str, Spec] = {}
    taken: set[str] = set()
    for command_cls in command_classes:
        command = collect_spec(command_cls, reserved, [*inherited, *options])
        for word in (command.name, *command.aliases):
            if word in taken:
                msg = f"command name {word!r} used more than once"
                raise TypeError(msg)
            taken.add(word)
        commands[command.name] = command

    name, aliases = _command_names(cls)
    return Spec(
        cls=cls,
        name=name,
        aliases=aliases,
        options=options,
        positionals=positionals,
        command_attr=command_attr,
        commands=commands,
        command_required=command_required,
    )


def _command_names(cls: type[object]) -> tuple[str, tuple[str, ...]]:
    """Get a command class's name and aliases: from `@command`, else its kebab-case name."""
    default = _WORD_BOUNDARY.sub("-", cls.__name__).lower()
    # Read from the class itself, so a subclass doesn't inherit its base's names
    names: object = cls.__dict__.get(COMMAND_NAMES_ATTR)
    if not isinstance(names, CommandNames):
        return default, ()

    for word in (names.name, *names.aliases):
        if word is not None and not _COMMAND_NAME.fullmatch(word):
            msg = f"{cls.__name__} has invalid command name {word!r}"
            raise TypeError(msg)
    return names.name or default, names.aliases


def _field(name: str, typ: object, decl: Declaration) -> Field:
    field = Field(name=name, typ=_parsed_type(typ), decl=decl)
    _check_type(field)
    _check_converter(field)
    _check_nargs(field)
    return field


def _command_classes(name: str, typ: object) -> tuple[tuple[type[object], ...], bool]:
    """Get the classes in a `cmd()` annotation, and whether it's required (no `| None`)."""
    typ = _expand_aliases(typ)
    members: tuple[object, ...] = get_args(typ) if get_origin(typ) is UnionType else (typ,)
    required = NoneType not in members
    members = tuple(m for m in members if m is not NoneType)
    classes = tuple(m for m in members if isinstance(m, type))
    if not classes or len(classes) != len(members):
        msg = f"{name!r} must be annotated with a class or a union of classes"
        raise TypeError(msg)
    return classes, required


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


def as_text(value: object) -> str:
    """Write a value as it's typed: an enum member's name in kebab-case, else `str(value)`."""
    return value.name.lower().replace("_", "-") if isinstance(value, Enum) else str(value)


def _check_type(field: Field) -> None:
    # Literal can't hold floats (PEP 586), and choices are typed as text
    choices = field.choices.values()
    supported = (
        field.converter is not None
        or (field.is_flag and not field.decl.is_pos)
        or (bool(choices) and all(isinstance(value, str | int | Enum) for value in choices))
    )

    if not supported:
        scalars = ", ".join(t.__name__ for t in _SCALAR_TYPES)
        msg = (
            f"{field.name!r} has unsupported type {field.typ!r} (supported: {scalars}, Enum, "
            "Literal of str/int, a list of those, and bool for flags; use parse= for others)"
        )
        raise TypeError(msg)


def _check_converter(field: Field) -> None:
    """Check `parse=`/`each=` fit the field; type checkers catch most misuse, but not all."""
    if field.decl.parse and field.is_list:
        msg = f"{field.name!r} is a list, so convert its items with each= instead of parse="
    elif field.decl.each and not field.is_list:
        msg = f"{field.name!r} isn't a list, so convert it with parse= instead of each="
    elif (field.decl.parse or field.decl.each) and get_origin(field.value_typ) is Literal:
        msg = f"{field.name!r} is a Literal, so its values are matched as typed (no parse=/each=)"
    else:
        return
    raise TypeError(msg)


def _check_nargs(field: Field) -> None:
    if field.decl.nargs is None:
        return
    if not field.is_list:
        msg = f"{field.name!r} has nargs but isn't a list"
        raise TypeError(msg)

    low, high = field.nargs_range
    if low < 0 or (high is not None and high < max(low, 1)):
        msg = f"{field.name!r} has invalid nargs {field.decl.nargs!r}"
        raise TypeError(msg)


def _check_keys(fields: Sequence[Field]) -> None:
    for field in fields:
        if field.decl.short is not None and not _SHORT_KEY.fullmatch(field.decl.short):
            msg = (
                f"{field.name!r} has invalid short {field.decl.short!r} "
                "(expected '-' plus one letter or digit)"
            )
            raise TypeError(msg)
        if isinstance(field.decl.custom_long, str) and not _LONG_KEY.fullmatch(
            field.decl.custom_long
        ):
            msg = (
                f"{field.name!r} has invalid long {field.decl.custom_long!r} "
                "(expected '--' plus letters, digits or '-')"
            )
            raise TypeError(msg)
        if not field.keys:
            msg = f"{field.name!r} has long=False, so it needs a short key"
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
    is_optional = [not field.is_required for field in fields if field.decl.is_pos]

    if is_optional != sorted(is_optional):
        msg = "required positionals must precede optional ones"
        raise TypeError(msg)

    # A variable-count list takes the remaining values, so nothing can follow it;
    # a fixed-count list (nargs=N) can go anywhere
    pos_fields = [field for field in fields if field.decl.is_pos]
    if any(field.is_list and len(set(field.nargs_range)) > 1 for field in pos_fields[:-1]):
        msg = "only the last positional can take a variable number of values (use nargs=N)"
        raise TypeError(msg)
