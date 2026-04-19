# EN↔FR Translate Toggle on Advice Output

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add two independent EN/FR toggles to the `AdvicePanel` — one on the `ThinkingBlock` (reasoning stream), one on the `AdviceCard` (final 40-60 word advice). Default display is raw English. First click on a toggle fires a translation request to Haiku 4.5; the result is cached in component state; subsequent clicks toggle instantly without re-fetching.

**Architecture:**
- New stateless `POST /api/translate` endpoint. Body: `{ text, target_lang? }`. Response: `{ translation, cost_usd }`. No DB persistence — translations are ephemeral UI aids, not research data.
- Translation helper lives in a dedicated module (`poker_coach/translation.py`) that calls the Anthropic SDK directly, **not** through the oracle abstraction. The oracle is built for structured tool-call streaming; a one-shot text completion is cleaner and 20 lines.
- Frontend: `useTranslation(text)` hook owns `{ lang, frText, loading, error, toggle }`. Each block (`ThinkingBlock`, `AdviceCard`) instantiates its own hook → independent toggles, independent caches.
- `ThinkingBlock` toggle is disabled until `stream.status` is terminal (`done` / `error`). Translating a live-changing stream would race.

**Tech Stack:** FastAPI + Pydantic, `anthropic` async SDK, React + Vite + TypeScript.

**Load-bearing gotchas to re-read before touching code:**
- `CLAUDE.md` §"Load-bearing gotchas" item 1 — async SDK final-message methods must be `await`ed. For translation we're reading the full `message.content`, so the same trap applies to the response handling. Use the real async SDK methods in both the module and its test fakes.
- Pricing snapshot coupling: the `/api/decisions` path records the pricing snapshot in use. For translation we don't persist, but we still **compute** cost from the same `PricingSnapshot` for the response payload so a future UI could surface it. Don't hardcode rates.
- `anthropic` SDK messages API: the helper calls `messages.create()` (non-streaming — translations are small enough that streaming adds no UX value and complicates error paths).

---

## Task 1: Translation helper module

**Files:**
- Create: `backend/src/poker_coach/translation.py`
- Create: `backend/tests/translation/__init__.py`
- Create: `backend/tests/translation/test_translation.py`

**Step 1: Write the failing test**

Create `backend/tests/translation/test_translation.py`:

```python
"""Translation helper tests.

Use a fake Anthropic client matching the real SDK's async surface.
"""

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from poker_coach.oracle.pricing import PricingSnapshot
from poker_coach.translation import TRANSLATE_SYSTEM_PROMPT, translate_to_french


def _fake_message(text: str, input_tokens: int, output_tokens: int) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class _FakeMessages:
    def __init__(self, reply: SimpleNamespace) -> None:
        self._reply = reply
        self.captured: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.captured.update(kwargs)
        return self._reply


class _FakeClient:
    def __init__(self, reply: SimpleNamespace) -> None:
        self.messages = _FakeMessages(reply)


def test_translate_to_french_returns_translation_and_cost(
    sample_pricing: PricingSnapshot,
) -> None:
    client = _FakeClient(_fake_message("Coucou le monde", input_tokens=50, output_tokens=10))
    result = asyncio.run(
        translate_to_french("Hello world", client=client, pricing=sample_pricing)
    )
    assert result.translation == "Coucou le monde"
    assert result.cost_usd > 0
    assert client.messages.captured["system"] == TRANSLATE_SYSTEM_PROMPT
    assert client.messages.captured["messages"] == [
        {"role": "user", "content": "Hello world"},
    ]


def test_translate_system_prompt_preserves_poker_jargon() -> None:
    # Terms that must explicitly stay untranslated must be listed so the
    # model doesn't French-ify "3-bet" into "3-mise".
    for term in ["3-bet", "check-raise", "polarized", "villain", "hero"]:
        assert term in TRANSLATE_SYSTEM_PROMPT


def test_translate_rejects_empty_text(sample_pricing: PricingSnapshot) -> None:
    client = _FakeClient(_fake_message("", 0, 0))
    with pytest.raises(ValueError, match="empty"):
        asyncio.run(translate_to_french("", client=client, pricing=sample_pricing))
```

**Step 2: Run it to verify it fails**

Run: `cd backend && uv run pytest tests/translation/ -v`

Expected: FAIL — module doesn't exist.

**Step 3: Create `backend/src/poker_coach/translation.py`**

