"""Help and errors are colored on a terminal, without changing the text itself."""

import io
import re
import sys
from typing import override

import pytest

from bicker import cmd, flag, opt, parse_args, pos

ANSI_CODE = re.compile(r"\x1b\[[0-9;]*m")


class Args:
    src: str = pos(description="Image to resize")
    files: list[str] = pos([])
    width: int = opt(800, short="-w", metavar="PX")
    verbose: bool = flag(short="-v")


class Terminal(io.StringIO):
    @override
    def isatty(self) -> bool:
        return True


def help_output(monkeypatch: pytest.MonkeyPatch, *, isatty: bool) -> str:
    stdout = Terminal() if isatty else io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)
    with pytest.raises(SystemExit):
        _ = parse_args(Args, ["-h"], prog="tool")
    return stdout.getvalue()


def test_help_is_colored_on_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    colored = help_output(monkeypatch, isatty=True)
    assert ANSI_CODE.search(colored)
    assert ANSI_CODE.sub("", colored) == help_output(monkeypatch, isatty=False)


def test_no_color_disables_color(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    assert not ANSI_CODE.search(help_output(monkeypatch, isatty=True))


def test_errors_are_colored_on_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    stderr = Terminal()
    monkeypatch.setattr(sys, "stderr", stderr)
    with pytest.raises(SystemExit):
        _ = parse_args(Args, ["a", "-w", "x"], prog="tool")
    assert ANSI_CODE.sub("", stderr.getvalue()).startswith('error: -w expects int, got "x"')
    assert ANSI_CODE.search(stderr.getvalue())


class Build:
    release: bool = flag(short="-r")


class WithCommand:
    verbose: bool = flag(short="-v")
    command: Build = cmd()


def test_examples_color_commands_and_their_options(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    stdout = Terminal()
    monkeypatch.setattr(sys, "stdout", stdout)
    with pytest.raises(SystemExit):
        _ = parse_args(WithCommand, ["-h"], prog="tool", examples=["-v build -r x"])
    example = stdout.getvalue().rstrip("\n").rpartition("\n")[2]
    assert ANSI_CODE.sub("", example) == "  tool -v build -r x"
    # Every word but the plain value "x" is colored
    assert re.findall(r"\x1b\[(?!0m)[0-9;]+m([^\x1b]+)", example) == ["tool", "-v", "build", "-r"]
