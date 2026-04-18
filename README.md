# Poker HU LLM Coach

Local web-based heads-up No-Limit Hold'em coach powered by LLMs. Two modes:

- **Live coach** — two humans play face to face; hero receives real-time coaching on every decision, villain plays without assistance.
- **Spot analysis** — enter any heads-up spot manually and get the LLM's recommendation, reasoning, and confidence (side-by-side across multiple models).

Not RTA. Not connected to any real poker room.

## Status

Phase 0 in progress — repo scaffolding and dev loop. See [`docs/plans/2026-04-18-poker-hu-llm-coach-design.md`](docs/plans/2026-04-18-poker-hu-llm-coach-design.md) for the full design and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the condensed reference.

Phase progression:

| Phase | Deliverable |
|---|---|
| 0 | Repo skeleton, CI, dev loop, Alembic baseline |
| 1 | HU NLHE engine + phevaluator showdown |
| 2 | Anthropic oracle + first prompt pack + log schema |
| 3 | FastAPI + SSE + decision lifecycle + sweeper |
| 4 | React Live Coach UI |
| 5 | OpenAI Responses oracle + multi-model Compare |
| 6 | History, Prompts editor, cost footer breakdowns |

## Install and run

To be filled in as Phase 0 completes. The target dev loop is:

```sh
make dev       # FastAPI :8000 + Vite :5173 (Vite proxies /api)
make test      # pytest + vitest + playwright
make lint      # ruff + mypy + eslint + tsc + prettier
```

Secrets live in `.env` (gitignored); see `.env.example`.

## License

TBD.
