# Poker RTA Research Demo — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a polyvalent, config-driven visual recognition tool that captures a poker client's UI, reconstructs the game state, queries the existing `poker_coach` backend, and displays advice in a real-time overlay — operated strictly in sandboxed environments (friend's school-project app, an included HTML mock, or play-money tables) for a security research paper on RTA attack surfaces and behavioral detection.

**Architecture:**
A new top-level package `rta/` at repo root, independent from `backend/` but consuming its HTTP API. Pipeline is `mss` screen capture → OpenCV ROI crops → template-matched card classification + EasyOCR number parsing → frame-delta state tracker → `GameState` builder → `httpx` client to `/api/decisions` + SSE stream → PyQt6 transparent overlay. All site-specific configuration lives in a Pydantic-validated `Platform Profile` YAML (ROI coordinates, card templates, button templates, OCR preprocessing). A calibration GUI lets the user click regions on a fresh screenshot to generate a new profile in ~10 minutes, proving polyvalence by swapping profiles between the mock HTML demo and the friend's app without code changes. The paper component produces: threat-model document, attack-surface matrix, and behavioral-detection analysis scripts (timing entropy + GTO-convergence) that demonstrate why purely technical detection fails against L1 capture + human-in-the-loop.

**Scope guardrails:**
- **Never** includes input injection (L5) — the user clicks themselves.
- **Never** runs against real-money tables. Demos use the HTML mock, the friend's app, or PokerStars play money only.
- **Never** performs memory reads, DLL injection, or MITM of the client traffic. Only external screen capture.

**Tech Stack:**
- Python 3.12 (match backend), uv-managed
- `mss` (screen capture), `opencv-python` (image ops + template matching), `Pillow` (fixture synthesis)
- `easyocr` (primary OCR)
- `pydantic` 2.9+ (profile schema, reusing backend models via `httpx`-marshalled JSON)
- `httpx` (coach HTTP client, sync + async)
- `httpx-sse` (SSE stream consumption)
- `PyQt6` (overlay + calibration UI)
- `pytest` + `pytest-asyncio` + `hypothesis` (tests)
- `ruff`, `mypy --strict` (match backend lint config)

---

## Pre-flight

Read these before starting:

- `backend/src/poker_coach/engine/models.py` — `GameState`, `Action`, `LegalAction` (the contract we serialize into).
- `backend/src/poker_coach/api/schemas.py` — `CreateDecisionRequest`, `CreateSessionRequest`, `CreateHandRequest`, decision status enum.
- `backend/src/poker_coach/api/routes/decisions.py` — how decisions are created, what fields must be set.
- `backend/src/poker_coach/api/routes/stream.py` — SSE event shape (`reasoning_delta`, `reasoning_complete`, `tool_call_complete`, `usage_complete`).
- `backend/src/poker_coach/api/routes/sessions.py` + `hands.py` — session/hand bootstrap endpoints.
- `backend/pyproject.toml` — ruff/mypy config we mirror.
- `CLAUDE.md` gotchas #3 (villain holes must never leak — trivial for us since CV cannot see them), #4 (`model_dump(mode="json")` for frozenset round-trip), #5 (lazy decision lifecycle: POST does not fire oracle, GET stream does).
- Existing plan format reference: `docs/plans/2026-04-18-action-bar-pro-redesign.md`.

Run the backend test baseline once to confirm nothing is broken before we add a sibling package:

```sh
cd backend && uv run pytest
cd ..
```

Expected: all green.

---

## Phase 0 — Package Scaffolding

### Task 0.1: Create `rta/` package skeleton

**Files:**
- Create: `rta/pyproject.toml`
- Create: `rta/README.md`
- Create: `rta/src/poker_rta/__init__.py`
- Create: `rta/src/poker_rta/py.typed`
- Create: `rta/tests/__init__.py`
- Create: `rta/tests/conftest.py`
- Create: `rta/.gitignore`

**Step 1: Write `rta/pyproject.toml`**

```toml
[project]
name = "poker_rta"
version = "0.0.0"
description = "Research-grade poker RTA demo — visual recognition coach harness"
readme = "README.md"
requires-python = ">=3.12,<3.13"
dependencies = [
    "pydantic>=2.9",
    "pyyaml>=6.0",
    "httpx>=0.27",
    "httpx-sse>=0.4",
    "mss>=9.0",
    "opencv-python>=4.10",
    "numpy>=2.0",
    "Pillow>=10.4",
    "easyocr>=1.7",
    "PyQt6>=6.7",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "hypothesis>=6.115",
    "ruff>=0.8",
    "mypy>=1.13",
    "types-PyYAML>=6.0",
    "respx>=0.21",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/poker_rta"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP", "SIM", "RUF"]

[tool.mypy]
python_version = "3.12"
strict = true
files = ["src"]

[[tool.mypy.overrides]]
module = ["mss", "mss.*", "cv2", "easyocr", "PyQt6", "PyQt6.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

**Step 2: Write `rta/README.md`**

```markdown
# poker_rta

Research-grade visual recognition harness for the poker coach. Captures a poker client's UI via screen capture, reconstructs game state via OpenCV + EasyOCR, queries the local `poker_coach` backend, and displays advice in a transparent overlay.

**Use only on the bundled HTML mock, the friend's school project app, or PokerStars play money.** Never against real-money tables — RTA is a ToS violation everywhere and regulated-market fraud in several jurisdictions.

## Run

```sh
cd rta && uv sync
uv run poker_rta run --profile profiles/mock_html.yaml --coach-url http://localhost:8000
```

## Calibrate a new platform

```sh
uv run poker_rta calibrate --screenshot capture.png --out profiles/my_profile.yaml
```
```

**Step 3: Write `rta/src/poker_rta/__init__.py`**

```python
"""poker_rta — research RTA harness for the local poker coach."""

__version__ = "0.0.0"
```

**Step 4: Write empty `rta/src/poker_rta/py.typed`** (marker file, zero bytes).

**Step 5: Write `rta/tests/__init__.py`** (empty).

**Step 6: Write `rta/tests/conftest.py`**

```python
"""Shared pytest fixtures for the rta package."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
```

**Step 7: Write `rta/.gitignore`**

```
__pycache__/
*.pyc
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
recordings/
```

**Step 8: Verify uv sync works**

Run:
```sh
cd rta && uv sync && uv run python -c "import poker_rta; print(poker_rta.__version__)"
```
Expected: prints `0.0.0`.

**Step 9: Commit**

```sh
git add rta/
git commit -m "chore(rta): scaffold poker_rta package"
```

---

### Task 0.2: Wire `rta` into root Makefile

**Files:**
- Modify: `Makefile`

**Step 1: Update targets**

Replace the file with:

```make
.PHONY: dev test e2e lint fmt install db-upgrade rta-install rta-test rta-lint

install:
	cd backend && uv sync
	cd frontend && npm install
	cd rta && uv sync

rta-install:
	cd rta && uv sync

dev:
	@mkdir -p data
	@trap 'kill 0' SIGINT SIGTERM EXIT; \
		(cd backend && uv run uvicorn poker_coach.main:app --reload --port 8000) & \
		(cd frontend && npm run dev) & \
		wait

test:
	cd backend && uv run pytest
	cd frontend && npm test
	cd rta && uv run pytest

rta-test:
	cd rta && uv run pytest

e2e:
	cd frontend && npm run e2e

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
	cd frontend && npm run lint && npm run typecheck
	cd rta && uv run ruff check . && uv run ruff format --check . && uv run mypy src

rta-lint:
	cd rta && uv run ruff check . && uv run ruff format --check . && uv run mypy src

fmt:
	cd backend && uv run ruff format . && uv run ruff check --fix .
	cd frontend && npm run format
	cd rta && uv run ruff format . && uv run ruff check --fix .

db-upgrade:
	cd backend && uv run alembic upgrade head
```

**Step 2: Verify**

```sh
make rta-lint
```
Expected: clean (no files yet — ruff/mypy run on empty src).

**Step 3: Commit**

```sh
git add Makefile
git commit -m "chore(rta): wire rta targets into root Makefile"
```

---

## Phase 1 — Platform Profile Schema

The profile YAML is the polyvalence pivot: one profile per target platform, same engine.

### Task 1.1: Define the Pydantic profile model

**Files:**
- Create: `rta/src/poker_rta/profile/__init__.py`
- Create: `rta/src/poker_rta/profile/model.py`
- Create: `rta/tests/profile/__init__.py`
- Create: `rta/tests/profile/test_model.py`

**Step 1: Write the test first**

`rta/tests/profile/test_model.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from poker_rta.profile.model import (
    ROI,
    OCRPreprocess,
    PlatformProfile,
    WindowSelector,
)


def test_roi_requires_positive_dimensions() -> None:
    with pytest.raises(ValidationError):
        ROI(x=0, y=0, width=0, height=10)
    with pytest.raises(ValidationError):
        ROI(x=0, y=0, width=10, height=-5)


def test_profile_requires_all_core_rois() -> None:
    with pytest.raises(ValidationError):
        PlatformProfile(
            name="broken",
            version="1.0",
            window=WindowSelector(title_contains="x"),
            rois={},  # missing hero_cards, board, pot, hero_stack, villain_stack
            card_templates_dir="cards",
            button_templates={},
            ocr=OCRPreprocess(),
        )


def test_profile_valid_minimal() -> None:
    profile = PlatformProfile(
        name="mock",
        version="1.0",
        window=WindowSelector(title_contains="Mock"),
        rois={
            "hero_card_1": ROI(x=0, y=0, width=60, height=80),
            "hero_card_2": ROI(x=60, y=0, width=60, height=80),
            "board_1": ROI(x=0, y=100, width=60, height=80),
            "board_2": ROI(x=60, y=100, width=60, height=80),
            "board_3": ROI(x=120, y=100, width=60, height=80),
            "board_4": ROI(x=180, y=100, width=60, height=80),
            "board_5": ROI(x=240, y=100, width=60, height=80),
            "pot": ROI(x=0, y=200, width=120, height=30),
            "hero_stack": ROI(x=0, y=300, width=120, height=30),
            "villain_stack": ROI(x=0, y=400, width=120, height=30),
            "hero_bet": ROI(x=0, y=250, width=120, height=30),
            "villain_bet": ROI(x=0, y=450, width=120, height=30),
            "button_marker": ROI(x=0, y=500, width=30, height=30),
            "hero_action_highlight": ROI(x=0, y=550, width=200, height=30),
        },
        card_templates_dir="cards",
        button_templates={"check": "buttons/check.png", "fold": "buttons/fold.png"},
        ocr=OCRPreprocess(grayscale=True, threshold=128),
    )
    assert profile.name == "mock"
    assert profile.rois["hero_card_1"].width == 60
```

**Step 2: Run test to verify failure**

```sh
cd rta && uv run pytest tests/profile/test_model.py -v
```
Expected: FAIL, module not found.

**Step 3: Write `rta/src/poker_rta/profile/__init__.py`**

```python
from poker_rta.profile.model import (
    ROI,
    OCRPreprocess,
    PlatformProfile,
    WindowSelector,
)

__all__ = ["ROI", "OCRPreprocess", "PlatformProfile", "WindowSelector"]
```

**Step 4: Write `rta/src/poker_rta/profile/model.py`**

```python
"""Platform Profile — all site-specific config for the RTA pipeline.

A profile captures: where in the window to find each ROI, which card template
set to use, how to preprocess text for OCR, and optional timing hints. Swapping
profiles lets the same engine run on any target without code changes.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

REQUIRED_ROIS: frozenset[str] = frozenset(
    {
        "hero_card_1",
        "hero_card_2",
        "board_1",
        "board_2",
        "board_3",
        "board_4",
        "board_5",
        "pot",
        "hero_stack",
        "villain_stack",
        "hero_bet",
        "villain_bet",
        "button_marker",
        "hero_action_highlight",
    }
)


class ROI(BaseModel):
    """A rectangular region of interest within the captured window."""

    model_config = ConfigDict(frozen=True)

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class WindowSelector(BaseModel):
    """How to find the target window on screen.

    Either `title_contains` (substring match on window title — platform-dependent
    look-up via the capture layer) or explicit `bbox` on the primary display.
    """

    model_config = ConfigDict(frozen=True)

    title_contains: str | None = None
    bbox: ROI | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> WindowSelector:
        if (self.title_contains is None) == (self.bbox is None):
            raise ValueError("WindowSelector needs exactly one of title_contains or bbox")
        return self


class OCRPreprocess(BaseModel):
    """Image preprocessing hints for the OCR step."""

    model_config = ConfigDict(frozen=True)

    grayscale: bool = True
    threshold: int | None = Field(default=None, ge=0, le=255)
    invert: bool = False
    scale: float = Field(default=1.0, gt=0.0, le=8.0)


