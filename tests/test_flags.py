import re

import pytest

from bicker import flag, opt, parse_args


class Args:
    color: bool = flag(default=True, short="-c", description="Color output")
    json: bool = flag(exclusive="format")
    yaml: bool = flag(exclusive="format")
    out: str | None = opt(exclusive="format")
    verbose: bool = flag(short="-v")


def parse(*argv: str) -> Args:
    return parse_args(Args, list(argv), prog="tool")


def test_negatable_flag() -> None:
    assert parse().color
    assert not parse("--no-color").color
    assert parse("--no-color", "--color").color  # The last one wins


def test_exclusive_options_alone_are_fine() -> None:
    assert parse("--json").json
    assert parse("--out", "x").out == "x"


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--json", "--yaml"], "error: --json, --yaml can't be used together\n"),
        (
            ["--yaml", "--out", "x", "--json"],
            "error: --json, --yaml, --out can't be used together\n",
        ),
    ],
)
def test_exclusive_options_together(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        _ = parse(*argv)
    assert capsys.readouterr().err.startswith(message)


def test_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        _ = parse("-h")
    assert capsys.readouterr().out == (
        "Usage: tool [-c] [--json | --yaml | --out OUT] [-v]\n"
        "\n"
        "Options:\n"
        "  -c, --[no-]color  Color output\n"
        "      --json\n"
        "      --yaml\n"
        "      --out OUT\n"
        "  -v, --verbose\n"
        "  -h, --help        Show this message and exit\n"
    )


class OwnNegation:
    color: bool = flag(default=True)
    no_color: bool = flag()


class ShortOnlyTrue:
    color: bool = flag(default=True, short="-c", long=False)


class Lonely:
    json: bool = flag(exclusive="format")


class RequiredExclusive:
    name: str = opt(required=True, exclusive="who")
    anon: bool = flag(exclusive="who")


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        (OwnNegation, "option key --no-color is used by 'color' (to turn it off) and 'no_color'"),
        (ShortOnlyTrue, "'color' defaults to True, so it needs a long key for its --no- key"),
        (Lonely, "'json' is the only option with exclusive='format'"),
        (RequiredExclusive, "'name' is required, so it can't be exclusive with other options"),
    ],
)
def test_declaration_errors(spec: type[object], message: str) -> None:
    with pytest.raises(TypeError, match=re.escape(message)):
        _ = parse_args(spec, [])
