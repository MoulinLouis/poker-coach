"""State parity: CV path vs frontend path.

Verifies that driving ``EngineSession`` with synthesized ``FrameObservation``s
produces the same engine state as replaying the scripted hand directly via the
backend engine API endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def _normalize(s: dict[str, Any]) -> dict[str, Any]:
    """Strip fields that legitimately differ between paths.

    * ``hand_id``    — random UUID, differs every run.
    * ``villain_hole`` — CV path cannot observe villain cards.
    """
    out = dict(s)
    out.pop("hand_id", None)
    out.pop("villain_hole", None)
    return out


async def test_cv_state_matches_frontend_state(api_client: TestClient) -> None:
    from parity.conftest import run_cv_path, run_frontend_path

    frontend_state = run_frontend_path(api_client)
    cv_state = await run_cv_path(api_client)

    assert _normalize(frontend_state) == _normalize(cv_state)