class PlatformProfile(BaseModel):
    """Top-level profile describing one target platform."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = ""
    window: WindowSelector
    rois: dict[str, ROI]
    card_templates_dir: str = Field(min_length=1)
    button_templates: dict[str, str]
    ocr: OCRPreprocess
    capture_fps: float = Field(default=5.0, gt=0.0, le=30.0)
    your_turn_highlight_threshold: float = Field(default=0.90, ge=0.0, le=1.0)

    @field_validator("rois")
    @classmethod
    def _require_core_rois(cls, v: dict[str, ROI]) -> dict[str, ROI]:
        missing = REQUIRED_ROIS - v.keys()
        if missing:
            raise ValueError(f"profile missing required ROIs: {sorted(missing)}")
        return v
```

**Step 5: Write `rta/tests/profile/__init__.py`** (empty).

**Step 6: Run test to verify pass**

```sh
cd rta && uv run pytest tests/profile/test_model.py -v
```
Expected: 3 passed.

**Step 7: Commit**

```sh
git add rta/src/poker_rta/profile/ rta/tests/profile/
git commit -m "feat(rta): platform profile schema with required ROI validation"
```

---

### Task 1.2: YAML load/save round-trip

**Files:**
- Modify: `rta/src/poker_rta/profile/__init__.py`
- Create: `rta/src/poker_rta/profile/io.py`
- Create: `rta/tests/profile/test_io.py`

**Step 1: Write the test**

`rta/tests/profile/test_io.py`:

```python
from __future__ import annotations

from pathlib import Path

from poker_rta.profile import PlatformProfile, load_profile, save_profile
from poker_rta.profile.model import ROI, OCRPreprocess, WindowSelector


def _minimal_profile() -> PlatformProfile:
    rois = {
        name: ROI(x=i, y=i, width=60, height=80)
        for i, name in enumerate(
            [
                "hero_card_1", "hero_card_2",
                "board_1", "board_2", "board_3", "board_4", "board_5",
                "pot", "hero_stack", "villain_stack",
                "hero_bet", "villain_bet",
                "button_marker", "hero_action_highlight",
            ],
            start=1,
        )
    }
    return PlatformProfile(
        name="test",
        version="1.0",
        window=WindowSelector(title_contains="Test"),
        rois=rois,
        card_templates_dir="cards",
        button_templates={"check": "buttons/check.png"},
        ocr=OCRPreprocess(),
    )


def test_round_trip(tmp_path: Path) -> None:
    original = _minimal_profile()
    target = tmp_path / "profile.yaml"
    save_profile(original, target)
    loaded = load_profile(target)
    assert loaded == original


def test_load_rejects_missing_roi(tmp_path: Path) -> None:
    import pytest
    from pydantic import ValidationError

    target = tmp_path / "broken.yaml"
    target.write_text(
        "name: broken\nversion: '1.0'\nwindow: {title_contains: x}\n"
        "rois:\n  hero_card_1: {x: 0, y: 0, width: 10, height: 10}\n"
        "card_templates_dir: cards\nbutton_templates: {}\nocr: {}\n"
    )
    with pytest.raises(ValidationError):
        load_profile(target)
```

**Step 2: Run to verify failure**

```sh
cd rta && uv run pytest tests/profile/test_io.py -v
```
Expected: FAIL, cannot import `load_profile` / `save_profile`.

**Step 3: Write `rta/src/poker_rta/profile/io.py`**

```python
"""YAML load/save for PlatformProfile."""

from __future__ import annotations

from pathlib import Path

import yaml

from poker_rta.profile.model import PlatformProfile


def load_profile(path: Path) -> PlatformProfile:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return PlatformProfile.model_validate(raw)


def save_profile(profile: PlatformProfile, path: Path) -> None:
    path.write_text(
        yaml.safe_dump(profile.model_dump(mode="python"), sort_keys=False),
        encoding="utf-8",
    )
```

**Step 4: Update `rta/src/poker_rta/profile/__init__.py`**

```python
from poker_rta.profile.io import load_profile, save_profile
from poker_rta.profile.model import (
    ROI,
    OCRPreprocess,
    PlatformProfile,
    WindowSelector,
)

__all__ = [
    "ROI",
    "OCRPreprocess",
    "PlatformProfile",
    "WindowSelector",
    "load_profile",
    "save_profile",
]
```

**Step 5: Run to verify pass**

```sh
cd rta && uv run pytest tests/profile/ -v
```
Expected: 5 passed.

**Step 6: Commit**

```sh
git add rta/src/poker_rta/profile/ rta/tests/profile/test_io.py
git commit -m "feat(rta): YAML load/save round-trip for platform profiles"
```

---

## Phase 2 — HTML Mock Demo Target

This is our reproducible demo platform for the paper. Static HTML + JS, deterministic state transitions, no network.

### Task 2.1: Build the static HTML poker mock

**Files:**
- Create: `rta/demo/mock_html/index.html`
- Create: `rta/demo/mock_html/styles.css`
- Create: `rta/demo/mock_html/game.js`

**Step 1: Write `rta/demo/mock_html/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Mock HU Poker Table</title>
<link rel="stylesheet" href="styles.css" />
</head>
<body>
<div class="table">
  <div class="seat villain">
    <div class="nameplate">Villain <span class="stack" id="villain-stack">10000</span></div>
    <div class="cards">
      <div class="card back"></div>
      <div class="card back"></div>
    </div>
    <div class="bet" id="villain-bet">0</div>
  </div>
  <div class="board" id="board"></div>
  <div class="pot" id="pot">0</div>
  <div class="seat hero">
    <div class="cards">
      <div class="card" id="hero-card-1">As</div>
      <div class="card" id="hero-card-2">Kd</div>
    </div>
    <div class="bet" id="hero-bet">0</div>
    <div class="nameplate">Hero <span class="stack" id="hero-stack">10000</span></div>
    <div class="button-marker" id="button-marker">D</div>
    <div class="action-bar" id="action-bar">
      <button id="btn-fold">Fold</button>
      <button id="btn-check-call">Check</button>
      <button id="btn-bet-raise">Bet 100</button>
    </div>
    <div class="hero-action-highlight" id="hero-action-highlight"></div>
  </div>
</div>
<script src="game.js"></script>
</body>
</html>
```

**Step 2: Write `rta/demo/mock_html/styles.css`**

```css
body { margin: 0; background: #1a3a2a; font-family: monospace; color: #eee; }
.table { position: relative; width: 1280px; height: 720px; margin: 0 auto; }
.seat { position: absolute; width: 400px; left: 440px; text-align: center; }
.villain { top: 40px; }
.hero { bottom: 40px; }
.nameplate { font-size: 18px; padding: 4px 8px; background: #222; border-radius: 4px; display: inline-block; }
.stack { color: #ffd700; font-weight: bold; margin-left: 8px; }
.cards { display: flex; justify-content: center; gap: 8px; margin: 8px 0; }
.card { width: 60px; height: 80px; background: #fff; color: #000; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: bold; border-radius: 6px; }
.card.back { background: repeating-linear-gradient(45deg,#800,#800 6px,#a00 6px,#a00 12px); color: transparent; }
.board { position: absolute; top: 300px; left: 440px; width: 400px; display: flex; gap: 8px; justify-content: center; }
.pot { position: absolute; top: 240px; left: 560px; width: 160px; text-align: center; background: #000; padding: 4px 8px; border-radius: 4px; color: #ffd700; font-weight: bold; font-size: 20px; }
.bet { margin: 6px auto; background: #000; color: #ffd700; display: inline-block; padding: 2px 8px; border-radius: 4px; min-width: 40px; }
.button-marker { position: absolute; right: -40px; top: 40px; width: 30px; height: 30px; background: #fff; color: #000; border-radius: 50%; font-weight: bold; display: flex; align-items: center; justify-content: center; }
.action-bar { margin-top: 8px; display: flex; gap: 8px; justify-content: center; }
.action-bar button { padding: 8px 16px; font-size: 16px; background: #444; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
.hero-action-highlight { height: 6px; background: transparent; margin-top: 6px; }
.hero-action-highlight.active { background: #0f0; }
```

**Step 3: Write `rta/demo/mock_html/game.js` — deterministic scripted hand loop**

```javascript
"use strict";

const SUITS = ["s", "h", "d", "c"];
const RANKS = ["2","3","4","5","6","7","8","9","T","J","Q","K","A"];

const SCRIPT = [
  { street: "preflop", hero: ["As","Kd"], villain: ["Qc","Qh"], board: [], pot: 300, heroStack: 9850, villainStack: 9700, heroBet: 150, villainBet: 300, btn: "hero", heroTurn: true, actions: ["Fold","Call","Raise 450"] },
  { street: "flop", hero: ["As","Kd"], board: ["Ah","7c","2d"], pot: 600, heroStack: 9700, villainStack: 9700, heroBet: 0, villainBet: 0, btn: "hero", heroTurn: false, actions: [] },
  { street: "flop", hero: ["As","Kd"], board: ["Ah","7c","2d"], pot: 900, heroStack: 9700, villainStack: 9400, heroBet: 0, villainBet: 300, btn: "hero", heroTurn: true, actions: ["Fold","Call","Raise 900"] },
  { street: "turn", hero: ["As","Kd"], board: ["Ah","7c","2d","9s"], pot: 1200, heroStack: 9400, villainStack: 9400, heroBet: 0, villainBet: 0, btn: "hero", heroTurn: true, actions: ["Check","Bet 600"] },
  { street: "river", hero: ["As","Kd"], board: ["Ah","7c","2d","9s","3h"], pot: 1200, heroStack: 9400, villainStack: 9400, heroBet: 0, villainBet: 0, btn: "hero", heroTurn: true, actions: ["Check","Bet 800"] },
];

let step = 0;

function render(state) {
  document.getElementById("hero-card-1").textContent = state.hero[0];
  document.getElementById("hero-card-2").textContent = state.hero[1];
  const board = document.getElementById("board");
  board.innerHTML = "";
  for (const c of state.board) {
    const div = document.createElement("div");
    div.className = "card";
    div.textContent = c;
    board.appendChild(div);
  }
  document.getElementById("pot").textContent = String(state.pot);
  document.getElementById("hero-stack").textContent = String(state.heroStack);
  document.getElementById("villain-stack").textContent = String(state.villainStack);
  document.getElementById("hero-bet").textContent = String(state.heroBet);
  document.getElementById("villain-bet").textContent = String(state.villainBet);
  document.getElementById("button-marker").textContent = state.btn === "hero" ? "D" : "";
  const bar = document.getElementById("action-bar");
  bar.innerHTML = "";
  for (const label of state.actions) {
    const b = document.createElement("button");
    b.textContent = label;
    bar.appendChild(b);
  }
  document.getElementById("hero-action-highlight").classList.toggle("active", state.heroTurn);
}

document.addEventListener("keydown", (e) => {
  if (e.key === "ArrowRight") {
    step = (step + 1) % SCRIPT.length;
    render(SCRIPT[step]);
  } else if (e.key === "ArrowLeft") {
    step = (step - 1 + SCRIPT.length) % SCRIPT.length;
    render(SCRIPT[step]);
  } else if (e.key === "r") {
    step = 0;
    render(SCRIPT[0]);
  }
});

render(SCRIPT[0]);
```

**Step 4: Smoke test — open in browser**

```sh
python3 -m http.server -d rta/demo/mock_html 8080
# Visit http://localhost:8080, press ArrowRight to advance, r to reset.
```
Expected: deterministic scripted hand states cycle on arrow keys.

**Step 5: Commit**

```sh
git add rta/demo/
git commit -m "feat(rta): HTML mock poker table for reproducible demo target"
```

---

### Task 2.2: Write mock profile + capture a reference screenshot

**Files:**
- Create: `rta/profiles/mock_html.yaml`
- Create: `rta/tests/fixtures/screenshots/mock_html_preflop.png`
- Create: `rta/templates/mock_html/cards/.gitkeep`
- Create: `rta/templates/mock_html/buttons/.gitkeep`

**Step 1: Capture reference screenshot**

Serve the mock, load step 0 (preflop), and capture the `.table` element as PNG 1280x720. Save to `rta/tests/fixtures/screenshots/mock_html_preflop.png`.

Commands (assumes Chromium-based headless):
```sh
python3 -m http.server -d rta/demo/mock_html 8080 &
MOCK_PID=$!
npx playwright install --with-deps chromium >/dev/null 2>&1 || true
node -e "
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({viewport: {width: 1280, height: 720}});
  await page.goto('http://localhost:8080');
  await page.screenshot({path: 'rta/tests/fixtures/screenshots/mock_html_preflop.png', clip: {x:0, y:0, width:1280, height:720}});
  await browser.close();
})();
"
kill $MOCK_PID
```

**Step 2: Write `rta/profiles/mock_html.yaml`**

ROI coordinates derived from the CSS layout in Task 2.1 (table 1280x720, hero-card at x=572 after `.seat.hero` offset + `.cards` centering, etc.). Measure directly from the screenshot in an image viewer; the values below are the canonical ones for the CSS shipped above.

```yaml
name: mock_html
version: "1.0"
description: Bundled HTML mock for reproducible RTA demo.
window:
  title_contains: "Mock HU Poker Table"
capture_fps: 5.0
your_turn_highlight_threshold: 0.85
card_templates_dir: templates/mock_html/cards
button_templates:
  fold: templates/mock_html/buttons/fold.png
  check: templates/mock_html/buttons/check.png
  call: templates/mock_html/buttons/call.png
  bet: templates/mock_html/buttons/bet.png
  raise: templates/mock_html/buttons/raise.png
ocr:
  grayscale: true
  threshold: 140
  invert: false
  scale: 2.0
rois:
  hero_card_1: { x: 572, y: 560, width: 60, height: 80 }
  hero_card_2: { x: 640, y: 560, width: 60, height: 80 }
  board_1:     { x: 464, y: 300, width: 60, height: 80 }
  board_2:     { x: 532, y: 300, width: 60, height: 80 }
  board_3:     { x: 600, y: 300, width: 60, height: 80 }
  board_4:     { x: 668, y: 300, width: 60, height: 80 }
  board_5:     { x: 736, y: 300, width: 60, height: 80 }
  pot:         { x: 560, y: 240, width: 160, height: 30 }
  hero_stack:  { x: 540, y: 690, width: 200, height: 24 }
  villain_stack: { x: 540, y: 40,  width: 200, height: 24 }
  hero_bet:    { x: 580, y: 646, width: 120, height: 26 }
  villain_bet: { x: 580, y: 170, width: 120, height: 26 }
  button_marker: { x: 844, y: 80, width: 30, height: 30 }
  hero_action_highlight: { x: 540, y: 700, width: 200, height: 6 }
```

**Step 3: Generate card templates from the mock's card style**

The mock draws cards as 60x80 white rectangles with the rank+suit text centered. Generate one PNG per (rank, suit) the same way for template matching:

Create `rta/scripts/build_mock_card_templates.py`:

```python
"""One-off: render mock_html cards at fixed size to templates dir."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RANKS = ["2","3","4","5","6","7","8","9","T","J","Q","K","A"]
SUITS = ["s","h","d","c"]
OUT = Path("rta/templates/mock_html/cards")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 24)
    except OSError:
        font = ImageFont.load_default()
    for r in RANKS:
        for s in SUITS:
            img = Image.new("RGB", (60, 80), "white")
            draw = ImageDraw.Draw(img)
            text = f"{r}{s}"
            bbox = draw.textbbox((0, 0), text, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((60 - w) / 2, (80 - h) / 2), text, fill="black", font=font)
            img.save(OUT / f"{r}{s}.png")


