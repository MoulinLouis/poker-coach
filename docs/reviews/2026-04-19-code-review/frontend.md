# Frontend Review

## Scope

React 18 + TypeScript + Vite + Tailwind 4. Reviewed: `App.tsx`, `main.tsx`, 12 components, `components/actionBar/sizing.ts`, 4 routes, 1 hook (`useHotkeys`), all of `api/` (`client`, `useTranslation`, `useAdviceStream`, `types`). Matching test files were skimmed to confirm intent; e2e tests were excluded.

Top themes:
1. **One route (`SpotAnalysis`) uses inline styles and hex colors** while the rest of the app is Tailwind 4 — visually and structurally inconsistent.
2. **Small utilities duplicated across files** — `parseHole`, suit glyph/color mappings, agreement-rate calc.
3. **Observability gaps in streams/hooks** — parse errors get generic messages, cost polling never backs off on failure.

Note: per CLAUDE.md, `CardPicker` is intentionally uncontrolled — findings below do not touch that pattern.

---

### [F-1] SpotAnalysis uses inline styles instead of Tailwind
- **File:** `frontend/src/routes/SpotAnalysis.tsx:173-367`
- **Severity:** High
- **Category:** polish
- **Problem:** The entire route is styled via inline `style={{}}` objects with raw hex colors (`#ddd`, `#888`, `crimson`, `#444`, `#666`, `#f6f6f6`). Every other route and component uses Tailwind 4 classes (`bg-stone-900`, `ring-1 ring-white/5`, etc.). Makes maintenance harder and looks visually off when placed beside the rest of the app.
- **Suggested change:** Convert to Tailwind class-by-class. Reference `SetupPanel.tsx` for form styles. Concrete replacements: `border: "1px solid #ddd"` → `ring-1 ring-white/5`; `color: "crimson"` → `text-red-500`; `background: "#f6f6f6"` → `bg-stone-900`. Do this as a single focused commit so diff review is straightforward.
- **Breaking risk:** None — visual-only. Existing tests (`SpotAnalysis` isn't covered by unit tests; any e2e selectors use text content, not styles) are unaffected.

---

### [F-2] `useTranslation` resets four state pieces conditionally
- **File:** `frontend/src/api/useTranslation.ts:18-25`
- **Severity:** Low
- **Category:** over-abstraction
- **Problem:** When `text` changes, the hook conditionally resets each of `lang`, `frText`, `loading`, `error` via four separate `if` + `set*` calls. Verbose; easy to drift when a fifth piece of state is added.
- **Suggested change:** Reset unconditionally on text change — the parent call-site already re-renders:
  ```ts
  if (prevTextRef.current !== text) {
      prevTextRef.current = text;
      setLang("en");
      setFrText(null);
      setLoading(false);
      setError(null);
  }
  ```
  Or consolidate the four fields into a single `useState<TranslationState>` record.
- **Breaking risk:** Low — `useTranslation.test.ts` covers the lifecycle. Verify `mountedRef` pattern (CLAUDE.md gotcha #1 for frontend) is unchanged.

---

### [F-3] `CostFooter` polling never backs off on failure
- **File:** `frontend/src/components/CostFooter.tsx:11-27`
- **Severity:** Low
- **Category:** efficiency
- **Problem:** The `setInterval` keeps firing even if `/api/cost` returns errors indefinitely. The catch block is a silent `/* swallow */`. Sessions left open on a broken backend generate steady noise.
- **Suggested change:** Track a failure counter in a ref; pause polling after 3 consecutive failures and resume on user action (e.g., route change or a retry button). Simpler alternative: exponential backoff capped at 60s.
- **Breaking risk:** None — improves behavior; no test depends on aggressive polling.

---

### [F-4] `parseHole` duplicated in 3 places
- **File:** `frontend/src/routes/LiveCoach.tsx:27-30`, `frontend/src/routes/SpotAnalysis.tsx:95-99`, `frontend/src/components/SetupPanel.tsx:13-16`
- **Severity:** Nit
- **Category:** duplication
- **Problem:** Three near-identical definitions of "parse a 4-char hole string into `[c1, c2] | null`".
- **Suggested change:** Create `frontend/src/utils/cards.ts` with a single exported `parseHole`. Import in all three.
- **Breaking risk:** None.

---

### [F-5] Suit glyphs + colors duplicated between BoardPicker and CardPicker
- **File:** `frontend/src/components/BoardPicker.tsx:150-151`, `frontend/src/components/CardPicker.tsx:6-11`, `frontend/src/components/PlayingCard.tsx` (`SUITS` object)
- **Severity:** Medium
- **Category:** duplication
- **Problem:** BoardPicker inlines ternaries for suit→glyph and suit→color; CardPicker has `SUIT_LABEL`; PlayingCard has `SUITS`. Three sources of truth for the same map.
- **Suggested change:** Pick PlayingCard's `SUITS` as the canonical export (or hoist to `utils/cards.ts` next to `parseHole`). Import it in both pickers, delete the inline ternaries and the second record.
- **Breaking risk:** None — identical render output.

---

### [F-6] `AdvicePanel` spins up two independent translation hooks
- **File:** `frontend/src/components/AdvicePanel.tsx:92-96, 151-162`
- **Severity:** Low
- **Category:** efficiency
- **Problem:** `ThinkingBlock` and `AdviceCard` each call `useTranslation(...)` with overlapping inputs. When both are rendered, two translation state machines spin up and can even hit the backend twice for the same text.
- **Suggested change:** Hoist the translation call one level up into `AdvicePanel` and pass `displayedReasoning` down as a prop. Keeps a single source of truth for the current language and avoids duplicate fetches.
- **Breaking risk:** Low — verify `AdvicePanel.test.tsx` still passes. The `mountedRef` guard inside `useTranslation` is safe across this refactor.

---

### [F-7] Double-clamp on bet sizing input is defensive and acceptable
- **File:** `frontend/src/components/ActionBar.tsx:73, 115`
- **Severity:** Nit
- **Category:** note
- **Problem:** `sizeChips` is clamped in render (display) and again in the `onSetChips` callback. Two clamps is one more than strictly required.
- **Suggested change:** Leave as-is. The tests (`ActionBar.test.tsx` L174-209 for stale-size clamping) benefit from both call-site and display-side guards. Changing this has more risk than reward.
- **Breaking risk:** Medium if removed — tests assert the clamped output on size changes.

---

### [F-8] `SpotAnalysis` remounts `useColumn` hooks on every preset toggle
- **File:** `frontend/src/routes/SpotAnalysis.tsx:71-74`
- **Severity:** Medium
- **Category:** efficiency
- **Problem:** The current `selected` array drives column hooks; when a preset toggles, the number of hooks changes, which violates React's rules-of-hooks across renders. The current code compensates by resetting the column set (L94) — but this is fragile. If someone adds a new state branch that doesn't reset the columns, hook count will mismatch and React will crash the route.
- **Suggested change:** Allocate a fixed-size array of column slots (`N_SLOTS = 3` or whatever the UI max is) and call the hooks unconditionally with an optional preset. Skip rendering empty slots. That way hook count is stable and selection becomes pure data.
- **Breaking risk:** Medium — changes the route's state model. Add a test (vitest) that toggles presets in sequence and confirms no React hook-count error.

---

### [F-9] Villain-profile toggle inlined in `SetupPanel`
- **File:** `frontend/src/components/SetupPanel.tsx:70-87`
- **Severity:** Nit
- **Category:** over-abstraction
- **Problem:** A two-button `reg|unknown` toggle is inlined. Nothing wrong; only SetupPanel uses it today.
- **Suggested change:** Leave unless a second caller appears. Resist early abstraction.
- **Breaking risk:** None.

---

### [F-10] Street label capitalized via `charAt(0).toUpperCase() + slice(1)`
- **File:** `frontend/src/components/PokerTable.tsx:26`
- **Severity:** Nit
- **Category:** polish
- **Problem:** Fine for single-word street names; fragile if a street string ever contains a hyphen (unlikely given the backend `Literal`).
- **Suggested change:** Skip. Revisit only if the `Street` Literal grows a compound value.
- **Breaking risk:** None.

---

### [F-11] Stream parse errors logged as `parse error: ${String(err)}`
- **File:** `frontend/src/api/useAdviceStream.ts:92-97`
- **Severity:** Medium
- **Category:** quality
- **Problem:** If the backend sends malformed JSON on an SSE frame, the user sees `parse error: SyntaxError: ...` with no data context. Per CLAUDE.md we log `status="invalid_response"` on the backend — the frontend should mirror by at least capturing the raw event.
- **Suggested change:** Keep the user-facing message minimal but log richer info in dev:
  ```ts
  if (import.meta.env.DEV) {
      console.error("[advice-stream] malformed frame", { event, raw: rawPayload, err });
  }
  ```
  Capture `rawPayload` (first ~200 chars) in the error object so the user's copy-paste bug report is useful.
- **Breaking risk:** None — no test asserts the exact error message shape.

---

### [F-12] Amount parsing pattern duplicated in SpotAnalysis vs ActionBar
- **File:** `frontend/src/routes/SpotAnalysis.tsx:370-381`, `frontend/src/components/ActionBar.tsx:307-314`
- **Severity:** Low
- **Category:** duplication
- **Problem:** Both compute `parseFloat(value) * bb` and null-check. Not identical but very close; drift-prone.
- **Suggested change:** Extract `parseAmountInput(input: string, bb: number): number | null` in `utils/cards.ts` or `utils/bet.ts`. Reuse.
- **Breaking risk:** None.

---

### [F-13] `History` filter state uses separate `useState` pieces with spread on change
- **File:** `frontend/src/routes/History.tsx:7-11`
- **Severity:** Low
- **Category:** quality
- **Problem:** Three filter fields are bundled into a single state record but each change does `setFilters((f) => ({ ...f, ...}))`. Readable, slightly noisy.
- **Suggested change:** Leave as-is. A `useReducer` wouldn't earn its weight here. Skip.
- **Breaking risk:** None.

---

### [F-14] `Board` wraps each card in a redundant flex div
- **File:** `frontend/src/components/Board.tsx:6-16`
- **Severity:** Nit
- **Category:** polish
- **Problem:** Each board slot renders inside `<div className="flex items-center">`; the parent `Board` is already `flex gap-2` and the child is block-level, so the wrapper adds nothing.
- **Suggested change:** Render the card or dashed placeholder directly:
  ```tsx
  {cards[i] ? <PlayingCard code={cards[i]} size="lg" /> : <div className="w-20 h-28 rounded-md border-2 border-dashed border-white/15" />}
  ```
  No flex wrapper. Layout unchanged.
- **Breaking risk:** None — visual snapshot identical.

---

### [F-15] Agreement-rate formula duplicated
- **File:** `frontend/src/routes/LiveCoach.tsx:258-265`, `frontend/src/components/HandSummary.tsx:12-15`
- **Severity:** Nit
- **Category:** duplication
- **Problem:** `Math.round(((total - diverged) / total) * 100)` in two places.
- **Suggested change:** Extract `agreementPct(total, diverged)` in `utils/agreement.ts`. Handle `total === 0` explicitly (currently both paths would `NaN`).
- **Breaking risk:** None.

---

### [F-16] `SetupPanel` effective-stack input has no min/max/validation
- **File:** `frontend/src/components/SetupPanel.tsx:38-45`
- **Severity:** Low
- **Category:** quality
- **Problem:** Plain `<input type="number">` lets users submit 0, negative, or absurd values; the backend rejects but the UX is silent until error.
- **Suggested change:** Add `min={1}` to the input; on change, clamp or surface an inline helper text when invalid. Keep it minimal — one-line validation, no dependency.
- **Breaking risk:** None.

---

### [F-17] Prompts `bumpVersion` regex is fragile
- **File:** `frontend/src/routes/Prompts.tsx:194-198`
- **Severity:** Low
- **Category:** quality
- **Problem:** `^v(\d+)$` matches `v1`, `v2` but fails silently on `v1-alpha` or `v2.0`, returning a fallback `${current}_next` string that won't pass the backend's version regex.
- **Suggested change:** Either narrow the UI to only allow `v\d+` versions (reject suffixed versions in the input) or match with `^v(\d+)` (no end anchor) and preserve the suffix. Add a test.
- **Breaking risk:** Low — affects new-version creation only.

---

### [F-18] `LangToggle` disabled reason not surfaced to user
- **File:** `frontend/src/components/AdvicePanel.tsx:114, 128-149`
- **Severity:** Low
- **Category:** a11y
- **Problem:** The button disables for two distinct reasons (`loading` or `disabled`/terminal) but no tooltip distinguishes. Keyboard users see "disabled" without context.
- **Suggested change:** Add a conditional `title`:
  ```tsx
  title={loading ? "Translation in progress…" : disabled ? "Translation locked on terminal state" : "Toggle language"}
  ```
- **Breaking risk:** None.

---

### [F-19] `PlayingCard` silently renders a red div for invalid card codes
- **File:** `frontend/src/components/PlayingCard.tsx:33-46`
- **Severity:** Low
- **Category:** quality
- **Problem:** Passing an invalid code like `"Zz"` produces a red div with `data-invalid="true"` but no console warning. Dev mistakes are invisible.
- **Suggested change:** In dev only, `console.warn("[PlayingCard] invalid code", code)`. Production behavior unchanged.
- **Breaking risk:** None.

---

### [F-20] Prompts editor has no unsaved-changes guard or token-count hint
- **File:** `frontend/src/routes/Prompts.tsx:160-166`
- **Severity:** Low
- **Category:** quality
- **Problem:** Per CLAUDE.md gotcha #8, Anthropic system prompts must stay ≥1024 tokens (2048 on Haiku) or caching silently breaks. The Prompts editor has no hint tracking token count; accidental trims kill the cache without warning.
- **Suggested change:** Rough token estimate via `text.length / 4` (acceptable heuristic); render `Estimated tokens: ~1140` below the textarea with a warning color below 1100. Add a `beforeunload` guard when the textarea is dirty.
- **Breaking risk:** None.

---

### [F-21] `CostFooter` row key uses concatenated string
- **File:** `frontend/src/components/CostFooter.tsx:76`
- **Severity:** Nit
- **Category:** polish
- **Problem:** `key={`${row.model_id}/${row.reasoning_effort}`}` is fine, just noted.
- **Suggested change:** Leave as-is unless the backend starts returning a stable row ID.
- **Breaking risk:** None.

---

### [F-22] `ActionBar` sizing-slider aria-labels mix units
- **File:** `frontend/src/components/ActionBar.tsx:266-276, 247, 283`
- **Severity:** Low
- **Category:** a11y
- **Problem:** The range input announces "chips" while the +/- buttons announce "1bb". Screen reader users get inconsistent units.
- **Suggested change:** Standardize on "big blinds" in labels and keep the underlying value-in-chips internal. Add `aria-valuetext` formatting `${chipsToBB(value)} bb` to the slider so the announcement matches the visual display.
- **Breaking risk:** None.

---

### [F-23] `useAdviceStream` cleanup correctly aborts on unmount
- **File:** `frontend/src/api/useAdviceStream.ts:38-42, 115-117`
- **Severity:** N/A
- **Category:** note
- **Problem:** Checked explicitly — cleanup path is correct.
- **Suggested change:** None. Flagged only to confirm the `mountedRef` + abort pattern works given CLAUDE.md's prior bug about latched refs under StrictMode.
- **Breaking risk:** N/A.

---

### [F-24] Prompts route auto-selects last version as "active"
- **File:** `frontend/src/routes/Prompts.tsx:19-21, 87-88`
- **Severity:** Nit
- **Category:** quality
- **Problem:** `versions.at(-1)` is treated as "latest". Assumes git-linear version ordering in the list response. Fine today; worth noting.
- **Suggested change:** Backend could return an `is_active` flag (or the full list sorted with an explicit `active_version` field). Defer unless versions start being added out of order.
- **Breaking risk:** None.

---

## Confidence and caveats

- All findings are from code inspection; no runtime profiling, no e2e coverage review.
- `CardPicker`'s uncontrolled pattern and the `StrictMode` `mountedRef` pattern are intentional per CLAUDE.md — no findings touch them.
- F-1 (SpotAnalysis Tailwind conversion) is the largest visible change by diff size, but low risk — no unit tests depend on inline styles.
- F-8 (SpotAnalysis hook remount on toggle) is the most load-bearing and deserves a test added alongside any fix.
