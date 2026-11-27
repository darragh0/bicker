import re

import pytest

from bicker import cmd, flag, opt, parse_args, pos


class Add:
    """Add a remote.

    The name must be unique.
    """

    name: str = pos(description="Remote name")


class Remote:
    """Manage remotes."""

    show_urls: bool = flag(short="-u")
    action: Add = cmd()


class Build:
    """Build the project."""

    release: bool = flag(short="-r", description="Optimise the build")


class RunTests:
    pattern: str | None = pos(None)


type Command = Build | RunTests | Remote


class Args:
    verbose: bool = flag(short="-v", description="Print more")
    jobs: int = opt(1, short="-j")
    command: Command = cmd()


def parse(*argv: str) -> Args:
    return parse_args(Args, list(argv), prog="tool")


def test_command_is_parsed_into_its_class() -> None:
    args = parse("build", "-r")
    assert isinstance(args.command, Build)
    assert args.command.release
    assert not args.verbose


def test_global_options_go_before_or_after_the_command() -> None:
    args = parse("-v", "run-tests", "-j", "2", "unit")
    assert isinstance(args.command, RunTests)
    assert (args.verbose, args.jobs, args.command.pattern) == (True, 2, "unit")


def test_nested_commands() -> None:
    args = parse("remote", "-u", "add", "origin", "-v")
    assert isinstance(args.command, Remote)
    assert isinstance(args.command.action, Add)
    assert (args.verbose, args.command.show_urls, args.command.action.name) == (
        True,
        True,
        "origin",
    )


def test_command_after_double_dash() -> None:
    args = parse("--", "run-tests", "-x")
    assert isinstance(args.command, RunTests)
    assert args.command.pattern == "-x"


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], "missing command (one of: build, run-tests, remote)"),
        (["-v"], "missing command (one of: build, run-tests, remote)"),
        (["deploy"], 'unknown command "deploy" (one of: build, run-tests, remote)'),
        (["-r", "build"], "option -r not recognized"),
        (["remote"], "missing command (one of: add)"),
        (["build", "x"], 'unexpected positional: "x"'),
    ],
)
def test_command_errors(argv: list[str], message: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        _ = parse(*argv)
    assert exc.value.code == 1
    assert f"error: {message}\n" in capsys.readouterr().err


def test_usage_after_a_command_error_is_the_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        _ = parse("remote", "-u")
    assert capsys.readouterr().err.endswith("Usage: tool remote [-u] action\n")


def help_text(capsys: pytest.CaptureFixture[str], *argv: str) -> str:
    with pytest.raises(SystemExit) as exc:
        _ = parse(*argv)
    assert exc.value.code == 0
    return capsys.readouterr().out


def test_help_lists_commands(capsys: pytest.CaptureFixture[str]) -> None:
    assert help_text(capsys, "-h") == (
        "Usage: tool [-v] [-j JOBS] command\n"
        "\n"
        "Commands:\n"
        "  build            Build the project\n"
        "  run-tests\n"
        "  remote           Manage remotes\n"
        "\n"
        "Options:\n"
        "  -v, --verbose    Print more\n"
        "  -j, --jobs JOBS\n"
        "  -h, --help       Show this message and exit\n"
    )


def test_command_help_shows_its_docstring_and_global_options(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert help_text(capsys, "build", "-h") == (
        "Usage: tool build [-r]\n"
        "\n"
        "Build the project.\n"
        "\n"
        "Options:\n"
        "  -r, --release    Optimise the build\n"
        "  -h, --help       Show this message and exit\n"
        "\n"
        "Global options:\n"
        "  -v, --verbose    Print more\n"
        "  -j, --jobs JOBS\n"
    )


def test_nested_command_help(capsys: pytest.CaptureFixture[str]) -> None:
    out = help_text(capsys, "-v", "remote", "add", "--help")
    assert out.startswith(
        "Usage: tool remote add name\n\nAdd a remote.\n\nThe name must be unique.\n"
    )
    assert "Global options:\n  -v, --verbose" in out
    assert "  -u, --show-urls\n" in out


def test_help_before_the_command_is_the_programs(capsys: pytest.CaptureFixture[str]) -> None:
    assert "Commands:\n" in help_text(capsys, "-h", "build")


class WithPositional:
    src: str = pos()
    command: Build = cmd()


class TwoCommands:
    first: Build = cmd()
    second: RunTests = cmd()


class NotAClass:
    command: Build | int | None = cmd()


class Clash:
    release: bool = flag(short="-r")
    command: Build = cmd()


class Build2:
    pass


Build2.__name__ = "Build"


class SameName:
    command: Build | Build2 = cmd()


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        (WithPositional, "WithPositional has a cmd(), so it can't have positionals"),
        (TwoCommands, "TwoCommands has more than one cmd()"),
        (NotAClass, "'command' must be annotated with a class or a union of classes"),
        (Clash, "option keys used more than once: -r, --release"),
        (SameName, "command name 'build' used more than once"),
    ],
)
def test_declaration_errors(spec: type[object], message: str) -> None:
    with pytest.raises(TypeError, match=re.escape(message)):
        _ = parse_args(spec, [])