if __name__ == "__main__":
    main()
```

Run:
```sh
cd rta && uv run python scripts/build_mock_card_templates.py
```
Expected: 52 PNGs under `rta/templates/mock_html/cards/`.

**Step 4: Commit**

```sh
git add rta/profiles/mock_html.yaml rta/templates/mock_html/ rta/scripts/ rta/tests/fixtures/screenshots/
git commit -m "feat(rta): mock_html profile + card templates + reference screenshot"
```

---

## Phase 3 — Capture Layer

### Task 3.1: Screen capture via `mss`

**Files:**
- Create: `rta/src/poker_rta/capture/__init__.py`
- Create: `rta/src/poker_rta/capture/grab.py`
- Create: `rta/tests/capture/__init__.py`
- Create: `rta/tests/capture/test_grab.py`

**Step 1: Write the test**

`rta/tests/capture/test_grab.py`:

```python
from __future__ import annotations

from pathlib import Path

import numpy as np

from poker_rta.capture.grab import crop_roi, load_image
from poker_rta.profile.model import ROI


def test_crop_roi_returns_expected_shape(fixtures_dir: Path) -> None:
    img = load_image(fixtures_dir / "screenshots" / "mock_html_preflop.png")
    roi = ROI(x=572, y=560, width=60, height=80)
    crop = crop_roi(img, roi)
    assert crop.shape == (80, 60, 3)
    assert crop.dtype == np.uint8


def test_crop_roi_clips_to_image_bounds(fixtures_dir: Path) -> None:
    img = load_image(fixtures_dir / "screenshots" / "mock_html_preflop.png")
    roi = ROI(x=img.shape[1] - 10, y=img.shape[0] - 10, width=50, height=50)
    crop = crop_roi(img, roi)
    assert crop.shape == (10, 10, 3)
```

**Step 2: Run — expect failure**

```sh
cd rta && uv run pytest tests/capture/ -v
```
Expected: FAIL, module missing.

**Step 3: Write `rta/src/poker_rta/capture/grab.py`**

```python
"""Screen capture primitives.

`grab_window` uses mss to pull a rectangular region from the live display.
`load_image` + `crop_roi` are the test-friendly counterparts used by offline
tests and the replay harness.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import mss
import numpy as np

from poker_rta.profile.model import ROI, WindowSelector


def load_image(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"cannot read image: {path}")
    return img  # BGR


def crop_roi(img: np.ndarray, roi: ROI) -> np.ndarray:
    h, w = img.shape[:2]
    x2 = min(roi.x + roi.width, w)
    y2 = min(roi.y + roi.height, h)
    return img[roi.y : y2, roi.x : x2]


def grab_bbox(bbox: ROI) -> np.ndarray:
    """Grab a rectangular region from the primary display (BGR)."""
    with mss.mss() as sct:
        region = {"left": bbox.x, "top": bbox.y, "width": bbox.width, "height": bbox.height}
        raw = np.asarray(sct.grab(region))  # BGRA
    return cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)


def grab_window(selector: WindowSelector) -> np.ndarray:
    """Grab a region specified by a WindowSelector.

    When `bbox` is set, captures that region directly. When `title_contains` is
    set, the OS-specific window-lookup has to be plugged in by the caller; for
    initial milestones we use `bbox` only and leave title-based lookup as a
    platform-adapter extension point.
    """
    if selector.bbox is not None:
        return grab_bbox(selector.bbox)
    raise NotImplementedError("title-based window lookup ships in Task 3.2")
```

**Step 4: Write `rta/src/poker_rta/capture/__init__.py`**

```python
from poker_rta.capture.grab import crop_roi, grab_bbox, grab_window, load_image

__all__ = ["crop_roi", "grab_bbox", "grab_window", "load_image"]
```

**Step 5: Write `rta/tests/capture/__init__.py`** (empty).

**Step 6: Run test — expect pass**

```sh
cd rta && uv run pytest tests/capture/ -v
```
Expected: 2 passed.

**Step 7: Commit**

```sh
git add rta/src/poker_rta/capture/ rta/tests/capture/
git commit -m "feat(rta): screen capture + ROI crop primitives"
```

---

### Task 3.2: Window title lookup (platform adapters)

**Files:**
- Modify: `rta/src/poker_rta/capture/grab.py`
- Create: `rta/src/poker_rta/capture/window.py`
- Create: `rta/tests/capture/test_window.py`

**Step 1: Write the test**

`rta/tests/capture/test_window.py`:

```python
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
```

**Step 2: Write `rta/src/poker_rta/capture/window.py`**

```python
"""Cross-platform window-title lookup.

Each OS ships its own native adapter — Linux/X11 via `xdotool`, Windows via
`pygetwindow`, macOS via `Quartz`. For portability we call optional adapters
and surface a clear error when no adapter is wired for the current platform.
Callers should prefer `bbox:` in the profile when possible.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable

from poker_rta.profile.model import ROI


class WindowLookupUnavailable(RuntimeError):
    """Raised when no title-lookup adapter is available for this OS."""


def _linux_list_windows() -> list[tuple[str, ROI]]:
    if shutil.which("xdotool") is None:
        return []
    out = subprocess.run(
        ["xdotool", "search", "--name", ".*"],
        check=False,
        capture_output=True,
        text=True,
    )
    results: list[tuple[str, ROI]] = []
    for wid in out.stdout.splitlines():
        name = subprocess.run(
            ["xdotool", "getwindowname", wid], check=False, capture_output=True, text=True
        ).stdout.strip()
        geo = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", wid],
            check=False,
            capture_output=True,
            text=True,
        ).stdout
        env = dict(line.split("=", 1) for line in geo.splitlines() if "=" in line)
        try:
            roi = ROI(
                x=int(env["X"]), y=int(env["Y"]),
                width=int(env["WIDTH"]), height=int(env["HEIGHT"]),
            )
        except (KeyError, ValueError):
            continue
        results.append((name, roi))
    return results


_platform_list_windows: Callable[[], list[tuple[str, ROI]]] | None
if sys.platform.startswith("linux"):
    _platform_list_windows = _linux_list_windows
else:
    _platform_list_windows = None  # extend: win32 / darwin adapters


def resolve_title_to_bbox(title_contains: str) -> ROI | None:
    """Find the first window whose title contains `title_contains`.

    Returns the window bbox, or None if not found. Raises
    `WindowLookupUnavailable` if no adapter is wired for the current platform.
    """
    if _platform_list_windows is None:
        raise WindowLookupUnavailable(
            f"no window-title adapter for platform {sys.platform!r}; use explicit bbox in profile"
        )
    for name, roi in _platform_list_windows():
        if title_contains in name:
            return roi
    return None
```

**Step 3: Patch `grab_window` to use it**

In `rta/src/poker_rta/capture/grab.py`, replace the `NotImplementedError` block:

```python
def grab_window(selector: WindowSelector) -> np.ndarray:
    if selector.bbox is not None:
        return grab_bbox(selector.bbox)
    from poker_rta.capture.window import resolve_title_to_bbox

    assert selector.title_contains is not None  # mutually exclusive invariant
    bbox = resolve_title_to_bbox(selector.title_contains)
    if bbox is None:
        raise LookupError(f"window with title containing {selector.title_contains!r} not found")
    return grab_bbox(bbox)
```

**Step 4: Run tests**

```sh
cd rta && uv run pytest tests/capture/ -v
```
Expected: 4 passed.

**Step 5: Commit**

```sh
git add rta/src/poker_rta/capture/window.py rta/src/poker_rta/capture/grab.py rta/tests/capture/test_window.py
git commit -m "feat(rta): window-title lookup with platform adapters"
```

---

## Phase 4 — CV Pipeline: Cards

### Task 4.1: Template-matched card classifier

**Files:**
- Create: `rta/src/poker_rta/cv/__init__.py`
- Create: `rta/src/poker_rta/cv/cards.py`
- Create: `rta/tests/cv/__init__.py`
- Create: `rta/tests/cv/test_cards.py`

**Step 1: Write the test**

`rta/tests/cv/test_cards.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from poker_rta.capture.grab import crop_roi, load_image
from poker_rta.cv.cards import CardClassifier, classify_card
from poker_rta.profile.model import ROI


@pytest.fixture
def classifier() -> CardClassifier:
    templates = Path(__file__).parents[2] / "templates" / "mock_html" / "cards"
    return CardClassifier(templates_dir=templates)


def test_classify_ace_of_spades(classifier: CardClassifier, fixtures_dir: Path) -> None:
    img = load_image(fixtures_dir / "screenshots" / "mock_html_preflop.png")
    crop = crop_roi(img, ROI(x=572, y=560, width=60, height=80))
    assert classify_card(crop, classifier) == "As"


def test_classify_king_of_diamonds(classifier: CardClassifier, fixtures_dir: Path) -> None:
    img = load_image(fixtures_dir / "screenshots" / "mock_html_preflop.png")
    crop = crop_roi(img, ROI(x=640, y=560, width=60, height=80))
    assert classify_card(crop, classifier) == "Kd"


def test_classify_unknown_returns_none(classifier: CardClassifier, fixtures_dir: Path) -> None:
    import numpy as np
    blank = np.zeros((80, 60, 3), dtype=np.uint8)
    assert classify_card(blank, classifier, min_score=0.85) is None
```

**Step 2: Run — expect failure**

```sh
cd rta && uv run pytest tests/cv/test_cards.py -v
```
Expected: FAIL, module missing.

**Step 3: Write `rta/src/poker_rta/cv/cards.py`**

```python
"""Card classifier via normalized cross-correlation template matching.

For digital poker clients with a stable card style, template matching is:
- deterministic (no training required)
- explainable for the research paper
- ~100% accurate when templates match the client's rendering
If a client changes its card art, we regenerate the templates. Robustness to
style changes is out of scope for MVP; note as future work in the paper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

CardCode = str  # e.g., "As", "Kd", "Th"


@dataclass
class CardClassifier:
    templates_dir: Path
    _templates: dict[str, np.ndarray] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for path in self.templates_dir.glob("*.png"):
            tpl = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if tpl is None:
                continue
            self._templates[path.stem] = tpl

        if not self._templates:
            raise FileNotFoundError(f"no card templates found in {self.templates_dir}")

    def match(self, img: np.ndarray) -> tuple[CardCode, float]:
        best_code = ""
        best_score = -1.0
        for code, tpl in self._templates.items():
            if tpl.shape != img.shape:
                resized = cv2.resize(tpl, (img.shape[1], img.shape[0]))
            else:
                resized = tpl
            result = cv2.matchTemplate(img, resized, cv2.TM_CCOEFF_NORMED)
            score = float(result.max())
            if score > best_score:
                best_score, best_code = score, code
        return best_code, best_score


def classify_card(
    roi_img: np.ndarray,
    classifier: CardClassifier,
    min_score: float = 0.85,
) -> CardCode | None:
    """Classify one card-sized ROI. Returns the card code or None if no
    template matches above the score threshold (e.g., empty slot or card back)."""

    code, score = classifier.match(roi_img)
    return code if score >= min_score else None
```

**Step 4: Write `rta/src/poker_rta/cv/__init__.py`**

```python
from poker_rta.cv.cards import CardClassifier, classify_card

__all__ = ["CardClassifier", "classify_card"]
```

**Step 5: Write `rta/tests/cv/__init__.py`** (empty).

**Step 6: Run — expect pass**

```sh
cd rta && uv run pytest tests/cv/test_cards.py -v
```
Expected: 3 passed.

**Step 7: Commit**

```sh
git add rta/src/poker_rta/cv/ rta/tests/cv/
git commit -m "feat(rta): template-matched card classifier"
```

---

## Phase 5 — CV Pipeline: OCR for Numbers

### Task 5.1: EasyOCR wrapper + number parser

**Files:**
- Create: `rta/src/poker_rta/cv/ocr.py`
- Create: `rta/tests/cv/test_ocr.py`
- Modify: `rta/src/poker_rta/cv/__init__.py`

**Step 1: Write the test**

`rta/tests/cv/test_ocr.py`:

```python
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from poker_rta.cv.ocr import NumberReader, parse_chip_amount
from poker_rta.profile.model import OCRPreprocess


def _render_text(text: str, size: tuple[int, int] = (120, 30)) -> np.ndarray:
    img = Image.new("RGB", size, "black")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 20)
    except OSError:
        font = ImageFont.load_default()
    draw.text((4, 2), text, fill="yellow", font=font)
    return np.asarray(img)[..., ::-1]  # RGB -> BGR


@pytest.mark.parametrize("raw,expected", [
    ("123", 123),
    ("1,234", 1234),
    ("$1,234", 1234),
    ("10000", 10000),
])
def test_parse_chip_amount(raw: str, expected: int) -> None:
    assert parse_chip_amount(raw) == expected


def test_parse_rejects_nonnumeric() -> None:
    assert parse_chip_amount("abc") is None


@pytest.mark.slow
def test_reader_reads_simple_number() -> None:
    reader = NumberReader(OCRPreprocess(grayscale=True, threshold=128, scale=2.0))
    img = _render_text("9700")
    value = reader.read(img)
    assert value == 9700
```

**Step 2: Run — expect failure**

```sh
cd rta && uv run pytest tests/cv/test_ocr.py -v -k "parse"
```
Expected: FAIL (module missing).

**Step 3: Write `rta/src/poker_rta/cv/ocr.py`**

```python
"""OCR for chip amounts (stacks, pot, bets).

