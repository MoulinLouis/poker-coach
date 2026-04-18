# CardPicker is uncontrolled, no prop resync

## Context

`CardPicker` receives `heroHole: [string, string] | null` and `villainHole: [string, string] | null` from the parent. The slot model has 4 independent positions (h1, h2, v1, v2), each of which can be empty while its pair-mate is filled.

That intermediate state ("v1 set, v2 not") has no representation in the parent's prop shape — a pair with one element null collapses to `null`. When the parent re-rendered with a `null` villain prop after the user filled v1, an original `useEffect` compared props against internal state and re-seeded the slots to match props, clobbering the just-set v1.

## Decision

`CardPicker` is uncontrolled:

- Parent props seed initial state on mount only (`useState(() => ...)`).
- No `useEffect` to sync props → state after mount.
- Internal state is authoritative for the four slot values.
- Parent is notified via `onChange` only when a complete pair is ready (or becomes unset).
- If a caller needs to force a reset, it passes a new `key` to remount.

## Rationale

React controlled/uncontrolled is not a style choice — it's dictated by whether the parent's prop shape can faithfully represent every state the child needs. When it can't, attempting control introduces destructive resyncs. The child must own state that the parent can't express.

## Canary

- User-visible regression: filling villain's first card, then a second click either dropping the first card or failing to assign the second → a prop resync has crept back in.
- Grep `CardPicker.tsx` for `useEffect`. It should have none (or a narrowly-scoped one that doesn't touch `slots`).

## Implementing commits

- `313370f` — drop CardPicker prop re-sync that clobbered villain slots
- `a4deb48` — preserve intermediate slot state
