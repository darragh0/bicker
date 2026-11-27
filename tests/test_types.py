import re
from datetime import date
from enum import Enum, auto
from pathlib import Path
from typing import Literal

import pytest

from bicker import opt, parse_args, pos


class Color(Enum):
    RED = auto()
    DARK_BLUE = auto()


def number(text: str) -> int | str:
    return int(text) if text.isdigit() else text.removeprefix("#")


class Args:
    src: Path = pos()
    includes: list[Path] = opt([], short="-I")
    color: Color = opt(Color.RED, short="-c")
    when: date = opt(date(2026, 1, 1), parse=date.fromisoformat)
    days: list[date] = opt([], each=date.fromisoformat)
    num: int | str | None = opt(parse=number)


def parse(*argv: str) -> Args:
    return parse_args(Args, list(argv), prog="tool")


def test_defaults() -> None:
    args = parse("a.txt")
    assert (args.src, args.color, args.when, args.num) == (
        Path("a.txt"),
        Color.RED,
        date(2026, 1, 1),
        None,
    )


def test_paths_enums_and_parse() -> None:
    args = parse(
        "a.txt", "-I", "inc", "-c", "dark-blue", "--when", "2026-11-27", "--days", "2026-01-02"
    )
    assert (args.includes, args.color, args.when, args.days) == (
        [Path("inc")],
        Color.DARK_BLUE,
        date(2026, 11, 27),
        [date(2026, 1, 2)],
    )
    assert parse("a", "--num", "#x").num == "x"


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["a", "-c", "green"], '-c must be one of: "red", "dark-blue"'),
        (["a", "--when", "soon"], 'error: --when expects date, got "soon"'),
        (["a", "--days", "x"], 'error: --days expects date, got "x"'),
    ],
)
def test_errors(argv: list[str], message: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        _ = parse(*argv)
    assert message in capsys.readouterr().err


def bad(text: str) -> int | str:
    raise ValueError(text)


class Union:
    num: int | str | None = opt(parse=bad)


def test_parse_error_for_a_non_class_type(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        _ = parse_args(Union, ["--num", "x"])
    assert 'error: --num expects a valid value, got "x"' in capsys.readouterr().err


def test_help_shows_enum_choices_and_defaults(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        _ = parse("-h")
    out = capsys.readouterr().out
    assert '  -c, --color {red,dark-blue}  [default: "red"]\n' in out
    assert '      --when WHEN              [default: "2026-01-01"]\n' in out


class NoParse:
    when: date = opt(date(2026, 1, 1))


def test_unsupported_type_suggests_parse() -> None:
    with pytest.raises(TypeError, match="use parse= for others"):
        _ = parse_args(NoParse, [])


class WrongParse:
    # Type checkers flag this; ignored to test the runtime backstop
    name: str = opt("a", parse=int)  # type: ignore[arg-type]  # pyright: ignore[reportAssignmentType]


def test_parse_returning_the_wrong_type_is_caught() -> None:
    assert parse_args(WrongParse, []).name == "a"
    with pytest.raises(TypeError, match="'name' is str, but its converter returned int"):
        _ = parse_args(WrongParse, ["--name", "3"])


# Type checkers flag each of these; ignored to test the runtime checks
class ParseOnList:
    days: list[date] = opt([], parse=date.fromisoformat)  # type: ignore[arg-type]  # pyright: ignore[reportAssignmentType, reportUnknownVariableType, reportUnknownArgumentType]


class EachOnScalar:
    day: date = opt(date(2026, 1, 1), each=date.fromisoformat)  # type: ignore[call-overload]  # pyright: ignore[reportArgumentType, reportAssignmentType]


class ParseOnLiteral:
    mode: Literal["a", "b"] = opt("a", parse=str.lower)  # type: ignore[arg-type]  # pyright: ignore[reportAssignmentType]


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        (ParseOnList, "'days' is a list, so convert its items with each= instead of parse="),
        (EachOnScalar, "'day' isn't a list, so convert it with parse= instead of each="),
        (ParseOnLiteral, "'mode' is a Literal, so its values are matched as typed"),
    ],
)
def test_converter_misuse(spec: type[object], message: str) -> None:
    with pytest.raises(TypeError, match=re.escape(message)):
        _ = parse_args(spec, [])