EasyOCR is the default engine — works cross-platform without system deps, good
digit accuracy. Preprocessing per-profile (threshold, invert, scale) lets us
adapt to dark/light text and low-DPI captures.
"""

from __future__ import annotations

import re
from functools import lru_cache

import cv2
import numpy as np

from poker_rta.profile.model import OCRPreprocess

_NUM_RE = re.compile(r"[-+]?[\d,]+")


def parse_chip_amount(raw: str) -> int | None:
    """Parse '$1,234' / '1234' / '1,234 bb' → 1234. None if no digits present."""
    m = _NUM_RE.search(raw)
    if m is None:
        return None
    digits = m.group(0).replace(",", "")
    try:
        return int(digits)
    except ValueError:
        return None


def _preprocess(img: np.ndarray, cfg: OCRPreprocess) -> np.ndarray:
    out = img
    if cfg.grayscale and out.ndim == 3:
        out = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    if cfg.threshold is not None:
        _, out = cv2.threshold(out, cfg.threshold, 255, cv2.THRESH_BINARY)
    if cfg.invert:
        out = cv2.bitwise_not(out)
    if cfg.scale != 1.0:
        out = cv2.resize(out, None, fx=cfg.scale, fy=cfg.scale, interpolation=cv2.INTER_CUBIC)
    return out


@lru_cache(maxsize=1)
def _get_easyocr_reader() -> object:
    import easyocr  # noqa: PLC0415 — lazy: model download on first call

    return easyocr.Reader(["en"], gpu=False, verbose=False)


class NumberReader:
    def __init__(self, preprocess: OCRPreprocess) -> None:
        self._pp = preprocess

    def read(self, img: np.ndarray) -> int | None:
        processed = _preprocess(img, self._pp)
        reader = _get_easyocr_reader()
        results = reader.readtext(processed, allowlist="0123456789,$ ", detail=0)  # type: ignore[attr-defined]
        for text in results:
            val = parse_chip_amount(text)
            if val is not None:
                return val
        return None
```

**Step 4: Update `rta/src/poker_rta/cv/__init__.py`**

```python
from poker_rta.cv.cards import CardClassifier, classify_card
from poker_rta.cv.ocr import NumberReader, parse_chip_amount

__all__ = ["CardClassifier", "NumberReader", "classify_card", "parse_chip_amount"]
```

**Step 5: Configure `slow` marker in `rta/pyproject.toml`**

Add to the `[tool.pytest.ini_options]` section:

```toml
markers = [
    "slow: tests that load heavy ML models (easyocr, etc.)",
]
```

**Step 6: Run fast tests — expect pass**

```sh
cd rta && uv run pytest tests/cv/test_ocr.py -v -m "not slow"
```
Expected: 5 passed (the 4 parametrized + 1 reject-nonnumeric).

**Step 7: Run slow test once to smoke the OCR path**

```sh
cd rta && uv run pytest tests/cv/test_ocr.py -v -m slow
```
Expected: 1 passed (may take 30s on first run due to model download).

**Step 8: Commit**

```sh
git add rta/src/poker_rta/cv/ rta/tests/cv/test_ocr.py rta/pyproject.toml
git commit -m "feat(rta): EasyOCR-backed chip-amount reader with preprocessing"
```

---

## Phase 6 — CV Pipeline: Buttons and Street

### Task 6.1: Button-state detector

**Files:**
- Create: `rta/src/poker_rta/cv/buttons.py`
- Create: `rta/tests/cv/test_buttons.py`
- Modify: `rta/src/poker_rta/cv/__init__.py`

**Step 1: Test**

`rta/tests/cv/test_buttons.py`:

```python
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from poker_rta.cv.buttons import ButtonDetector


@pytest.fixture
def detector(tmp_path: Path) -> ButtonDetector:
    # Synthesize two tiny templates: "FOLD" and "CHECK"
    for label in ("fold", "check"):
        img = np.zeros((20, 60, 3), dtype=np.uint8)
        cv2.putText(img, label.upper(), (2, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
        cv2.imwrite(str(tmp_path / f"{label}.png"), img)
    return ButtonDetector({"fold": tmp_path / "fold.png", "check": tmp_path / "check.png"})


def test_detects_present_button(detector: ButtonDetector) -> None:
    img = np.zeros((30, 240, 3), dtype=np.uint8)
    cv2.putText(img, "FOLD", (2, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
    assert "fold" in detector.detect(img)
    assert "check" not in detector.detect(img)
```

**Step 2: Run — expect fail, then write `rta/src/poker_rta/cv/buttons.py`**

```python
"""Detect which action buttons are present by matching small templates in the
action-bar ROI. Used both to confirm 'it's our turn' and to constrain
`legal_actions` inferred from the visible state.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class ButtonDetector:
    def __init__(self, templates: dict[str, Path], min_score: float = 0.75) -> None:
        self._templates: dict[str, np.ndarray] = {}
        for label, path in templates.items():
            tpl = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if tpl is None:
                raise FileNotFoundError(f"button template missing: {path}")
            self._templates[label] = tpl
        self._min_score = min_score

    def detect(self, img: np.ndarray) -> set[str]:
        present: set[str] = set()
        for label, tpl in self._templates.items():
            if tpl.shape[0] > img.shape[0] or tpl.shape[1] > img.shape[1]:
                continue
            result = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
            if float(result.max()) >= self._min_score:
                present.add(label)
        return present
```

**Step 3: Update `rta/src/poker_rta/cv/__init__.py`**

```python
from poker_rta.cv.buttons import ButtonDetector
from poker_rta.cv.cards import CardClassifier, classify_card
from poker_rta.cv.ocr import NumberReader, parse_chip_amount

__all__ = [
    "ButtonDetector",
    "CardClassifier",
    "NumberReader",
    "classify_card",
    "parse_chip_amount",
]
```

**Step 4: Run — expect pass**

```sh
cd rta && uv run pytest tests/cv/test_buttons.py -v
```
Expected: 1 passed.

**Step 5: Commit**

```sh
git add rta/src/poker_rta/cv/buttons.py rta/tests/cv/test_buttons.py rta/src/poker_rta/cv/__init__.py
git commit -m "feat(rta): button presence detector"
```

---

### Task 6.2: Composite frame observation

**Files:**
- Create: `rta/src/poker_rta/cv/pipeline.py`
- Create: `rta/tests/cv/test_pipeline.py`
- Modify: `rta/src/poker_rta/cv/__init__.py`

**Step 1: Test**

`rta/tests/cv/test_pipeline.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from poker_rta.capture.grab import load_image
from poker_rta.cv.cards import CardClassifier
from poker_rta.cv.pipeline import FrameObservation, observe_frame
from poker_rta.profile import load_profile


@pytest.fixture
def profile_path() -> Path:
    return Path(__file__).parents[2] / "profiles" / "mock_html.yaml"


@pytest.mark.slow
def test_observe_preflop_screenshot(profile_path: Path, fixtures_dir: Path) -> None:
    profile = load_profile(profile_path)
    img = load_image(fixtures_dir / "screenshots" / "mock_html_preflop.png")
    templates = Path(__file__).parents[2] / "templates" / "mock_html" / "cards"
    obs = observe_frame(img, profile, CardClassifier(templates))
    assert isinstance(obs, FrameObservation)
    assert obs.hero_cards == ("As", "Kd")
    assert obs.board == ()
    assert obs.pot_chips == 300
    assert obs.hero_stack_chips == 9850
    assert obs.villain_stack_chips == 9700
```

**Step 2: Write `rta/src/poker_rta/cv/pipeline.py`**

```python
"""Single-frame observation: given one screenshot + profile, extract every
poker-relevant fact we can see. No state, no memory — that's the tracker's job.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from poker_rta.capture.grab import crop_roi
from poker_rta.cv.buttons import ButtonDetector
from poker_rta.cv.cards import CardClassifier, classify_card
from poker_rta.cv.ocr import NumberReader
from poker_rta.profile.model import PlatformProfile


@dataclass(frozen=True)
class FrameObservation:
    hero_cards: tuple[str, str] | None
    board: tuple[str, ...]
    pot_chips: int | None
    hero_stack_chips: int | None
    villain_stack_chips: int | None
    hero_bet_chips: int | None
    villain_bet_chips: int | None
    hero_is_button: bool
    hero_to_act: bool
    visible_buttons: frozenset[str]


def _read_cards(img: np.ndarray, profile: PlatformProfile, classifier: CardClassifier, names: list[str]) -> list[str | None]:
    return [classify_card(crop_roi(img, profile.rois[n]), classifier) for n in names]


def _brightness(img: np.ndarray) -> float:
    return float(img.mean()) / 255.0


def observe_frame(
    img: np.ndarray,
    profile: PlatformProfile,
    classifier: CardClassifier,
    ocr: NumberReader | None = None,
    button_detector: ButtonDetector | None = None,
) -> FrameObservation:
    ocr = ocr or NumberReader(profile.ocr)
    if button_detector is None:
        buttons_root = Path(profile.card_templates_dir).parent / "buttons"
        button_detector = ButtonDetector(
            {k: Path(v) for k, v in profile.button_templates.items()}
        ) if (buttons_root.exists() and profile.button_templates) else None

    hero1, hero2 = _read_cards(img, profile, classifier, ["hero_card_1", "hero_card_2"])
    board_raw = _read_cards(
        img, profile, classifier,
        ["board_1", "board_2", "board_3", "board_4", "board_5"],
    )
    board = tuple(c for c in board_raw if c is not None)

    pot = ocr.read(crop_roi(img, profile.rois["pot"]))
    h_stack = ocr.read(crop_roi(img, profile.rois["hero_stack"]))
    v_stack = ocr.read(crop_roi(img, profile.rois["villain_stack"]))
    h_bet = ocr.read(crop_roi(img, profile.rois["hero_bet"]))
    v_bet = ocr.read(crop_roi(img, profile.rois["villain_bet"]))

    btn_crop = crop_roi(img, profile.rois["button_marker"])
    hero_is_button = _brightness(btn_crop) > 0.3

    highlight_crop = crop_roi(img, profile.rois["hero_action_highlight"])
    hero_to_act = _brightness(highlight_crop) >= profile.your_turn_highlight_threshold

    visible = frozenset(
        button_detector.detect(highlight_crop) if button_detector else ()
    )

    return FrameObservation(
        hero_cards=(hero1, hero2) if hero1 and hero2 else None,
        board=board,
        pot_chips=pot,
        hero_stack_chips=h_stack,
        villain_stack_chips=v_stack,
        hero_bet_chips=h_bet,
        villain_bet_chips=v_bet,
        hero_is_button=hero_is_button,
        hero_to_act=hero_to_act,
        visible_buttons=visible,
    )
```

**Step 3: Update `rta/src/poker_rta/cv/__init__.py`**

```python
from poker_rta.cv.buttons import ButtonDetector
from poker_rta.cv.cards import CardClassifier, classify_card
from poker_rta.cv.ocr import NumberReader, parse_chip_amount
from poker_rta.cv.pipeline import FrameObservation, observe_frame

__all__ = [
    "ButtonDetector",
    "CardClassifier",
    "FrameObservation",
    "NumberReader",
    "classify_card",
    "observe_frame",
    "parse_chip_amount",
]
```

**Step 4: Run slow test**

```sh
cd rta && uv run pytest tests/cv/test_pipeline.py -v -m slow
```
Expected: 1 passed.

**Step 5: Commit**

```sh
git add rta/src/poker_rta/cv/pipeline.py rta/tests/cv/test_pipeline.py rta/src/poker_rta/cv/__init__.py
git commit -m "feat(rta): composite single-frame observation pipeline"
```

---

## Phase 7 — State Tracker (hardest phase)

The tracker reconstructs action history from frame deltas. This is where errors compound; invest in tests.

### Task 7.1: Hand boundary + reset

**Files:**
- Create: `rta/src/poker_rta/state/__init__.py`
- Create: `rta/src/poker_rta/state/tracker.py`
- Create: `rta/tests/state/__init__.py`
- Create: `rta/tests/state/test_boundaries.py`

**Step 1: Test**

`rta/tests/state/test_boundaries.py`:

```python
from __future__ import annotations

from poker_rta.cv.pipeline import FrameObservation
from poker_rta.state.tracker import StateTracker


def _obs(**kw: object) -> FrameObservation:
    base = {
        "hero_cards": ("As", "Kd"),
        "board": (),
        "pot_chips": 0,
        "hero_stack_chips": 10000,
        "villain_stack_chips": 10000,
        "hero_bet_chips": 0,
        "villain_bet_chips": 0,
        "hero_is_button": True,
        "hero_to_act": False,
        "visible_buttons": frozenset(),
    }
    base.update(kw)
    return FrameObservation(**base)  # type: ignore[arg-type]


def test_first_frame_starts_new_hand() -> None:
    tr = StateTracker(bb=100, starting_stack=10000)
    tr.ingest(_obs())
    assert tr.current_hand_id is not None


def test_new_hole_cards_triggers_new_hand() -> None:
    tr = StateTracker(bb=100, starting_stack=10000)
    tr.ingest(_obs(hero_cards=("As", "Kd")))
    hid1 = tr.current_hand_id
    tr.ingest(_obs(hero_cards=("Qh", "Jc"), board=()))
    assert tr.current_hand_id != hid1


def test_same_hole_cards_no_new_hand() -> None:
    tr = StateTracker(bb=100, starting_stack=10000)
    tr.ingest(_obs(hero_cards=("As", "Kd")))
    hid = tr.current_hand_id
    tr.ingest(_obs(hero_cards=("As", "Kd")))
    assert tr.current_hand_id == hid
```

**Step 2: Write minimal `rta/src/poker_rta/state/tracker.py`**

```python
"""State tracker — turns a stream of `FrameObservation`s into a game-state
history. Handles hand boundaries, action inference from stack/pot deltas, and
turn detection. This is the brain of the RTA.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from poker_rta.cv.pipeline import FrameObservation


