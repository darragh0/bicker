import pytest

from bicker import flag, parse_args, pos


class Args:
    src: str = pos()
    verbose: bool = flag(short="-v")


class VersionClash:
    show_version: bool = flag(long="--version")


def test_version_prints_prog_and_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        _ = parse_args(Args, ["--version"], prog="tool", version="1.2.0")
    assert exc.value.code == 0
    assert capsys.readouterr().out == "tool 1.2.0\n"


def test_short_version_key_is_opt_in(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        _ = parse_args(Args, ["-V"], prog="tool", version="1.2.0", version_keys=("-V",))
    assert exc.value.code == 0
    assert capsys.readouterr().out == "tool 1.2.0\n"

    with pytest.raises(SystemExit) as exc:
        _ = parse_args(Args, ["-V"], prog="tool", version="1.2.0")
    assert exc.value.code == 1


def test_no_version_option_without_a_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        _ = parse_args(Args, ["a", "--version"], prog="tool")
    assert exc.value.code == 1
    assert "option --version not recognized" in capsys.readouterr().err


def test_help_lists_the_version_option(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        _ = parse_args(Args, ["-h"], prog="tool", version="1.2.0")
    assert capsys.readouterr().out.endswith(
        "  -h, --help     Show this message and exit\n      --version  Show the version and exit\n"
    )


def test_version_keys_are_reserved_only_with_a_version() -> None:
    assert not parse_args(VersionClash, []).show_version
    with pytest.raises(TypeError, match="reserved by version_keys"):
        _ = parse_args(VersionClash, [], version="1.2.0")