```python
"""Lightweight EN→FR translation helper.

Deliberately separate from the oracle abstraction. The oracle is built
for structured tool-call streaming with event parsing; a one-shot text
translation with Haiku 4.5 is cleaner as a direct SDK call.

Cost is computed from the same PricingSnapshot used for decisions so
pricing updates propagate without code changes here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from poker_coach.oracle.pricing import PricingSnapshot

TRANSLATE_MODEL_ID = "claude-haiku-4-5-20251001"

TRANSLATE_SYSTEM_PROMPT = (
    "You are an EN→FR translator specialized for heads-up No-Limit Hold'em poker content. "
    "Translate the user's text to natural, fluent French. "
    "Keep these poker jargon terms EXACTLY as-is (do not translate): "
    "3-bet, 4-bet, 5-bet, check-raise, c-bet, polarized, range, board, flop, turn, river, "
    "villain, hero, BB, SB, limp, open, call, fold, raise, bet, all-in, GTO, EV, mix. "
    "Preserve punctuation, line breaks, and any markdown-like structure. "
    "Output ONLY the translation — no preamble, no commentary, no quotes."
)


class _AsyncMessages(Protocol):
    async def create(self, **kwargs: Any) -> Any: ...


class _AsyncClient(Protocol):
    messages: _AsyncMessages


@dataclass(frozen=True)
class TranslationResult:
    translation: str
    cost_usd: float


async def translate_to_french(
    text: str,
    *,
    client: _AsyncClient,
    pricing: PricingSnapshot,
    max_tokens: int = 4096,
) -> TranslationResult:
    if not text.strip():
        raise ValueError("text is empty")

    message = await client.messages.create(
        model=TRANSLATE_MODEL_ID,
        max_tokens=max_tokens,
        system=TRANSLATE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )

    # Anthropic returns a list of content blocks; concatenate text blocks.
    parts = [b.text for b in message.content if getattr(b, "type", None) == "text"]
    translation = "".join(parts).strip()

    rate = pricing.for_model(TRANSLATE_MODEL_ID)
    cost = (
        message.usage.input_tokens * rate.input_per_1k / 1000.0
        + message.usage.output_tokens * rate.output_per_1k / 1000.0
    )
    return TranslationResult(translation=translation, cost_usd=cost)
```

**Step 4: Verify the rate lookup actually works**

Run: `grep -n 'claude-haiku-4-5' backend/config/pricing.yaml`

Expected: an entry exists. If not (unlikely — Haiku is the existing fast preset), add one matching the other Claude entries' structure.

**Step 5: Run tests**

Run: `cd backend && uv run pytest tests/translation/ -v`

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/src/poker_coach/translation.py \
        backend/tests/translation/__init__.py \
        backend/tests/translation/test_translation.py
git commit -m "feat(translation): add EN→FR helper using Haiku 4.5 with poker jargon preservation"
```

---

## Task 2: `/api/translate` route + wiring

**Files:**
- Create: `backend/src/poker_coach/api/routes/translate.py`
- Create: `backend/tests/api/test_translate.py`
- Modify: `backend/src/poker_coach/api/app.py` (register router)
- Modify: `backend/src/poker_coach/api/deps.py` (add optional `get_anthropic_client` dep)

**Background:** production wiring builds one shared `AsyncAnthropic` client at app startup and stashes it on `app.state`. Tests inject a fake client the same way the oracle factory is injected today. The pattern mirrors `oracle_factory`.

**Step 1: Extend `deps.py`**

Append to `backend/src/poker_coach/api/deps.py`:

```python
def get_anthropic_client(request: Request) -> Any:
    client = getattr(request.app.state, "anthropic_client", None)
    if client is None:
        raise RuntimeError(
            "anthropic_client not configured on app.state; "
            "production wiring should create one at startup."
        )
    return client