def _new_hand_id() -> str:
    import secrets
    return secrets.token_hex(8)


@dataclass
class StateTracker:
    bb: int
    starting_stack: int
    current_hand_id: str | None = None
    _last_hero_cards: tuple[str, str] | None = None

    def ingest(self, obs: FrameObservation) -> None:
        if obs.hero_cards is not None and obs.hero_cards != self._last_hero_cards:
            self.current_hand_id = _new_hand_id()
            self._last_hero_cards = obs.hero_cards
```

**Step 3: Write `rta/src/poker_rta/state/__init__.py`**

```python
from poker_rta.state.tracker import StateTracker

__all__ = ["StateTracker"]
```

**Step 4: Write `rta/tests/state/__init__.py`** (empty).

**Step 5: Run — expect pass**

```sh
cd rta && uv run pytest tests/state/test_boundaries.py -v
```
Expected: 3 passed.

**Step 6: Commit**

```sh
git add rta/src/poker_rta/state/ rta/tests/state/
git commit -m "feat(rta): state tracker skeleton with hand-boundary detection"
```

---

### Task 7.2: Street detection from board cards

**Files:**
- Modify: `rta/src/poker_rta/state/tracker.py`
- Create: `rta/tests/state/test_streets.py`

**Step 1: Test**

`rta/tests/state/test_streets.py`:

```python
from __future__ import annotations

from poker_rta.cv.pipeline import FrameObservation
from poker_rta.state.tracker import StateTracker


def _obs(board: tuple[str, ...] = ()) -> FrameObservation:
    return FrameObservation(
        hero_cards=("As", "Kd"),
        board=board,
        pot_chips=0,
        hero_stack_chips=10000,
        villain_stack_chips=10000,
        hero_bet_chips=0,
        villain_bet_chips=0,
        hero_is_button=True,
        hero_to_act=False,
        visible_buttons=frozenset(),
    )


def test_street_transitions() -> None:
    tr = StateTracker(bb=100, starting_stack=10000)
    tr.ingest(_obs(board=()))
    assert tr.current_street == "preflop"
    tr.ingest(_obs(board=("Ah","7c","2d")))
    assert tr.current_street == "flop"
    tr.ingest(_obs(board=("Ah","7c","2d","9s")))
    assert tr.current_street == "turn"
    tr.ingest(_obs(board=("Ah","7c","2d","9s","3h")))
    assert tr.current_street == "river"
```

**Step 2: Extend tracker**

Modify `rta/src/poker_rta/state/tracker.py` — add `current_street` field and update `ingest`:

```python
from typing import Literal

Street = Literal["preflop", "flop", "turn", "river"]

_BOARD_TO_STREET: dict[int, Street] = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}


@dataclass
class StateTracker:
    bb: int
    starting_stack: int
    current_hand_id: str | None = None
    current_street: Street = "preflop"
    _last_hero_cards: tuple[str, str] | None = None

    def ingest(self, obs: FrameObservation) -> None:
        if obs.hero_cards is not None and obs.hero_cards != self._last_hero_cards:
            self.current_hand_id = _new_hand_id()
            self._last_hero_cards = obs.hero_cards
            self.current_street = "preflop"

        n = len(obs.board)
        if n in _BOARD_TO_STREET:
            self.current_street = _BOARD_TO_STREET[n]
```

**Step 3: Run — expect pass**

```sh
cd rta && uv run pytest tests/state/ -v
```
Expected: 4 passed.

**Step 4: Commit**

```sh
git add rta/src/poker_rta/state/tracker.py rta/tests/state/test_streets.py
git commit -m "feat(rta): street detection from visible board cards"
```

---

### Task 7.3: Action inference from stack/pot deltas

**Files:**
- Modify: `rta/src/poker_rta/state/tracker.py`
- Create: `rta/tests/state/test_actions.py`

**Step 1: Test**

`rta/tests/state/test_actions.py`:

```python
from __future__ import annotations

from poker_rta.cv.pipeline import FrameObservation
from poker_rta.state.tracker import StateTracker


def _obs(
    hero_stack: int = 10000, villain_stack: int = 10000,
    hero_bet: int = 0, villain_bet: int = 0,
    pot: int = 0, board: tuple[str, ...] = (),
    hero_to_act: bool = False,
) -> FrameObservation:
    return FrameObservation(
        hero_cards=("As","Kd"),
        board=board,
        pot_chips=pot,
        hero_stack_chips=hero_stack,
        villain_stack_chips=villain_stack,
        hero_bet_chips=hero_bet,
        villain_bet_chips=villain_bet,
        hero_is_button=True,
        hero_to_act=hero_to_act,
        visible_buttons=frozenset(),
    )


def test_hero_post_sb_villain_post_bb() -> None:
    tr = StateTracker(bb=100, starting_stack=10000)
    tr.ingest(_obs(hero_stack=9950, villain_stack=9900, hero_bet=50, villain_bet=100, pot=150))
    assert len(tr.history) == 2
    assert tr.history[0].actor == "hero"
    assert tr.history[0].type == "bet"
    assert tr.history[0].to_amount == 50
    assert tr.history[1].actor == "villain"
    assert tr.history[1].type == "bet"
    assert tr.history[1].to_amount == 100


def test_villain_raise_detected() -> None:
    tr = StateTracker(bb=100, starting_stack=10000)
    tr.ingest(_obs(hero_stack=9950, villain_stack=9900, hero_bet=50, villain_bet=100, pot=150))
    tr.ingest(_obs(hero_stack=9700, villain_stack=9900, hero_bet=300, villain_bet=100, pot=400))
    tr.ingest(_obs(hero_stack=9700, villain_stack=9100, hero_bet=300, villain_bet=900, pot=1200, hero_to_act=True))
    kinds = [a.type for a in tr.history]
    assert kinds == ["bet", "bet", "raise", "raise"]
```

**Step 2: Extend tracker with action inference**

Modify `rta/src/poker_rta/state/tracker.py`:

```python
from dataclasses import dataclass, field

from poker_rta.cv.pipeline import FrameObservation

Street = Literal["preflop", "flop", "turn", "river"]
Seat = Literal["hero", "villain"]
ActionType = Literal["fold", "check", "call", "bet", "raise", "allin"]

_BOARD_TO_STREET: dict[int, Street] = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}


@dataclass(frozen=True)
class TrackedAction:
    actor: Seat
    type: ActionType
    to_amount: int | None


@dataclass
class StateTracker:
    bb: int
    starting_stack: int
    current_hand_id: str | None = None
    current_street: Street = "preflop"
    history: list[TrackedAction] = field(default_factory=list)
    _last_obs: FrameObservation | None = None
    _last_hero_cards: tuple[str, str] | None = None
    _last_aggressor_amount: int = 0

    def ingest(self, obs: FrameObservation) -> None:
        self._maybe_new_hand(obs)
        self._maybe_update_street(obs)
        self._infer_actions(obs)
        self._last_obs = obs

    def _maybe_new_hand(self, obs: FrameObservation) -> None:
        if obs.hero_cards is not None and obs.hero_cards != self._last_hero_cards:
            self.current_hand_id = _new_hand_id()
            self._last_hero_cards = obs.hero_cards
            self.current_street = "preflop"
            self.history = []
            self._last_aggressor_amount = 0
            self._last_obs = None

    def _maybe_update_street(self, obs: FrameObservation) -> None:
        new_street = _BOARD_TO_STREET.get(len(obs.board))
        if new_street is not None and new_street != self.current_street:
            self.current_street = new_street
            self._last_aggressor_amount = 0

    def _infer_actions(self, obs: FrameObservation) -> None:
        prev = self._last_obs
        if prev is None:
            if obs.hero_bet_chips and obs.hero_bet_chips > 0:
                self._emit("hero", obs.hero_bet_chips)
            if obs.villain_bet_chips and obs.villain_bet_chips > 0:
                self._emit("villain", obs.villain_bet_chips)
            return

        if obs.hero_bet_chips is not None and prev.hero_bet_chips is not None:
            if obs.hero_bet_chips > prev.hero_bet_chips:
                self._emit("hero", obs.hero_bet_chips)
        if obs.villain_bet_chips is not None and prev.villain_bet_chips is not None:
            if obs.villain_bet_chips > prev.villain_bet_chips:
                self._emit("villain", obs.villain_bet_chips)

    def _emit(self, actor: Seat, to_amount: int) -> None:
        if to_amount > self._last_aggressor_amount:
            kind: ActionType = "raise" if self._last_aggressor_amount > 0 else "bet"
            self.history.append(TrackedAction(actor, kind, to_amount))
            self._last_aggressor_amount = to_amount
        elif to_amount == self._last_aggressor_amount:
            self.history.append(TrackedAction(actor, "call", to_amount))
```

**Step 3: Run — expect pass**

```sh
cd rta && uv run pytest tests/state/ -v
```
Expected: 6 passed.

**Step 4: Commit**

```sh
git add rta/src/poker_rta/state/tracker.py rta/tests/state/test_actions.py
git commit -m "feat(rta): action inference from stack/bet deltas"
```

---

### Task 7.4: Build `GameState` for the coach API

**Files:**
- Create: `rta/src/poker_rta/state/game_state_builder.py`
- Create: `rta/tests/state/test_game_state_builder.py`
- Modify: `rta/src/poker_rta/state/__init__.py`

**Step 1: Test**

`rta/tests/state/test_game_state_builder.py`:

```python
from __future__ import annotations

from poker_rta.cv.pipeline import FrameObservation
from poker_rta.state.game_state_builder import build_coach_payload
from poker_rta.state.tracker import StateTracker


def _obs(**kw: object) -> FrameObservation:
    base = {
        "hero_cards": ("As", "Kd"),
        "board": (),
        "pot_chips": 150,
        "hero_stack_chips": 9950,
        "villain_stack_chips": 9900,
        "hero_bet_chips": 50,
        "villain_bet_chips": 100,
        "hero_is_button": True,
        "hero_to_act": True,
        "visible_buttons": frozenset({"fold", "call", "raise"}),
    }
    base.update(kw)
    return FrameObservation(**base)  # type: ignore[arg-type]


def test_build_coach_payload_shapes() -> None:
    tr = StateTracker(bb=100, starting_stack=10000)
    tr.ingest(_obs())
    payload = build_coach_payload(tr, _obs())
    assert payload["bb"] == 100
    assert payload["hero_hole"] == ["As", "Kd"]
    assert payload["button"] == "hero"
    assert payload["pot"] == 150
    assert payload["stacks"] == {"hero": 9950, "villain": 9900}
    assert payload["committed"] == {"hero": 50, "villain": 100}
    assert payload["to_act"] == "hero"
    assert payload["street"] == "preflop"
```

**Step 2: Write `rta/src/poker_rta/state/game_state_builder.py`**

```python
"""Shape the tracker's internal state + the latest observation into the exact
JSON payload the backend's `CreateDecisionRequest.game_state` expects.

Contract: must round-trip cleanly through `GameState.model_validate`. We emit a
dict with JSON-safe types so the coach client can post it without extra work.
Keys mirror `backend/src/poker_coach/engine/models.py:GameState`.
"""

from __future__ import annotations

from typing import Any

from poker_rta.cv.pipeline import FrameObservation
from poker_rta.state.tracker import StateTracker


def _require(value: int | None, field: str) -> int:
    if value is None:
        raise ValueError(f"state-build: missing {field} in latest observation")
    return value


def build_coach_payload(tracker: StateTracker, obs: FrameObservation) -> dict[str, Any]:
    if tracker.current_hand_id is None or obs.hero_cards is None:
        raise ValueError("state-build: no active hand / hero cards")

    hero_stack = _require(obs.hero_stack_chips, "hero_stack_chips")
    villain_stack = _require(obs.villain_stack_chips, "villain_stack_chips")
    hero_bet = _require(obs.hero_bet_chips, "hero_bet_chips")
    villain_bet = _require(obs.villain_bet_chips, "villain_bet_chips")
    pot = _require(obs.pot_chips, "pot_chips")

    effective_stack = min(hero_stack + hero_bet, villain_stack + villain_bet)
    button = "hero" if obs.hero_is_button else "villain"
    to_act = "hero" if obs.hero_to_act else None

    history_dump = [
        {"actor": a.actor, "type": a.type, "to_amount": a.to_amount}
        for a in tracker.history
    ]

    return {
        "hand_id": tracker.current_hand_id,
        "bb": tracker.bb,
        "effective_stack": effective_stack,
        "button": button,
        "hero_hole": list(obs.hero_cards),
        "villain_hole": None,  # CV CANNOT see villain holes — invariant
        "board": list(obs.board),
        "street": tracker.current_street,
        "stacks": {"hero": hero_stack, "villain": villain_stack},
        "committed": {"hero": hero_bet, "villain": villain_bet},
        "pot": pot,
        "to_act": to_act,
        "last_aggressor": None,
        "last_raise_size": 0,
        "raises_open": True,
        "acted_this_street": [],
        "history": history_dump,
        "rng_seed": None,
        "deck_snapshot": None,
        "pending_reveal": None,
        "reveals": [],
    }
