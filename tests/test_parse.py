from typing import Literal

import pytest

from bicker import flag, opt, parse_args, pos


class Args:
    src: str = pos()
    dst: str = pos("out.png")
    width: int = opt(800, "-w")
    scale: float = opt(1.0)
    fmt: Literal["png", "jpg"] = opt("png", "-f")
    tags: list[str] = opt([], "-t")
    verbose: bool = flag("-v")
    strict: bool = flag()


def parse(*argv: str) -> Args:
    return parse_args(Args, list(argv), prog="tool")


def test_defaults() -> None:
    args = parse("a.png")
    assert vars(args) == {
        "src": "a.png",
        "dst": "out.png",
        "width": 800,
        "scale": 1.0,
        "fmt": "png",
        "tags": [],
        "verbose": False,
        "strict": False,
    }


def test_all_option_spellings() -> None:
    args = parse("a.png", "b.jpg", "-w", "400", "--scale=0.5", "-fjpg", "-v", "--strict")
    assert (args.dst, args.width, args.scale, args.fmt) == ("b.jpg", 400, 0.5, "jpg")
    assert args.verbose
    assert args.strict


def test_options_after_positionals_and_double_dash() -> None:
    args = parse("-v", "a.png", "--", "--weird-name")
    assert (args.src, args.dst, args.verbose) == ("a.png", "--weird-name", True)


def test_repeated_option_collects_values() -> None:
    assert parse("a", "-t", "x", "--tags", "y").tags == ["x", "y"]


def test_list_default_is_not_shared() -> None:
    parse("a").tags.append("leak")
    assert parse("a").tags == []


class Renamed:
    count: int = opt(1, "-c", long="--num")


def test_custom_long_key_replaces_the_default() -> None:
    assert vars(parse_args(Renamed, ["--num", "3"])) == {"count": 3}


type Mode = Literal["fast", "slow"]
type Modes = list[Mode]


class Aliased:
    mode: Mode = opt("fast")
    modes: Modes = opt([])


def test_type_aliases_are_expanded() -> None:
    args = parse_args(Aliased, ["--mode", "slow", "--modes", "fast"])
    assert (args.mode, args.modes) == ("slow", ["fast"])


class Points:
    point: list[int] = pos(nargs=2)
    name: str = pos()
    files: list[str] = pos(nargs=(0, 2))


def test_nargs_positionals_are_consumed_in_order() -> None:
    args = parse_args(Points, ["1", "2", "bob", "a"])
    assert (args.point, args.name, args.files) == ([1, 2], "bob", ["a"])


class Counts:
    tags: list[str] = opt([], "-t", nargs=(1, 3))
    ids: list[int] = opt([], nargs=(0, 1))
    names: list[str] = opt([], nargs=(2, None))


@pytest.mark.parametrize(
    ("spec", "argv", "message"),
    [
        (Args, [], "missing positional: src"),
        (Args, ["a", "b", "c"], 'unexpected positional: "c"'),
        (Args, ["a", "-w", "x"], 'error: -w expects int, got "x"'),
        (Args, ["a", "-f", "gif"], '-f must be one of: "png", "jpg"'),
        (Args, ["a", "--nope"], "option --nope not recognized"),
        (Args, ["a", "--verbose=1"], "option --verbose must not have an argument"),
        (Args, ["a", "--s"], "option --s is ambiguous: --scale, --strict"),
        (Args, ["a", "--=x"], "option -- not recognized"),
        (Renamed, ["--count", "3"], "option --count not recognized"),
        (Points, ["1"], "point expects exactly 2 values, got 1"),
        (Points, ["1", "2", "bob", "a", "b", "c"], 'unexpected positional: "c"'),
        (Aliased, ["--mode", "x"], '--mode must be one of: "fast", "slow"'),
        (Counts, [], "--tags expects 1 to 3 values, got 0"),
        (Counts, ["-t", "a", "--ids", "1", "--ids", "2"], "--ids expects at most 1 value, got 2"),
        (Counts, ["-t", "a", "--names", "x"], "--names expects at least 2 values, got 1"),
    ],
)
def test_user_errors(
    spec: type[object], argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        _ = parse_args(spec, argv, prog="tool")
    err = capsys.readouterr().err
    assert exc.value.code == 1
    assert message in err
    assert "Usage: tool" in err


def test_usage_on_error_can_be_disabled(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        _ = parse_args(Args, [], prog="tool", usage_on_error=False)
    assert "Usage" not in capsys.readouterr().err
