import pytest

from bicker import flag, opt, parse_args


class Args:
    level: int = opt(1, short="-O", long=False, description="Optimisation level")
    name: str = opt(required=True, short="-n", long=False)
    debug: bool = flag(short="-g", long=False, description="Add debug info")


class NoKeys:
    x: int = opt(1, long=False)


def test_short_only_options_and_flags_are_parsed() -> None:
    args = parse_args(Args, ["-O2", "-n", "app", "-g"])
    assert (args.level, args.name, args.debug) == (2, "app", True)


def test_short_only_option_has_no_long_key(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        _ = parse_args(Args, ["-n", "app", "--level", "2"], prog="tool")
    assert "error: option --level not recognized\n" in capsys.readouterr().err


def test_messages_use_the_short_key(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        _ = parse_args(Args, [], prog="tool")
    assert capsys.readouterr().err.startswith("error: missing required option: -n\n")


def test_help_lists_the_short_key_only(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        _ = parse_args(Args, ["-h"], prog="tool")
    assert capsys.readouterr().out == (
        "Usage: tool [-O LEVEL] -n NAME [-g]\n"
        "\n"
        "Options:\n"
        "  -O LEVEL    Optimisation level\n"
        "  -n NAME\n"
        "  -g          Add debug info\n"
        "  -h, --help  Show this message and exit\n"
    )


def test_short_only_needs_a_short_key() -> None:
    with pytest.raises(TypeError, match="'x' has long=False, so it needs a short key"):
        _ = parse_args(NoKeys, [])
