from __future__ import annotations

import pytest

from poker_rta.capture.window import WindowLookupUnavailable, resolve_title_to_bbox


def test_title_lookup_returns_none_for_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from poker_rta.capture import window as mod

    monkeypatch.setattr(mod, "_platform_list_windows", lambda: [])
    assert resolve_title_to_bbox("NoSuchWindow") is None


def test_title_lookup_raises_when_no_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    from poker_rta.capture import window as mod

    monkeypatch.setattr(mod, "_platform_list_windows", None)
    with pytest.raises(WindowLookupUnavailable):
        resolve_title_to_bbox("Anything")