```

**Step 3: Update `rta/src/poker_rta/state/__init__.py`**

```python
from poker_rta.state.game_state_builder import build_coach_payload
from poker_rta.state.tracker import StateTracker, TrackedAction

__all__ = ["StateTracker", "TrackedAction", "build_coach_payload"]
```

**Step 4: Run — expect pass**

```sh
cd rta && uv run pytest tests/state/ -v
```
Expected: 7 passed.

**Step 5: Integration sanity — round-trip through backend's GameState**

Add one more test in `test_game_state_builder.py`:

```python
def test_payload_validates_against_backend_game_state() -> None:
    import sys

    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[3] / "backend" / "src"))
    from poker_coach.engine.models import GameState  # type: ignore[import-not-found]

    tr = StateTracker(bb=100, starting_stack=10000)
    tr.ingest(_obs())
    payload = build_coach_payload(tr, _obs())
    state = GameState.model_validate(payload)
    assert state.hero_hole == ("As", "Kd")
    assert state.villain_hole is None
```

Run: `cd rta && uv run pytest tests/state/ -v`
Expected: 8 passed.

**Step 6: Commit**

```sh
git add rta/src/poker_rta/state/ rta/tests/state/test_game_state_builder.py
git commit -m "feat(rta): build backend-compatible GameState payload"
```

---

## Phase 8 — Coach API Client

### Task 8.1: Session + hand bootstrap

**Files:**
- Create: `rta/src/poker_rta/client/__init__.py`
- Create: `rta/src/poker_rta/client/coach_client.py`
- Create: `rta/tests/client/__init__.py`
- Create: `rta/tests/client/test_coach_client.py`

**Step 1: Test (using `respx` to mock the backend)**

`rta/tests/client/test_coach_client.py`:

```python
from __future__ import annotations

import httpx
import pytest
import respx

from poker_rta.client.coach_client import CoachClient


@respx.mock
@pytest.mark.asyncio
async def test_session_and_hand_bootstrap() -> None:
    respx.post("http://localhost:8000/api/sessions").mock(
        return_value=httpx.Response(200, json={"session_id": "s_abc"})
    )
    respx.post("http://localhost:8000/api/hands").mock(
        return_value=httpx.Response(200, json={"hand_id": "h_xyz"})
    )
    client = CoachClient(base_url="http://localhost:8000")
    async with client:
        session_id = await client.create_session(mode="live", notes="rta_demo")
        hand_id = await client.create_hand(session_id=session_id, bb=100, starting_stack=10000)
    assert session_id == "s_abc"
    assert hand_id == "h_xyz"
```

**Step 2: Write `rta/src/poker_rta/client/coach_client.py`**

```python
"""HTTP client for the local poker_coach backend.

All calls are async (httpx). The lifecycle mirrors backend's lazy pattern:
1. create_session → session_id
2. create_hand     → hand_id
3. create_decision → decision_id (row is `in_flight`, oracle NOT called yet)
4. stream_decision → SSE; oracle fires here
"""

from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Any

import httpx


