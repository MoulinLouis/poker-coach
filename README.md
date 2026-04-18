# Poker HU LLM Coach

Local web-based heads-up No-Limit Hold'em coach powered by LLMs. Two modes:

- **Live coach** — two humans play face to face; hero receives real-time
  coaching on every decision, villain plays without assistance.
- **Spot analysis** — enter any heads-up spot manually and compare up to
  three models side-by-side.

Not RTA. Not connected to any real poker room.

## Stack

- Python 3.12 · FastAPI · SQLAlchemy + Alembic on SQLite · pytest + Hypothesis
- React 18 · Vite · Tailwind 4 · vitest + Playwright
- Oracle abstraction over **Anthropic Messages** and **OpenAI Responses**.
  Default preset `gpt-5.3-codex-xhigh`; see
  [`docs/decisions/2026-04-18-model-strategy.md`](docs/decisions/2026-04-18-model-strategy.md).

## Install and run

Prereqs: [`uv`](https://docs.astral.sh/uv/), Node 20+, `make`.

```sh
cp .env.example .env     # add ANTHROPIC_API_KEY and/or OPENAI_API_KEY
make install             # uv sync + npm install
make db-upgrade          # alembic upgrade head
make dev                 # FastAPI :8000 + Vite :5173 (Vite proxies /api)
```

Other make targets: `test`, `e2e`, `lint`, `fmt`. Full command reference in
[`CLAUDE.md`](CLAUDE.md).

Missing API keys don't crash startup — they raise `RuntimeError` lazily when
a decision is dispatched for that provider.

## Documentation

Start with [`CLAUDE.md`](CLAUDE.md) for the session-level rules and
load-bearing gotchas. Everything else is indexed from
[`docs/README.md`](docs/README.md).

| If you want to… | Open |
|---|---|
| Understand the architecture | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Add a preset / prompt pack / route / component | [`docs/CODE_PATTERNS.md`](docs/CODE_PATTERNS.md) |
| Know *why* a non-obvious decision was made | [`docs/decisions/`](docs/decisions/README.md) |
| See the original design | [`docs/plans/old/2026-04-18-poker-hu-llm-coach-design.md`](docs/plans/old/2026-04-18-poker-hu-llm-coach-design.md) |

## License

TBD.
