import re

import pytest

from bicker import flag, parse_args


class Args:
    color: bool = flag(default=True, short="-c", description="Color output")
    verbose: bool = flag(short="-v")


def parse(*argv: str) -> Args:
    return parse_args(Args, list(argv), prog="tool")


def test_negatable_flag() -> None:
    assert parse().color
    assert not parse("--no-color").color
    assert parse("--no-color", "--color").color  # The last one wins


def test_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        _ = parse("-h")
    assert capsys.readouterr().out == (
        "Usage: tool [-c] [-v]\n"
        "\n"
        "Options:\n"
        "  -c, --[no-]color  Color output\n"
        "  -v, --verbose\n"
        "  -h, --help        Show this message and exit\n"
    )


class OwnNegation:
    color: bool = flag(default=True)
    no_color: bool = flag()


class ShortOnlyTrue:
    color: bool = flag(default=True, short="-c", long=False)


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        (OwnNegation, "option key --no-color is used by 'color' (to turn it off) and 'no_color'"),
        (ShortOnlyTrue, "'color' defaults to True, so it needs a long key for its --no- key"),
    ],
)
def test_declaration_errors(spec: type[object], message: str) -> None:
    with pytest.raises(TypeError, match=re.escape(message)):
        _ = parse_args(spec, [])
