import pytest

from bicker import flag, opt, parse_args, pos


class Args:
    src: str = pos()
    name: str = opt(required=True, short="-n")
    tags: list[str] = opt(required=True, short="-t")
    verbose: bool = flag(short="-v")


def test_required_options_are_parsed() -> None:
    args = parse_args(Args, ["a", "-n", "bob", "-t", "x", "-t", "y"])
    assert (args.name, args.tags) == ("bob", ["x", "y"])


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["a", "-t", "x"], "error: missing required option: --name\n"),
        (["a"], "error: missing required options: --name, --tags\n"),
    ],
)
def test_missing_required_options(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        _ = parse_args(Args, argv, prog="tool")
    assert exc.value.code == 1
    assert capsys.readouterr().err.startswith(message)


@pytest.mark.parametrize(
    ("shorthand", "usage"),
    [
        (False, "Usage: tool -n NAME -t TAGS... [-v] src\n"),
        (True, "Usage: tool [options] -n NAME -t TAGS... src\n"),
    ],
)
def test_usage_shows_required_options_without_brackets(
    shorthand: bool,  # noqa: FBT001
    usage: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        _ = parse_args(Args, ["-h"], prog="tool", use_shorthand_usage=shorthand)
    assert exc.value.code == 0
    assert capsys.readouterr().out.startswith(usage)