```

**Step 2: Write the failing test**

Create `backend/tests/api/test_translate.py`:

```python
"""Translate route tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

from poker_coach.api.app import create_app


def _fake_message(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
    )


class _FakeMessages:
    def __init__(self, reply_text: str = "bonjour le monde") -> None:
        self._reply_text = reply_text
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return _fake_message(self._reply_text)


class _FakeClient:
    def __init__(self, reply_text: str = "bonjour le monde") -> None:
        self.messages = _FakeMessages(reply_text)


def _build_app(fake_client: _FakeClient) -> Any:
    app = create_app(
        oracle_factory=SimpleNamespace(for_spec=lambda spec: None),  # unused
        sweeper_interval_seconds=0,
    )

    @app.router.on_event("startup")  # type: ignore[deprecated]
    def _attach_fake() -> None:  # pragma: no cover - wired via TestClient startup
        app.state.anthropic_client = fake_client

    # TestClient runs the startup hooks automatically.
    app.state.anthropic_client = fake_client
    return app


def test_translate_returns_translation_and_cost() -> None:
    fake = _FakeClient("bonjour le monde")
    app = _build_app(fake)
    with TestClient(app) as client:
        resp = client.post("/api/translate", json={"text": "hello world"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["translation"] == "bonjour le monde"
    assert body["cost_usd"] > 0
    assert fake.messages.calls[0]["messages"] == [
        {"role": "user", "content": "hello world"},
    ]


def test_translate_rejects_empty_text() -> None:
    fake = _FakeClient()
    app = _build_app(fake)
    with TestClient(app) as client:
        resp = client.post("/api/translate", json={"text": ""})
    assert resp.status_code == 422


def test_translate_rejects_oversize_text() -> None:
    fake = _FakeClient()
    app = _build_app(fake)
    with TestClient(app) as client:
        resp = client.post("/api/translate", json={"text": "x" * 50_001})
    assert resp.status_code == 413
```

Adapt the app-building helper to match existing test patterns in `tests/api/` (use the `api_app` fixture if it accepts a client override; otherwise build directly as above).

**Step 3: Run to verify failure**

Run: `cd backend && uv run pytest tests/api/test_translate.py -v`

Expected: FAIL — route doesn't exist.

**Step 4: Create the route**

Create `backend/src/poker_coach/api/routes/translate.py`:

```python
"""POST /api/translate — one-shot EN→FR translation for UI display.

Stateless. No persistence. Translations are ephemeral UI aids, not
research data; logging them would bloat the decisions table and invite
questions about which "text" was authoritative for replay.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from poker_coach.api.deps import get_anthropic_client, get_pricing
from poker_coach.oracle.pricing import PricingSnapshot
from poker_coach.translation import translate_to_french

router = APIRouter()

_MAX_CHARS = 50_000


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    target_lang: str = "fr"


class TranslateResponse(BaseModel):
    translation: str
    cost_usd: float


@router.post("/translate", response_model=TranslateResponse)
async def translate(
    body: TranslateRequest,
    client: Annotated[Any, Depends(get_anthropic_client)],
    pricing: Annotated[PricingSnapshot, Depends(get_pricing)],
) -> TranslateResponse:
    if body.target_lang != "fr":
        raise HTTPException(
            status_code=400,
            detail=f"unsupported target_lang: {body.target_lang}",
        )
    if len(body.text) > _MAX_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"text exceeds {_MAX_CHARS} character limit",
        )
    try:
        result = await translate_to_french(
            body.text, client=client, pricing=pricing
        )
    except Exception as exc:  # SDK / network / auth errors all bubble up as 502
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TranslateResponse(
        translation=result.translation,
        cost_usd=result.cost_usd,
    )
```

**Step 5: Register the route in `app.py`**

Add to the imports:

```python
from poker_coach.api.routes import translate
```

Add after the other `include_router` calls:

```python
app.include_router(translate.router, prefix="/api")
```

**Step 6: Wire the production Anthropic client at startup**

In `create_app` — inside the `lifespan` context manager, before `yield` — add:

```python
from anthropic import AsyncAnthropic

app.state.anthropic_client = AsyncAnthropic()
```

Add the import at the top of `app.py`. The `AsyncAnthropic()` constructor reads `ANTHROPIC_API_KEY` from env; if missing it raises lazily on first request, matching the rest of the codebase's behavior.

**Step 7: Run the tests**

Run: `cd backend && uv run pytest tests/api/test_translate.py tests/translation/ -v`

Expected: PASS.

Run: `cd backend && make test`

Expected: full suite green.

**Step 8: Commit**

```bash
git add backend/src/poker_coach/api/routes/translate.py \
        backend/src/poker_coach/api/app.py \
        backend/src/poker_coach/api/deps.py \
        backend/tests/api/test_translate.py
git commit -m "feat(api): add /api/translate endpoint backed by Haiku 4.5"
```

---

## Task 3: Frontend API client

**Files:**
- Modify: `frontend/src/api/client.ts`

**Step 1: Add the client function**

Append to `frontend/src/api/client.ts`:

```ts
export async function translateText(text: string): Promise<{
  translation: string;
  cost_usd: number;
}> {
  return postJSON("/api/translate", { text });
}
```

**Step 2: Typecheck**

Run: `cd frontend && npm run typecheck`

Expected: PASS.

**Step 3: Commit (bundled with Task 4)**

---

## Task 4: `useTranslation` hook

**Files:**
- Create: `frontend/src/api/useTranslation.ts`
- Create: `frontend/src/api/useTranslation.test.ts`

**Step 1: Write the failing test**

Create `frontend/src/api/useTranslation.test.ts`:

```ts
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useTranslation } from "./useTranslation";
import * as client from "./client";

