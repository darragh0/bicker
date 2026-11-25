"""Mistakes in the args class itself raise `TypeError` before anything is parsed."""

import re

import pytest

from bicker import flag, opt, parse_args, pos


class NotDeclared:
    x: int = 3


class Unsupported:
    x: dict[str, int] = opt({})


class BadShort:
    x: int = opt(1, "x")


class BadLong:
    x: int = opt(1, long="x")


class DuplicateShort:
    a: int = opt(1, "-a")
    b: int = opt(2, "-a")


class DuplicateLong:
    a: int = opt(1, long="--b")
    b: int = opt(2)


class HelpClash:
    verbose: bool = flag("-h")


class OptionalBeforeRequired:
    a: str = pos("default")
    b: str = pos()


class VariableListNotLast:
    files: list[str] = pos()
    out: str = pos()


class NargsOnNonList:
    x: int = pos(nargs=2)


class InvalidNargs:
    x: list[int] = pos(nargs=(3, 1))


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        (NotDeclared, "must be declared with pos(), opt() or flag()"),
        (Unsupported, "has unsupported type"),
        (BadShort, "has invalid short 'x'"),
        (BadLong, "has invalid long 'x'"),
        (DuplicateShort, "option keys used more than once: -a"),
        (DuplicateLong, "option keys used more than once: --b"),
        (HelpClash, "reserved by help_keys"),
        (OptionalBeforeRequired, "required positionals must precede optional ones"),
        (VariableListNotLast, "only the last positional can take a variable number"),
        (NargsOnNonList, "has nargs but isn't a list"),
        (InvalidNargs, "has invalid nargs (3, 1)"),
    ],
)
def test_declaration_errors(spec: type[object], message: str) -> None:
    with pytest.raises(TypeError, match=re.escape(message)):
        _ = parse_args(spec, [])
