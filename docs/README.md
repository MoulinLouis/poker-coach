# Documentation Index

Where to look, and where to update. Agent-oriented.

If you're starting a new session, read [`../CLAUDE.md`](../CLAUDE.md) first — it
carries the load-bearing gotchas and the workflow rules. Everything below is
the deep reference that CLAUDE.md points into.

## Source of truth

One row per topic. The canonical file owns that topic — update it in the same
commit as the code change. Anywhere else that mentions the topic is a
pointer, not the source.

| Topic | Canonical file | Update when… |
|---|---|---|
| Session-level agent workflow | [`../CLAUDE.md`](../CLAUDE.md) | Workflow rules change, a new load-bearing gotcha is discovered |
| User-facing overview | [`../README.md`](../README.md) | Scope or install flow changes |
| Architecture orientation ("where things live") | [`ARCHITECTURE.md`](ARCHITECTURE.md) | New subpackage, new route, new top-level concern |
| Full design rationale | [`plans/old/2026-04-18-poker-hu-llm-coach-design.md`](plans/old/2026-04-18-poker-hu-llm-coach-design.md) | A design decision in the plan is overridden (record the override in a new ADR, leave the plan as historical) |
| Non-obvious decisions | [`decisions/`](decisions/README.md) | A decision that took debugging time to land and would cost future sessions to rediscover — add a new `YYYY-MM-DD-<slug>.md` with **Context · Decision · Rationale · Canary · Commits** |
| "When adding X, read Y" | [`CODE_PATTERNS.md`](CODE_PATTERNS.md) | New reusable pattern establishes or an existing one moves |
| Prompt packs | [`PROMPTS.md`](PROMPTS.md) + `../prompts/<pack>/<version>.md` | New pack / new version — bump the `version` in frontmatter, not an in-place rewrite |
| End-of-project analysis | [`RESULTS.md`](RESULTS.md) | Analytical conclusions land (not populated yet) |
| Implementation plans (historical) | [`plans/`](plans/) | New multi-step plan written; archive to `plans/old/` when complete |

## Doc types

**ADRs (`decisions/`)** — frozen once written. Every ADR has a **Canary**
section: the test or grep pattern that flips if the assumption behind the
decision breaks. When the canary flips, write a new ADR overriding the old
one; don't rewrite history in place.

**Plans (`plans/`)** — working documents. `YYYY-MM-DD-<slug>.md`. Once the
work ships, move to `plans/old/` so future sessions know not to re-execute
them.

**Living references (`ARCHITECTURE.md`, `CODE_PATTERNS.md`, `PROMPTS.md`)** —
update alongside code. The top of each file should carry
`<!-- Last verified against code: YYYY-MM-DD -->` so drift is visible.

## Find the right file

| If you want to… | Open |
|---|---|
| Run the project | [`../CLAUDE.md`](../CLAUDE.md) → **Run** section |
| Avoid the 7 landmines that bit past sessions | [`../CLAUDE.md`](../CLAUDE.md) → **Load-bearing gotchas** |
| Know why the engine uses integer chips / `deck_snapshot` / lazy oracle / etc. | [`decisions/`](decisions/README.md) |
| Add a new route, model preset, prompt pack, or React component | [`CODE_PATTERNS.md`](CODE_PATTERNS.md) |
| Understand the decision lifecycle (POST → SSE → finalize → sweep) | [`ARCHITECTURE.md`](ARCHITECTURE.md) → **Decision lifecycle** |
| Understand the engine invariants | [`../CLAUDE.md`](../CLAUDE.md) → **Engine invariants** |
| Debug unexplained Anthropic / OpenAI behavior | [`../CLAUDE.md`](../CLAUDE.md) → **When stuck** + relevant ADR in [`decisions/`](decisions/README.md) |
| See the full original design | [`plans/old/2026-04-18-poker-hu-llm-coach-design.md`](plans/old/2026-04-18-poker-hu-llm-coach-design.md) |
