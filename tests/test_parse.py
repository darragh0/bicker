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


class Points:
    point: list[int] = pos(nargs=2)
    name: str = pos()
    files: list[str] = pos(nargs=(0, 2))


def test_nargs_positionals_are_consumed_in_order() -> None:
    args = parse_args(Points, ["1", "2", "bob", "a"])
    assert (args.point, args.name, args.files) == ([1, 2], "bob", ["a"])


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
        (Points, ["1"], "point expects exactly 2 values, got 1"),
        (Points, ["1", "2", "bob", "a", "b", "c"], 'unexpected positional: "c"'),
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
