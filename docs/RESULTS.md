# Results

End-of-project quantitative analysis. Populated once enough decisions are logged to draw conclusions.

Planned sections:

- **Model comparison** — per-model agreement rate vs. a designated reference, average cost per decision, latency distribution.
- **Prompt pack comparison** — agreement-rate delta across prompt versions holding model constant; cost deltas; failure-mode breakdown (invalid_response, illegal_action rates).
- **Confidence calibration** — self-reported confidence vs. empirical agreement rate, plotted per model.
- **Cost breakdown** — total spend by model × reasoning effort, extrapolation to per-hour and per-session.

Source: aggregations over the `decisions` and `actual_actions` tables. Notebooks live under `notebooks/`.
