import pytest


@pytest.fixture(autouse=True)
def terminal_width(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fix the width help wraps at, whatever terminal the tests run in."""
    monkeypatch.setenv("COLUMNS", "100")
