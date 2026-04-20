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
