"""The public declaration functions: `pos()`, `opt()`, `flag()`, `cmd()` and `@command`."""

from __future__ import annotations

from dataclasses import MISSING, dataclass
from typing import TYPE_CHECKING, Final, Literal, TypedDict, Unpack, cast, final, overload

if TYPE_CHECKING:
    from collections.abc import Callable

# How many values a list field takes: exactly `n`, or `(min, max)` with `None` for no max
type Nargs = int | tuple[int, int | None]


@final
@dataclass(frozen=True, kw_only=True)
class Declaration:
    """What `pos()`, `opt()` and `flag()` return; `collect_spec` adds the name and type."""

    # MISSING for a required argument
    default: object
    short: str | None = None
    # False for a short-only option
    custom_long: str | Literal[False] | None = None
    is_pos: bool = False
    custom_metavar: str | None = None
    description: str | None = None
    nargs: Nargs | None = None
    # `parse=` converts a single value, `each=` a list's items
    parse: Callable[[str], object] | None = None
    each: Callable[[str], object] | None = None
    # The help heading an option is listed under
    group: str = "Options"


class _PosOptions(TypedDict, total=False):
    description: str | None
    nargs: Nargs | None


class _OptOptions(TypedDict, total=False):
    short: str | None
    long: str | Literal[False] | None
    description: str | None
    metavar: str | None
    nargs: Nargs | None
    group: str


@final
class CommandDeclaration:
    """What `cmd()` returns; the commands are read from the field's annotation."""


@final
@dataclass(frozen=True)
class CommandNames:
    """What `@command` stores on a class."""

    name: str | None
    aliases: tuple[str, ...]


COMMAND_NAMES_ATTR: Final = "__bicker_command__"