describe("useTranslation", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("starts in EN with no cached translation", () => {
    const { result } = renderHook(() => useTranslation("hello"));
    expect(result.current.lang).toBe("en");
    expect(result.current.frText).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it("fetches FR on first toggle and caches the result", async () => {
    const spy = vi
      .spyOn(client, "translateText")
      .mockResolvedValue({ translation: "bonjour", cost_usd: 0.001 });

    const { result } = renderHook(() => useTranslation("hello"));
    act(() => {
      result.current.toggle();
    });

    await waitFor(() => expect(result.current.lang).toBe("fr"));
    expect(result.current.frText).toBe("bonjour");
    expect(spy).toHaveBeenCalledTimes(1);

    // Toggle back to EN, then to FR again — no re-fetch.
    act(() => result.current.toggle());
    expect(result.current.lang).toBe("en");
    act(() => result.current.toggle());
    expect(result.current.lang).toBe("fr");
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("resets cache when text changes", async () => {
    vi.spyOn(client, "translateText")
      .mockResolvedValueOnce({ translation: "bonjour", cost_usd: 0.001 })
      .mockResolvedValueOnce({ translation: "salut", cost_usd: 0.001 });

    const { result, rerender } = renderHook(
      ({ text }: { text: string }) => useTranslation(text),
      { initialProps: { text: "hello" } }
    );

    act(() => result.current.toggle());
    await waitFor(() => expect(result.current.frText).toBe("bonjour"));

    rerender({ text: "hi" });
    expect(result.current.lang).toBe("en");
    expect(result.current.frText).toBeNull();

    act(() => result.current.toggle());
    await waitFor(() => expect(result.current.frText).toBe("salut"));
  });

  it("reverts to EN on error", async () => {
    vi.spyOn(client, "translateText").mockRejectedValue(new Error("boom"));

    const { result } = renderHook(() => useTranslation("hello"));
    act(() => result.current.toggle());

    await waitFor(() => expect(result.current.error).toBe("boom"));
    expect(result.current.lang).toBe("en");
    expect(result.current.frText).toBeNull();
  });
});
```

**Step 2: Run the test**

Run: `cd frontend && npm test -- --run useTranslation`

Expected: FAIL — hook doesn't exist.

**Step 3: Create the hook**

Create `frontend/src/api/useTranslation.ts`:

```ts
import { useCallback, useEffect, useRef, useState } from "react";
import { translateText } from "./client";

export type TranslationState = {
  lang: "en" | "fr";
  frText: string | null;
  loading: boolean;
  error: string | null;
  toggle: () => void;
};

export function useTranslation(text: string): TranslationState {
  const [lang, setLang] = useState<"en" | "fr">("en");
  const [frText, setFrText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset whenever the source text identity changes (new decision arrives).
  const prevTextRef = useRef(text);
  useEffect(() => {
    if (prevTextRef.current !== text) {
      prevTextRef.current = text;
      setLang("en");
      setFrText(null);
      setLoading(false);
      setError(null);
    }
  }, [text]);

  // Abort in-flight fetch on unmount or text change.
  const abortRef = useRef<AbortController | null>(null);
  useEffect(() => () => abortRef.current?.abort(), []);

  const toggle = useCallback(() => {
    if (loading) return;

    if (lang === "fr") {
      setLang("en");
      return;
    }
    if (frText !== null) {
      setLang("fr");
      return;
    }
    // First request: fetch FR lazily.
    setLoading(true);
    setError(null);
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    translateText(text)
      .then((r) => {
        setFrText(r.translation);
        setLang("fr");
      })
      .catch((e: Error) => {
        setError(e.message);
        setLang("en");
      })
      .finally(() => setLoading(false));
  }, [lang, frText, loading, text]);

  return { lang, frText, loading, error, toggle };
}
```

**Step 4: Run tests**

Run: `cd frontend && npm test -- --run useTranslation`

Expected: PASS.

**Step 5: Commit (bundles Task 3 + Task 4)**

```bash
git add frontend/src/api/client.ts \
        frontend/src/api/useTranslation.ts \
        frontend/src/api/useTranslation.test.ts
git commit -m "feat(frontend): add translateText client + useTranslation hook with lazy FR fetch"
```

---

## Task 5: Integrate toggles in `AdvicePanel`

**Files:**
- Modify: `frontend/src/components/AdvicePanel.tsx`

**Step 1: Add a shared toggle button component**

Inside `AdvicePanel.tsx`, add a small reusable button:

```tsx
function LangToggle({
  state,
  disabled = false,
}: {
  state: TranslationState;
  disabled?: boolean;
}) {
  const { lang, loading, error, toggle } = state;
  return (
    <button
      type="button"
      data-testid="lang-toggle"
      disabled={disabled || loading}
      onClick={toggle}
      className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border border-white/10 text-stone-300 hover:text-stone-100 hover:border-white/30 transition disabled:opacity-40 disabled:cursor-not-allowed"
      title={error ? `translation error: ${error}` : undefined}
    >
      {loading ? "…" : error ? "!" : lang === "fr" ? "FR" : "EN"}
    </button>
  );
}
```

Import `TranslationState` and `useTranslation` from `../api/useTranslation` at the top.

**Step 2: Wire the toggle into `ThinkingBlock`**

Inside `ThinkingBlock`, add:

```tsx
const translation = useTranslation(stream.reasoning);
const displayedReasoning =
  translation.lang === "fr" && translation.frText !== null
    ? translation.frText
    : stream.reasoning;
```

Disable the toggle while the stream is still live:

```tsx
const streamDone = stream.status === "done" || stream.status === "error";
```

Update the header to include the toggle (to the right of the char count):

```tsx
<div className="flex items-center justify-between">
  <button
    type="button"
    data-testid="thinking-toggle"
    onClick={() => setUserOverride(!collapsed)}
    className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-stone-400 hover:text-stone-200 transition"
  >
    <span className="font-mono">{collapsed ? "▶" : "▼"}</span>
    <span>Thinking</span>
    {live && <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />}
    <span className="opacity-50 normal-case tracking-normal">
      {stream.reasoning.length} chars
    </span>
  </button>
  <LangToggle state={translation} disabled={!streamDone} />
</div>
```

And render `displayedReasoning` instead of `stream.reasoning` inside the `<pre>`.

**Step 3: Wire the toggle into `AdviceCard`**

Inside `AdviceCard`:

```tsx
const translation = useTranslation(advice.reasoning);
const displayedReasoning =
  translation.lang === "fr" && translation.frText !== null
    ? translation.frText
    : advice.reasoning;
```

Add the toggle to the card header, next to the confidence badge:

```tsx
<div className="flex items-center gap-2">
  <LangToggle state={translation} />
  <span
    className={`px-2 py-0.5 rounded text-[10px] border uppercase tracking-wider ${confidenceStyle}`}
  >
    {advice.confidence}
  </span>
</div>
```

And render `{displayedReasoning}` in the paragraph at the bottom.

**Step 4: Typecheck + tests**

Run: `cd frontend && npm run typecheck && npm test -- --run`

Expected: PASS. Existing `AdvicePanel` tests (if any) assert on structure — the new DOM node has `data-testid="lang-toggle"` so existing selectors for `advice-card` / `thinking-toggle` still match.

**Step 5: Manual smoke**

Run: `make dev`.

1. Play a hand, request advice.
2. Wait for stream to finish.
3. Click the EN badge on the advice card → should become FR with translated reasoning.
4. Click again → instant EN (no network request in DevTools).
5. Click again → instant FR.
6. Click the EN badge on the thinking block → translated thinking text appears.
7. Start a new decision → both toggles reset to EN automatically.
8. Verify the thinking-block toggle is disabled (opacity-40) while `status === "streaming"`.

**Step 6: Commit**

```bash
git add frontend/src/components/AdvicePanel.tsx
git commit -m "feat(frontend): add EN/FR toggles to thinking block and advice card"
```

---

## Task 6: Full-stack verification

**Step 1: Full test suite**

Run: `make test`

Expected: all green.

**Step 2: Lint**

Run: `make lint`

Expected: clean.

**Step 3: E2E**

Run: `make e2e`

Expected: existing Playwright flows still pass. No new E2E tests added — the feature is covered by backend unit tests + frontend hook tests + manual smoke.

**Step 4: Commit only if cleanup surfaced**

If all green with no diffs, no commit.

---

## Post-merge follow-ups (out of scope)

- **Persist translations on the decisions row**: if users ask for translations to survive reload on the History page, add a `translations_json` TEXT column and have the `/api/translate` handler optionally write-through when a `decision_id` is supplied.
- **Surface translation cost in the UI**: the response already carries `cost_usd`. Could be summed with the decision cost in `CostFooter`.
- **Support other target languages**: the API already carries `target_lang`. Currently only `fr` is accepted; extending is a one-line table of system prompts.
- **Streaming translation**: for very long thinking blocks, stream the translation back. Unnecessary for current text sizes (~5k chars translated in ~2s).
