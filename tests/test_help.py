from typing import Literal, TypedDict, Unpack

import pytest

from bicker import flag, opt, parse_args, pos


class Args:
    src: str = pos(description="Image to resize")
    files: list[str] = pos([])
    width: int = opt(800, short="-w", metavar="PX", description="Target width")
    fmt: Literal["png", "jpg"] = opt("png")
    verbose: bool = flag(short="-v")


class HelpOptions(TypedDict, total=False):
    description: str
    epilog: str
    examples: list[str]
    use_shorthand_usage: bool


def help_text(
    capsys: pytest.CaptureFixture[str], *argv: str, **options: Unpack[HelpOptions]
) -> str:
    with pytest.raises(SystemExit) as exc:
        _ = parse_args(Args, list(argv), prog="tool", **options)
    assert exc.value.code == 0
    return capsys.readouterr().out


def test_help_lists_everything_aligned(capsys: pytest.CaptureFixture[str]) -> None:
    out = help_text(capsys, "--help", description="Resize images.", examples=["a.png -w 10"])
    assert out == (
        "Usage: tool [-w PX] [--fmt {png,jpg}] [-v] src [files...]\n"
        "\n"
        "Resize images.\n"
        "\n"
        "Positionals:\n"
        "  src                  Image to resize\n"
        "  [files...]\n"
        "\n"
        "Options:\n"
        "  -w, --width PX       Target width\n"
        "      --fmt {png,jpg}\n"
        "  -v, --verbose\n"
        "  -h, --help           Show this message and exit\n"
        "\n"
        "Examples:\n"
        "  tool a.png -w 10\n"
    )


def test_help_shorthand_usage_and_epilog(capsys: pytest.CaptureFixture[str]) -> None:
    out = help_text(capsys, "-h", use_shorthand_usage=True, epilog="See the docs.")
    assert out.startswith("Usage: tool [options] src [files...]\n")
    assert out.endswith("\n\nSee the docs.\n")


def test_help_wins_over_other_errors(capsys: pytest.CaptureFixture[str]) -> None:
    assert help_text(capsys, "--nope", "-h").startswith("Usage: tool")


def test_help_after_double_dash_is_a_positional() -> None:
    assert parse_args(Args, ["a", "--", "--help"]).files == ["--help"]


def test_help_keys_can_be_disabled(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        _ = parse_args(Args, ["-h"], prog="tool", help_keys=())
    assert exc.value.code == 1
    assert "option -h not recognized" in capsys.readouterr().err


class Grouped:
    src: str = pos()
    width: int = opt(800, short="-w", group="Output")
    quiet: bool = flag(short="-q")
    fmt: Literal["png", "jpg"] = opt("png", group="Output")
    retries: int = opt(3, group="Network")


def test_groups_get_their_own_heading_in_order(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        _ = parse_args(Grouped, ["-h"], prog="tool")
    assert capsys.readouterr().out == (
        "Usage: tool [-w WIDTH] [-q] [--fmt {png,jpg}] [--retries RETRIES] src\n"
        "\n"
        "Positionals:\n"
        "  src\n"
        "\n"
        "Options:\n"
        "  -q, --quiet\n"
        "  -h, --help             Show this message and exit\n"
        "\n"
        "Output:\n"
        "  -w, --width WIDTH\n"
        "      --fmt {png,jpg}\n"
        "\n"
        "Network:\n"
        "      --retries RETRIES\n"
    )