# Overloads tie `T` to the field's annotation: from `parse=`, `each=` or the default, else
# inferred (T only in the return type is intentional). Shared keywords come from a TypedDict.
@overload
def pos[T](**options: Unpack[_PosOptions]) -> T: ...  # type: ignore[type-var]  # pyright: ignore[reportInvalidTypeVarUse]
@overload
def pos[T](default: T, **options: Unpack[_PosOptions]) -> T: ...
@overload
def pos[T](*, parse: Callable[[str], T], **options: Unpack[_PosOptions]) -> T: ...
@overload
def pos[T](default: T, *, parse: Callable[[str], T], **options: Unpack[_PosOptions]) -> T: ...
@overload
def pos[V](*, each: Callable[[str], V], **options: Unpack[_PosOptions]) -> list[V]: ...
@overload
def pos[V](
    default: list[V], *, each: Callable[[str], V], **options: Unpack[_PosOptions]
) -> list[V]: ...
def pos(
    default: object = MISSING,
    *,
    description: str | None = None,
    nargs: Nargs | None = None,
    parse: Callable[[str], object] | None = None,
    each: Callable[[str], object] | None = None,
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
        parse: Turns the value's text into the field's type, for a type bicker doesn't support
            itself, e.g. `date.fromisoformat`. It should raise `ValueError` for an invalid value.
        each: Like `parse`, but for a `list[T]` field: turns each item's text into a `T`.

    Returns:
        A placeholder that `parse_args` replaces with the parsed value.
    """
    return Declaration(
        default=default,
        is_pos=True,
        description=description,
        nargs=nargs,
        parse=parse,
        each=each,
    )


@overload
def opt[T](*, required: Literal[True], **options: Unpack[_OptOptions]) -> T: ...  # type: ignore[type-var]  # pyright: ignore[reportInvalidTypeVarUse]
@overload
def opt[T](default: T, **options: Unpack[_OptOptions]) -> T: ...
@overload
def opt[T](**options: Unpack[_OptOptions]) -> T | None: ...
@overload
def opt[T](
    *, required: Literal[True], parse: Callable[[str], T], **options: Unpack[_OptOptions]
) -> T: ...
@overload
def opt[T](default: T, *, parse: Callable[[str], T], **options: Unpack[_OptOptions]) -> T: ...
@overload
def opt[T](*, parse: Callable[[str], T], **options: Unpack[_OptOptions]) -> T | None: ...
@overload
def opt[V](
    *, required: Literal[True], each: Callable[[str], V], **options: Unpack[_OptOptions]
) -> list[V]: ...
@overload
def opt[V](
    default: list[V], *, each: Callable[[str], V], **options: Unpack[_OptOptions]
) -> list[V]: ...
@overload
def opt[V](*, each: Callable[[str], V], **options: Unpack[_OptOptions]) -> list[V] | None: ...
def opt(
    default: object = None,
    *,
    required: bool = False,
    short: str | None = None,
    long: str | Literal[False] | None = None,
    description: str | None = None,
    metavar: str | None = None,
    nargs: Nargs | None = None,
    group: str = "Options",
    parse: Callable[[str], object] | None = None,
    each: Callable[[str], object] | None = None,
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
            `dry_run`. Pass `False` for a short-only option.
        description: The help text for this option.
        metavar: The value's placeholder in help. Defaults to `{a,b}` for a `Literal`, and
            the field name in uppercase otherwise.
        nargs: How many times a `list[T]` option can be given: exactly `n`, or `(min, max)`
            with `None` for no max. Defaults to any number, or at least 1 when `required`.
        group: The help heading to list this option under.
        parse: Turns the value's text into the field's type, for a type bicker doesn't support
            itself, e.g. `date.fromisoformat`. It should raise `ValueError` for an invalid value.
        each: Like `parse`, but for a `list[T]` field: turns each item's text into a `T`.

    Returns:
        A placeholder that `parse_args` replaces with the parsed value.
    """
    return Declaration(
        default=MISSING if required else default,
        short=short,
        custom_long=long,
        custom_metavar=metavar,
        description=description,
        nargs=nargs,
        parse=parse,
        each=each,
        group=group,
    )


def flag(
    *,
    default: bool = False,
    short: str | None = None,
    long: str | Literal[False] | None = None,
    description: str | None = None,
    group: str = "Options",
) -> bool:
    """Declare a flag: a `bool` option without a value, which sets it to `True`.

    Args:
        default: The value when the flag isn't given. With `True`, the flag also gets a
            `--no-` key to turn it off, e.g. `--no-color` for `color`.
        short: A short key like `-v`: a dash plus one letter or digit.
        long: A long key like `--verbose`. Defaults to the field name, e.g. `--dry-run` for
            `dry_run`. Pass `False` for a short-only flag.
        description: The help text for this flag.
        group: The help heading to list this flag under.

    Returns:
        A placeholder that `parse_args` replaces with the parsed value.
    """
    return opt(
        default=default,
        short=short,
        long=long,
        description=description,
        group=group,
    )


def cmd[T]() -> T:  # type: ignore[type-var]  # pyright: ignore[reportInvalidTypeVarUse]
    """Declare the command, annotated with one class per command, e.g. `command: Build | Test`.

    Each class declares its command's arguments, like the class passed to `parse_args`, and
    its docstring is the command's help text. A command's name is its class name in kebab-case,
    e.g. `run-tests` for `RunTests`, unless set with `@command`. Options declared next to
    `cmd()` can be given before or after the command. A class with a command can't have
    positionals. Add `| None` to the annotation to make the command optional.

    Returns:
        A placeholder that `parse_args` replaces with an instance of the given command's class.
    """
    return cast("T", CommandDeclaration())


def command[C: type[object]](
    name: str | None = None,
    *,
    aliases: list[str] | tuple[str, ...] = (),
) -> Callable[[C], C]:
    """Set a command class's name and aliases, as a class decorator.

    Args:
        name: The command's name. Defaults to the class name in kebab-case.
        aliases: Other names the command can be given as, e.g. `("l",)`.

    Returns:
        A decorator that returns the class unchanged, apart from its command names.

    Example:
        ```python
        @command("ls", aliases=("l",))
        class ListFiles: ...
        ```
    """

    def decorate(cls: C) -> C:
        setattr(cls, COMMAND_NAMES_ATTR, CommandNames(name, tuple(aliases)))
        return cls

    return decorate