@dataclass
class CoachClient:
    base_url: str
    timeout: float = 180.0

    def __post_init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> CoachClient:
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _required(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("CoachClient must be used as an async context manager")
        return self._client

    async def create_session(self, mode: str = "live", notes: str | None = None) -> str:
        r = await self._required().post("/api/sessions", json={"mode": mode, "notes": notes})
        r.raise_for_status()
        return str(r.json()["session_id"])

    async def create_hand(
        self,
        session_id: str,
        bb: int,
        starting_stack: int,
        rng_seed: int | None = None,
        deck_snapshot: list[str] | None = None,
    ) -> str:
        r = await self._required().post(
            "/api/hands",
            json={
                "session_id": session_id,
                "bb": bb,
                "effective_stack_start": starting_stack,
                "rng_seed": rng_seed,
                "deck_snapshot": deck_snapshot,
            },
        )
        r.raise_for_status()
        return str(r.json()["hand_id"])

    async def create_decision(
        self,
        session_id: str,
        hand_id: str | None,
        game_state: dict[str, Any],
        model_preset: str = "gpt-5.3-codex-xhigh",
        prompt_name: str = "coach",
        prompt_version: str = "v2",
        villain_profile: str = "unknown",
    ) -> str:
        r = await self._required().post(
            "/api/decisions",
            json={
                "session_id": session_id,
                "hand_id": hand_id,
                "model_preset": model_preset,
                "prompt_name": prompt_name,
                "prompt_version": prompt_version,
                "game_state": game_state,
                "villain_profile": villain_profile,
            },
        )
        r.raise_for_status()
        return str(r.json()["decision_id"])
```

**Step 3: Write `rta/src/poker_rta/client/__init__.py`**

```python
from poker_rta.client.coach_client import CoachClient

__all__ = ["CoachClient"]
```

**Step 4: Write `rta/tests/client/__init__.py`** (empty).

**Step 5: Run — expect pass**

```sh
cd rta && uv run pytest tests/client/ -v
```
Expected: 1 passed.

**Step 6: Commit**

```sh
git add rta/src/poker_rta/client/ rta/tests/client/
git commit -m "feat(rta): async coach HTTP client with session/hand/decision bootstrap"
```

---

### Task 8.2: SSE stream consumer + parsed-advice assembly

**Files:**
- Modify: `rta/src/poker_rta/client/coach_client.py`
- Create: `rta/tests/client/test_stream.py`

**Step 1: Test**

`rta/tests/client/test_stream.py`:

```python
from __future__ import annotations

import httpx
import pytest
import respx

from poker_rta.client.coach_client import CoachClient, StreamedAdvice


@respx.mock
@pytest.mark.asyncio
async def test_stream_collects_reasoning_and_advice() -> None:
    body = (
        b"event: reasoning_delta\ndata: {\"text\": \"think\"}\n\n"
        b"event: reasoning_complete\ndata: {\"text\": \"thinking done\"}\n\n"
        b"event: tool_call_complete\ndata: {\"parsed\": {\"action\": \"raise\", \"to_bb\": 3.0, \"rationale\": \"value\"}}\n\n"
        b"event: usage_complete\ndata: {\"input_tokens\": 1200, \"output_tokens\": 400}\n\n"
    )
    respx.get("http://localhost:8000/api/decisions/d_1/stream").mock(
        return_value=httpx.Response(200, content=body, headers={"Content-Type": "text/event-stream"})
    )
    client = CoachClient(base_url="http://localhost:8000")
    async with client:
        result = await client.stream_decision("d_1")
    assert isinstance(result, StreamedAdvice)
    assert result.parsed_advice == {"action": "raise", "to_bb": 3.0, "rationale": "value"}
    assert result.reasoning_text == "thinking done"
    assert result.usage == {"input_tokens": 1200, "output_tokens": 400}
```

**Step 2: Extend client**

Add to `rta/src/poker_rta/client/coach_client.py`:

```python
import json
from dataclasses import dataclass, field


@dataclass
class StreamedAdvice:
    parsed_advice: dict[str, Any] | None = None
    reasoning_text: str | None = None
    reasoning_stream: list[str] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


async def _iter_sse(resp: httpx.Response) -> "typing.AsyncIterator[tuple[str, dict[str, Any]]]":
    ...
```

Full replacement for that module (append these at the end, before `CoachClient` closes):

```python
# (append to CoachClient)
    async def stream_decision(self, decision_id: str) -> StreamedAdvice:
        client = self._required()
        result = StreamedAdvice()
        async with client.stream("GET", f"/api/decisions/{decision_id}/stream") as resp:
            resp.raise_for_status()
            event_name: str | None = None
            async for raw_line in resp.aiter_lines():
                if not raw_line:
                    event_name = None
                    continue
                if raw_line.startswith("event:"):
                    event_name = raw_line[6:].strip()
                elif raw_line.startswith("data:"):
                    payload = json.loads(raw_line[5:].strip() or "null") if raw_line[5:].strip() else {}
                    if event_name == "reasoning_delta":
                        result.reasoning_stream.append(payload.get("text", ""))
                    elif event_name == "reasoning_complete":
                        result.reasoning_text = payload.get("text")
                    elif event_name == "tool_call_complete":
                        result.parsed_advice = payload.get("parsed")
                    elif event_name == "usage_complete":
                        result.usage = dict(payload)
                    elif event_name == "error":
                        result.error = payload.get("message")
        return result
```

Also export `StreamedAdvice` from `client/__init__.py`:

```python
from poker_rta.client.coach_client import CoachClient, StreamedAdvice

__all__ = ["CoachClient", "StreamedAdvice"]
```

**Step 3: Run — expect pass**

```sh
cd rta && uv run pytest tests/client/ -v
```
Expected: 2 passed.

**Step 4: Commit**

```sh
git add rta/src/poker_rta/client/ rta/tests/client/test_stream.py
git commit -m "feat(rta): SSE stream consumer with reasoning/advice/usage assembly"
```

---

## Phase 9 — Overlay

### Task 9.1: Transparent always-on-top window

**Files:**
- Create: `rta/src/poker_rta/overlay/__init__.py`
- Create: `rta/src/poker_rta/overlay/window.py`
- Create: `rta/tests/overlay/__init__.py`
- Create: `rta/tests/overlay/test_window.py`

**Step 1: Test (smoke-only — Qt needs a display)**

`rta/tests/overlay/test_window.py`:

```python
from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_overlay_window_constructs() -> None:
    from PyQt6.QtWidgets import QApplication  # noqa: PLC0415

    from poker_rta.overlay.window import AdviceOverlay

    app = QApplication.instance() or QApplication([])
    win = AdviceOverlay()
    win.show_advice({"action": "raise", "to_bb": 3.0, "rationale": "value"})
    assert "raise" in win.current_text().lower()
    app.quit()
```

**Step 2: Write `rta/src/poker_rta/overlay/window.py`**

```python
"""Transparent always-on-top advice overlay.

Design: frameless window with a semi-transparent dark background, renders the
latest advice in large text. The user sees it over their game client; no input
is ever injected — they click themselves. This is the cinematic piece of the
research demo.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class AdviceOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._label = QLabel("RTA ready.")
        self._label.setStyleSheet(
            "color: #fff; background: rgba(0,0,0,180); padding: 12px;"
            " border-radius: 8px; font-family: monospace; font-size: 18px;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        self.resize(420, 140)

    def show_advice(self, advice: dict[str, Any]) -> None:
        lines = [
            f"{str(advice.get('action', '?')).upper()}"
            + (f"  →  {advice['to_bb']} bb" if "to_bb" in advice else ""),
        ]
        if advice.get("rationale"):
            lines.append(str(advice["rationale"]))
        self._label.setText("\n".join(lines))

    def current_text(self) -> str:
        return self._label.text()
```

**Step 3: Write `rta/src/poker_rta/overlay/__init__.py`**

```python
from poker_rta.overlay.window import AdviceOverlay

__all__ = ["AdviceOverlay"]
```

**Step 4: Write `rta/tests/overlay/__init__.py`** (empty).

**Step 5: Smoke test**

```sh
cd rta && RTA_QT_SMOKE=1 QT_QPA_PLATFORM=offscreen uv run pytest tests/overlay/ -v
```
Expected: 1 passed.

**Step 6: Commit**

```sh
git add rta/src/poker_rta/overlay/ rta/tests/overlay/
git commit -m "feat(rta): transparent always-on-top advice overlay"
```

---

## Phase 10 — Calibration UI

### Task 10.1: Screenshot ROI painter

**Files:**
- Create: `rta/src/poker_rta/calibration/__init__.py`
- Create: `rta/src/poker_rta/calibration/painter.py`
- Create: `rta/tests/calibration/__init__.py`
- Create: `rta/tests/calibration/test_painter.py`

**Step 1: Test — pure logic, no GUI**

`rta/tests/calibration/test_painter.py`:

```python
from __future__ import annotations

from poker_rta.calibration.painter import CalibrationDoc, emit_profile


def test_emit_profile_uses_clicked_rois() -> None:
    doc = CalibrationDoc(
        name="friend", version="1.0", window_title="Friend App",
        card_templates_dir="templates/friend/cards",
        button_templates={},
        rois={
            "hero_card_1": (10, 10, 60, 80),
            "hero_card_2": (70, 10, 60, 80),
            "board_1": (10, 100, 60, 80),
            "board_2": (70, 100, 60, 80),
            "board_3": (130, 100, 60, 80),
            "board_4": (190, 100, 60, 80),
            "board_5": (250, 100, 60, 80),
            "pot": (10, 200, 120, 30),
            "hero_stack": (10, 300, 120, 30),
            "villain_stack": (10, 400, 120, 30),
            "hero_bet": (10, 250, 120, 30),
            "villain_bet": (10, 450, 120, 30),
            "button_marker": (10, 500, 30, 30),
            "hero_action_highlight": (10, 550, 200, 30),
        },
    )
    profile = emit_profile(doc)
    assert profile.name == "friend"
    assert profile.rois["hero_card_1"].x == 10
    assert profile.window.title_contains == "Friend App"
```

**Step 2: Write `rta/src/poker_rta/calibration/painter.py`**

```python
"""Calibration doc → PlatformProfile. Pure-data layer; the Qt UI sits on top."""

from __future__ import annotations

from dataclasses import dataclass, field

from poker_rta.profile.model import (
    ROI,
    OCRPreprocess,
    PlatformProfile,
    WindowSelector,
)


@dataclass
class CalibrationDoc:
    name: str
    version: str
    window_title: str
    card_templates_dir: str
    button_templates: dict[str, str]
    rois: dict[str, tuple[int, int, int, int]] = field(default_factory=dict)  # (x, y, w, h)
    ocr: OCRPreprocess = field(default_factory=OCRPreprocess)


def emit_profile(doc: CalibrationDoc) -> PlatformProfile:
    return PlatformProfile(
        name=doc.name,
        version=doc.version,
        window=WindowSelector(title_contains=doc.window_title),
        rois={k: ROI(x=x, y=y, width=w, height=h) for k, (x, y, w, h) in doc.rois.items()},
        card_templates_dir=doc.card_templates_dir,
        button_templates=doc.button_templates,
        ocr=doc.ocr,
    )
```

**Step 3: Write `rta/src/poker_rta/calibration/__init__.py`**

```python
from poker_rta.calibration.painter import CalibrationDoc, emit_profile

__all__ = ["CalibrationDoc", "emit_profile"]
```

**Step 4: Write `rta/tests/calibration/__init__.py`** (empty).

**Step 5: Run — expect pass**

```sh
cd rta && uv run pytest tests/calibration/ -v
```
Expected: 1 passed.

**Step 6: Commit**

```sh
git add rta/src/poker_rta/calibration/ rta/tests/calibration/
git commit -m "feat(rta): calibration doc → profile emitter"
```

---

### Task 10.2: Qt calibration GUI

**Files:**
- Create: `rta/src/poker_rta/calibration/gui.py`

**Step 1: Write `rta/src/poker_rta/calibration/gui.py`**

```python
"""Minimal Qt GUI: open a screenshot, click-drag to define ROIs, pick the
current ROI label from a dropdown, save profile YAML.

Not covered by automated tests — run manually via `poker_rta calibrate`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QMouseEvent, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from poker_rta.calibration.painter import CalibrationDoc, emit_profile
from poker_rta.profile.io import save_profile
from poker_rta.profile.model import REQUIRED_ROIS


class CaptureCanvas(QLabel):
    def __init__(self, doc: CalibrationDoc, current_label: QLineEdit, parent: QWidget) -> None:
        super().__init__(parent)
        self._doc = doc
        self._label = current_label
        self._start: QPoint | None = None
        self._current_rect: QRect | None = None

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self.setPixmap(pixmap)
        self.setFixedSize(pixmap.size())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.position().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._start is not None:
            self._current_rect = QRect(self._start, event.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._start is not None and self._current_rect is not None:
            label = self._label.text().strip()
            if label:
                self._doc.rois[label] = (
                    self._current_rect.x(),
                    self._current_rect.y(),
                    self._current_rect.width(),
                    self._current_rect.height(),
                )
        self._start = None
        self.update()

    def paintEvent(self, event: object) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        for name, (x, y, w, h) in self._doc.rois.items():
            painter.setPen(QPen(Qt.GlobalColor.green, 2))
            painter.drawRect(x, y, w, h)
            painter.drawText(x + 2, y - 4, name)
        if self._current_rect is not None:
            painter.setPen(QPen(Qt.GlobalColor.yellow, 2, Qt.PenStyle.DashLine))
            painter.drawRect(self._current_rect)


class CalibrationWindow(QMainWindow):
    def __init__(self, screenshot: Path) -> None:
        super().__init__()
        self.setWindowTitle("poker_rta — calibration")
        self._doc = CalibrationDoc(
            name="new_profile",
            version="1.0",
            window_title="change me",
            card_templates_dir="templates/new_profile/cards",
            button_templates={},
        )
        self._label_input = QLineEdit()
        self._label_input.setPlaceholderText("ROI label (e.g. hero_card_1)")
        self._preset = QComboBox()
        self._preset.addItems(sorted(REQUIRED_ROIS))
        self._preset.currentTextChanged.connect(self._label_input.setText)

        self._canvas = CaptureCanvas(self._doc, self._label_input, self)
        pixmap = QPixmap(str(screenshot))
        self._canvas.set_pixmap(pixmap)

        save_btn = QPushButton("Save profile YAML…")
        save_btn.clicked.connect(self._save)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Label:"))
        controls.addWidget(self._label_input, 2)
        controls.addWidget(self._preset, 1)
        controls.addWidget(save_btn)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addLayout(controls)
        layout.addWidget(self._canvas)
        self.setCentralWidget(container)

    def _save(self) -> None:
        missing = REQUIRED_ROIS - self._doc.rois.keys()
        if missing:
            self.statusBar().showMessage(f"missing ROIs: {sorted(missing)}", 5000)
            return
        target, _ = QFileDialog.getSaveFileName(self, "Save profile", "profile.yaml", "YAML (*.yaml)")
        if not target:
            return
        save_profile(emit_profile(self._doc), Path(target))
        self.statusBar().showMessage(f"saved {target}", 3000)


def run(screenshot: Path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    win = CalibrationWindow(screenshot)
    win.show()
    app.exec()
```

**Step 2: Smoke test manually**

```sh
cd rta && uv run python -c "from poker_rta.calibration.gui import run; run(__import__('pathlib').Path('tests/fixtures/screenshots/mock_html_preflop.png'))"
```
Expected: GUI opens, you can draw rectangles, each required ROI can be labeled from the dropdown, save produces a valid YAML.

**Step 3: Commit**

```sh
git add rta/src/poker_rta/calibration/gui.py
git commit -m "feat(rta): Qt calibration GUI for new platform profiles"
```

---

## Phase 11 — End-to-End Integration

### Task 11.1: Run loop (capture → CV → tracker → coach → overlay)

**Files:**
- Create: `rta/src/poker_rta/runner.py`
- Create: `rta/tests/test_runner.py`

**Step 1: Test — injectable fakes for capture + coach**

`rta/tests/test_runner.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from poker_rta.cv.pipeline import FrameObservation
from poker_rta.profile import load_profile
from poker_rta.runner import RunnerDeps, run_once


@pytest.mark.asyncio
async def test_run_once_builds_payload_and_calls_coach() -> None:
    profile_path = Path(__file__).parent.parent / "profiles" / "mock_html.yaml"
    profile = load_profile(profile_path)

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    def fake_observe(img: np.ndarray, p: object) -> FrameObservation:
        return FrameObservation(
            hero_cards=("As", "Kd"),
            board=(),
            pot_chips=300,
            hero_stack_chips=9850,
            villain_stack_chips=9700,
            hero_bet_chips=150,
            villain_bet_chips=300,
            hero_is_button=True,
            hero_to_act=True,
            visible_buttons=frozenset({"fold", "call", "raise"}),
        )

    coach = MagicMock()
    coach.create_session = AsyncMock(return_value="s_1")
    coach.create_hand = AsyncMock(return_value="h_1")
    coach.create_decision = AsyncMock(return_value="d_1")
    coach.stream_decision = AsyncMock(return_value=MagicMock(parsed_advice={"action": "raise", "to_bb": 3.0, "rationale": "value"}))

    overlay = MagicMock()

    deps = RunnerDeps(
        grab=lambda: frame,
        observe=fake_observe,
        coach=coach,
        overlay=overlay,
        bb=100,
        starting_stack=10000,
    )
    await run_once(profile, deps)

    coach.create_decision.assert_called_once()
    overlay.show_advice.assert_called_once_with({"action": "raise", "to_bb": 3.0, "rationale": "value"})
```

**Step 2: Write `rta/src/poker_rta/runner.py`**

```python
"""End-to-end run loop.

`run_once` performs one capture → observe → payload → decision → stream →
overlay cycle. `run_loop` is the daemon that polls at the profile's capture
rate and fires `run_once` whenever hero-to-act becomes true.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from poker_rta.client.coach_client import CoachClient
from poker_rta.cv.pipeline import FrameObservation
from poker_rta.overlay.window import AdviceOverlay
from poker_rta.profile.model import PlatformProfile
from poker_rta.state.game_state_builder import build_coach_payload
from poker_rta.state.tracker import StateTracker


@dataclass
class RunnerDeps:
    grab: Callable[[], np.ndarray]
    observe: Callable[[np.ndarray, PlatformProfile], FrameObservation]
    coach: CoachClient
    overlay: AdviceOverlay
    bb: int
    starting_stack: int


async def run_once(profile: PlatformProfile, deps: RunnerDeps) -> None:
    frame = deps.grab()
    obs = deps.observe(frame, profile)
    if not obs.hero_to_act or obs.hero_cards is None:
        return

    tracker = StateTracker(bb=deps.bb, starting_stack=deps.starting_stack)
    tracker.ingest(obs)
    payload = build_coach_payload(tracker, obs)

    session_id = await deps.coach.create_session(mode="live", notes="rta")
    hand_id = await deps.coach.create_hand(session_id=session_id, bb=deps.bb, starting_stack=deps.starting_stack)
    decision_id = await deps.coach.create_decision(
        session_id=session_id, hand_id=hand_id, game_state=payload
    )
    result = await deps.coach.stream_decision(decision_id)
    if result.parsed_advice is not None:
        deps.overlay.show_advice(result.parsed_advice)


async def run_loop(profile: PlatformProfile, deps: RunnerDeps) -> None:
    period = 1.0 / profile.capture_fps
    last_fired_for_cards: tuple[str, str] | None = None
    while True:
        frame = deps.grab()
        obs = deps.observe(frame, profile)
        if obs.hero_to_act and obs.hero_cards and obs.hero_cards != last_fired_for_cards:
            await run_once(profile, deps)
            last_fired_for_cards = obs.hero_cards
        elif not obs.hero_to_act:
            last_fired_for_cards = None
        await asyncio.sleep(period)
```

**Step 3: Run — expect pass**

```sh
cd rta && uv run pytest tests/test_runner.py -v
```
Expected: 1 passed.

**Step 4: Commit**

```sh
git add rta/src/poker_rta/runner.py rta/tests/test_runner.py
git commit -m "feat(rta): end-to-end run loop (capture → CV → coach → overlay)"
```

---

### Task 11.2: CLI entry point

**Files:**
- Create: `rta/src/poker_rta/cli.py`
- Modify: `rta/pyproject.toml` (add `[project.scripts]`)
- Modify: `rta/src/poker_rta/__init__.py`

**Step 1: Write `rta/src/poker_rta/cli.py`**

```python
"""`poker_rta` CLI — `run`, `calibrate`, `replay` subcommands."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from poker_rta.capture.grab import grab_window
from poker_rta.client.coach_client import CoachClient
from poker_rta.cv.cards import CardClassifier
from poker_rta.cv.pipeline import observe_frame
from poker_rta.overlay.window import AdviceOverlay
from poker_rta.profile.io import load_profile
from poker_rta.runner import RunnerDeps, run_loop


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="poker_rta")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="start the real-time loop")
    run.add_argument("--profile", type=Path, required=True)
    run.add_argument("--coach-url", default="http://localhost:8000")
    run.add_argument("--bb", type=int, default=100)
    run.add_argument("--stack", type=int, default=10000)

    cal = sub.add_parser("calibrate", help="launch the calibration GUI")
    cal.add_argument("--screenshot", type=Path, required=True)

    return p


async def _run_cmd(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    classifier = CardClassifier(templates_dir=Path(profile.card_templates_dir))

    from PyQt6.QtWidgets import QApplication  # noqa: PLC0415
    app = QApplication.instance() or QApplication(sys.argv)
    overlay = AdviceOverlay()
    overlay.show()

    async with CoachClient(base_url=args.coach_url) as coach:
        deps = RunnerDeps(
            grab=lambda: grab_window(profile.window),
            observe=lambda img, pf: observe_frame(img, pf, classifier),
            coach=coach,
            overlay=overlay,
            bb=args.bb,
            starting_stack=args.stack,
        )
        await run_loop(profile, deps)
    app.quit()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd == "run":
        return asyncio.run(_run_cmd(args))
    if args.cmd == "calibrate":
        from poker_rta.calibration.gui import run as calibrate_run  # noqa: PLC0415
        calibrate_run(args.screenshot)
        return 0
    raise SystemExit(f"unknown cmd {args.cmd!r}")


if __name__ == "__main__":
    raise SystemExit(main())
```

**Step 2: Register entry point in `rta/pyproject.toml`**

Add:
```toml
[project.scripts]
poker_rta = "poker_rta.cli:main"
```

**Step 3: Re-sync + smoke test**

```sh
cd rta && uv sync && uv run poker_rta --help
```
Expected: argparse help printed.

**Step 4: Commit**

```sh
git add rta/src/poker_rta/cli.py rta/pyproject.toml
git commit -m "feat(rta): CLI entry point with run and calibrate subcommands"
```

---

### Task 11.3: Recording + replay modes

**Files:**
- Create: `rta/src/poker_rta/record.py`
- Create: `rta/tests/test_record.py`

**Step 1: Test**

`rta/tests/test_record.py`:

```python
from __future__ import annotations

from pathlib import Path

import numpy as np

from poker_rta.record import SessionRecorder, replay_session


def test_record_and_replay(tmp_path: Path) -> None:
    rec = SessionRecorder(tmp_path)
    frame = (np.random.rand(10, 10, 3) * 255).astype(np.uint8)
    rec.record(frame)
    rec.record(frame)
    frames = list(replay_session(tmp_path))
    assert len(frames) == 2
    assert frames[0].shape == (10, 10, 3)
```

**Step 2: Write `rta/src/poker_rta/record.py`**

```python
"""Record + replay frames for offline debugging, paper reproducibility, and
deterministic state-tracker tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np


@dataclass
class SessionRecorder:
    root: Path
    _idx: int = field(default=0)

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def record(self, frame: np.ndarray) -> Path:
        path = self.root / f"{self._idx:06d}.png"
        cv2.imwrite(str(path), frame)
        self._idx += 1
        return path


def replay_session(root: Path) -> Iterator[np.ndarray]:
    for p in sorted(root.glob("*.png")):
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is not None:
            yield img
```

**Step 3: Run — expect pass**

```sh
cd rta && uv run pytest tests/test_record.py -v
```
Expected: 1 passed.

**Step 4: Commit**

```sh
git add rta/src/poker_rta/record.py rta/tests/test_record.py
git commit -m "feat(rta): session record + replay"
```

---

## Phase 12 — Evaluation Harness

### Task 12.1: CV accuracy metrics

**Files:**
- Create: `rta/src/poker_rta/evaluation/__init__.py`
- Create: `rta/src/poker_rta/evaluation/metrics.py`
- Create: `rta/tests/evaluation/__init__.py`
- Create: `rta/tests/evaluation/test_metrics.py`

**Step 1: Test**

`rta/tests/evaluation/test_metrics.py`:

```python
from __future__ import annotations

from poker_rta.evaluation.metrics import (
    CVAccuracy,
    evaluate_card_accuracy,
)


def test_card_accuracy_all_correct() -> None:
    got = [("As", "Kd"), ("Qc", "Jh")]
    gold = [("As", "Kd"), ("Qc", "Jh")]
    acc = evaluate_card_accuracy(got, gold)
    assert acc == CVAccuracy(correct=4, total=4, rate=1.0)


def test_card_accuracy_partial() -> None:
    got = [("As", "Kd"), ("Qc", "Jh")]
    gold = [("As", "Kd"), ("Qc", "Jc")]
    acc = evaluate_card_accuracy(got, gold)
    assert acc == CVAccuracy(correct=3, total=4, rate=0.75)
```

**Step 2: Write `rta/src/poker_rta/evaluation/metrics.py`**

```python
"""Evaluation metrics: per-component CV accuracy and end-to-end state
reconstruction accuracy. Used in the paper and as a regression guard.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CVAccuracy:
    correct: int
    total: int
    rate: float


def evaluate_card_accuracy(
    got: list[tuple[str, str]], gold: list[tuple[str, str]]
) -> CVAccuracy:
    correct = sum(
        (g[0] == h[0]) + (g[1] == h[1]) for g, h in zip(got, gold, strict=True)
    )
    total = len(got) * 2
    return CVAccuracy(correct=correct, total=total, rate=correct / total if total else 0.0)
```

**Step 3: Write `rta/src/poker_rta/evaluation/__init__.py`** + empty `tests/evaluation/__init__.py`.

```python
from poker_rta.evaluation.metrics import CVAccuracy, evaluate_card_accuracy

__all__ = ["CVAccuracy", "evaluate_card_accuracy"]
```

**Step 4: Run**

```sh
cd rta && uv run pytest tests/evaluation/ -v
```
Expected: 2 passed.

**Step 5: Commit**

```sh
git add rta/src/poker_rta/evaluation/ rta/tests/evaluation/
git commit -m "feat(rta): CV accuracy metrics"
```

---

### Task 12.2: End-to-end benchmark against recorded mock session

**Files:**
- Create: `rta/scripts/benchmark_mock.py`
- Create: `rta/tests/fixtures/recordings/mock_script/` (frames + ground-truth JSON)

**Step 1: Record ground truth by driving the mock through its 5-step script**

Use the same Playwright setup from Task 2.2, stepping `ArrowRight` between captures. Save frame `000000.png` … `000004.png` + `ground_truth.json` with the expected observation per frame.

**Step 2: Write `rta/scripts/benchmark_mock.py`**

```python
"""Benchmark the CV pipeline against the 5-step mock recording.

Emits CV accuracy (cards, OCR) and end-to-end latency per step. Numbers feed
the paper's 'technical feasibility' section.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from poker_rta.cv.cards import CardClassifier
from poker_rta.cv.pipeline import observe_frame
from poker_rta.profile.io import load_profile
from poker_rta.record import replay_session


def main() -> None:
    root = Path("rta/tests/fixtures/recordings/mock_script")
    profile = load_profile(Path("rta/profiles/mock_html.yaml"))
    classifier = CardClassifier(templates_dir=Path(profile.card_templates_dir))
    gold = json.loads((root / "ground_truth.json").read_text())

    card_hits = 0
    card_total = 0
    num_hits = 0
    num_total = 0
    latencies: list[float] = []

    for i, frame in enumerate(replay_session(root)):
        t0 = time.perf_counter()
        obs = observe_frame(frame, profile, classifier)
        latencies.append((time.perf_counter() - t0) * 1000)

        exp = gold[i]
        for got, want in zip(obs.board, exp["board"], strict=False):
            card_hits += got == want
            card_total += 1
        if obs.hero_cards and exp.get("hero_cards"):
            for got, want in zip(obs.hero_cards, exp["hero_cards"], strict=True):
                card_hits += got == want
                card_total += 1

        for field in ("pot_chips", "hero_stack_chips", "villain_stack_chips"):
            want = exp.get(field)
            got = getattr(obs, field)
            if want is not None:
                num_hits += got == want
                num_total += 1

    print(f"card accuracy: {card_hits}/{card_total} = {card_hits / card_total:.2%}")
    print(f"number accuracy: {num_hits}/{num_total} = {num_hits / num_total:.2%}")
    print(f"median observe latency: {sorted(latencies)[len(latencies) // 2]:.1f} ms")


if __name__ == "__main__":
    main()
```

**Step 3: Run**

```sh
cd rta && uv run python scripts/benchmark_mock.py
```
Expected: ≥ 95% card accuracy, ≥ 95% number accuracy, < 500 ms median observe latency.

**Step 4: Commit**

```sh
git add rta/scripts/benchmark_mock.py rta/tests/fixtures/recordings/
git commit -m "feat(rta): mock-script CV benchmark for paper results"
```

---

## Phase 13 — Detection-Side Analysis (paper content)

### Task 13.1: Timing-entropy analyzer

**Files:**
- Create: `rta/src/poker_rta/detection/__init__.py`
- Create: `rta/src/poker_rta/detection/timing.py`
- Create: `rta/tests/detection/__init__.py`
- Create: `rta/tests/detection/test_timing.py`

**Step 1: Test**

`rta/tests/detection/test_timing.py`:

```python
from __future__ import annotations

import math

from poker_rta.detection.timing import decision_time_entropy


def test_uniform_decisions_have_high_entropy() -> None:
    times_ms = list(range(500, 30000, 200))
    e = decision_time_entropy(times_ms, bins=16)
    assert e > 3.0


def test_bot_like_narrow_timing_has_low_entropy() -> None:
    times_ms = [1500] * 50 + [1550] * 50
    e = decision_time_entropy(times_ms, bins=16)
    assert e < 1.5
    assert not math.isnan(e)
```

**Step 2: Write `rta/src/poker_rta/detection/timing.py`**

```python
"""Behavioral detection: timing-entropy of the player's decisions.

A key RTA tell is suspiciously consistent response latency — read the overlay,
click, repeat. Human players have wide natural variance. This module exposes
entropy and chi-square distance-from-human-prior metrics the paper cites.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable


def decision_time_entropy(times_ms: Iterable[int], bins: int = 16) -> float:
    times = list(times_ms)
    if not times:
        return 0.0
    lo, hi = min(times), max(times)
    width = max(1, (hi - lo) / bins)
    buckets = Counter(min(bins - 1, int((t - lo) / width)) for t in times)
    total = sum(buckets.values())
    return -sum((n / total) * math.log2(n / total) for n in buckets.values())
```

**Step 3: Write `rta/src/poker_rta/detection/__init__.py`** + empty `tests/detection/__init__.py`.

```python
from poker_rta.detection.timing import decision_time_entropy

__all__ = ["decision_time_entropy"]
```

**Step 4: Run — expect pass**

```sh
cd rta && uv run pytest tests/detection/ -v
```
Expected: 2 passed.

**Step 5: Commit**

```sh
git add rta/src/poker_rta/detection/ rta/tests/detection/
git commit -m "feat(rta): decision-timing entropy for behavioral detection analysis"
```

---

### Task 13.2: GTO-convergence fingerprint

**Files:**
- Create: `rta/src/poker_rta/detection/gto.py`
- Create: `rta/tests/detection/test_gto.py`

**Step 1: Test**

`rta/tests/detection/test_gto.py`:

```python
from __future__ import annotations

from poker_rta.detection.gto import convergence_score


def test_identical_actions_score_one() -> None:
    assert convergence_score(["raise"] * 100, ["raise"] * 100) == 1.0


def test_no_overlap_scores_zero() -> None:
    assert convergence_score(["fold"] * 100, ["raise"] * 100) == 0.0


def test_partial_agreement() -> None:
    assert convergence_score(["raise", "fold", "raise"], ["raise", "raise", "raise"]) == pytest_approx(2 / 3)


def pytest_approx(x: float) -> float:
    import pytest
    return pytest.approx(x)  # type: ignore[return-value]
```

**Step 2: Write `rta/src/poker_rta/detection/gto.py`**

```python
"""Convergence score between the player's actual actions and a GTO baseline.

RTA users tend to converge on a single oracle's recommendations across many
spots — detectable as higher-than-population agreement with any given baseline.
Hand-by-hand agreement rate is noisy; aggregate over N ≥ 200 decisions.
"""

from __future__ import annotations

from collections.abc import Sequence


def convergence_score(played: Sequence[str], baseline: Sequence[str]) -> float:
    if len(played) != len(baseline):
        raise ValueError("played and baseline must be the same length")
    if not played:
        return 0.0
    return sum(1 for a, b in zip(played, baseline, strict=True) if a == b) / len(played)
```

**Step 3: Update `rta/src/poker_rta/detection/__init__.py`**

```python
from poker_rta.detection.gto import convergence_score
from poker_rta.detection.timing import decision_time_entropy

__all__ = ["convergence_score", "decision_time_entropy"]
```

**Step 4: Run — expect pass**

```sh
cd rta && uv run pytest tests/detection/ -v
```
Expected: 5 passed.

**Step 5: Commit**

```sh
git add rta/src/poker_rta/detection/ rta/tests/detection/test_gto.py
git commit -m "feat(rta): GTO-convergence fingerprint for RTA detection"
```

---

### Task 13.3: Analysis notebook

**Files:**
- Create: `rta/paper/notebooks/detection_analysis.md` (literate-style notebook; switch to `.ipynb` if preferred)

**Step 1: Write the outline**

`rta/paper/notebooks/detection_analysis.md`:

```markdown
# Behavioral Detection of RTA Users — Analysis

## Setup

We compare four populations of 200 decisions each:
1. Baseline population — anonymized regs, no RTA.
2. Manual study — same players, using PioSolver off-table between sessions.
3. Our RTA — L1 + human-in-the-loop overlay, coach default preset.
4. Pure bot — coach's advice played directly without human delay.

## Timing entropy

Histogram of decision latencies for each population. Show that population 1
has entropy > 3.5 bits, population 3 stays > 2.5 bits (the human click
preserves variance), population 4 collapses to < 1.5 bits.

## GTO-convergence score

Run `convergence_score` of each population's actions vs. the coach's
recommendations across the same 200 spots. Expected: population 3 and 4 score
> 0.85, populations 1 and 2 score ≤ 0.65.

## Conclusion

The RTA is technically indistinguishable from a human with a strong mental
library over a single session. Over N ≥ 200 decisions the GTO-convergence
fingerprint dominates. Mitigation recommendations follow in the paper proper.
```

**Step 2: Commit**

```sh
git add rta/paper/notebooks/
git commit -m "docs(rta): detection analysis notebook outline"
```

---

## Phase 14 — Paper Materials

### Task 14.1: Threat model document

**Files:**
- Create: `rta/paper/threat_model.md`

Write: attack-surface matrix (reuses our earlier conversation's table), defender assumptions (what the poker room can observe), attacker assumptions (user has full control of their machine), scope (HU only for now), limitations (no multi-table, no GTO delta instrumentation for non-HU-coach platforms). Keep under 4 pages.

Commit: `docs(rta): threat model for the research paper`.

---

### Task 14.2: Results writeup template

**Files:**
- Create: `rta/paper/results.md`

Populate with placeholders:
- CV accuracy table (mock_html: card/OCR rates, friend's app: same once calibrated).
- End-to-end latency distribution.
- Detection comparison across populations.
- Discussion: why L1+human-in-the-loop forces defenders onto behavioral ground.
- Future work: anti-fingerprinting (randomized click jitter), VLM replacement of the CV pipeline, generalization to 6-max tables.

Commit: `docs(rta): results writeup template`.

---

## Final — Polish Pass

### Task F.1: Lint + mypy clean

```sh
make rta-lint
```

Fix any issues. Commit: `style(rta): lint and mypy clean-up`.

### Task F.2: Full test sweep

```sh
make rta-test
make test  # also confirms backend + frontend still green
```

### Task F.3: End-to-end demo

1. `make dev` (backend + frontend up).
2. `python3 -m http.server -d rta/demo/mock_html 8080` in another terminal.
3. Position the mock window at known coords; update `rta/profiles/mock_html.yaml` if needed.
4. `cd rta && uv run poker_rta run --profile profiles/mock_html.yaml --coach-url http://localhost:8000`.
5. Press `ArrowRight` in the mock to advance through the script, confirm overlay updates with coach advice on hero-turn frames.

Record a screen capture of the demo for the paper.

---

## Rollback and safety notes

- The `rta/` package is fully isolated from `backend/` and `frontend/` — deleting the directory cleanly removes everything added by this plan.
- No backend schema changes, no alembic migrations. The RTA uses the coach's existing HTTP surface only.
- No API key handling in `rta/`: the coach backend holds the keys. The RTA never talks to Anthropic/OpenAI directly.
- CLAUDE.md gotcha #3 (villain holes leak) is impossible for this pipeline by construction: CV can see face-down cards but cannot decode them; `villain_hole=None` always.

## Out of scope (do NOT build here)

- Input injection (L5). The user clicks themselves. Including this escalates the tool from "overlay" to "bot" and collapses the paper's L1-only argument.
- Multi-tabling. HU only to match the backend and keep state-tracking tractable.
- Memory reads, network MITM, browser-extension DOM scraping. Keep the demo firmly on L1 capture.
- A deploy target on real-money tables. Sandbox only.
