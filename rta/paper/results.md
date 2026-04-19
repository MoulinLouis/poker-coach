# Results

---

## 1. CV accuracy

Card classification accuracy across the two target environments. Each cell reports top-1 accuracy over TBD labelled frames. OCR rows cover rank and suit separately; the "card" row is the combined correct rank-and-suit prediction.

| Metric | mock_html | Friend's app |
|--------|-----------|--------------|
| Card accuracy (combined) | TBD% | TBD% |
| Rank OCR accuracy | TBD% | TBD% |
| Suit OCR accuracy | TBD% | TBD% |
| False-positive rate (non-card regions) | TBD% | TBD% |
| Frames evaluated | TBD | TBD |

**Notes.** mock_html results are from the scripted demo loop (TBD frames, TBD distinct card images). Friend's app results are pending calibration of `rta/profiles/friends_app.yaml`; column will be populated once profile ROIs are locked.

---

## 2. End-to-end latency distribution

Three timing intervals are measured per decision cycle:

| Interval | Description | p50 | p95 | p99 |
|----------|-------------|-----|-----|-----|
| Observe | `grab_window` + `observe_frame` (CV pipeline) | TBD ms | TBD ms | TBD ms |
| Coach round-trip | HTTP POST `/api/decisions` + SSE stream until `advice` event | TBD ms | TBD ms | TBD ms |
| Overlay update | Time from `advice` event receipt to overlay repaint | TBD ms | TBD ms | TBD ms |
| **Total** | Observe through overlay update | TBD ms | TBD ms | TBD ms |

**Target**: total p95 < 3 000 ms to keep advice visible before the typical action clock expires. Results are from TBD decision cycles on TBD hardware (CPU: TBD, GPU: TBD, network: loopback for coach backend).

---

## 3. Detection comparison across populations

Four populations of 200 decisions each (see `paper/notebooks/detection_analysis.md` for methodology).

| Population | Timing entropy (bits) | GTO-convergence score | Session win-rate variance |
|------------|----------------------|----------------------|--------------------------|
| 1. Baseline regs (no RTA) | TBD | TBD | TBD |
| 2. Manual-study regs (PioSolver off-table) | TBD | TBD | TBD |
| 3. RTA-assisted regs (L1 + human-in-the-loop) | TBD | TBD | TBD |
| 4. Pure bot (coach advice, no human delay) | TBD | TBD | TBD |

**Expected ranges** (from design rationale, to be confirmed experimentally):

- Timing entropy: pop 1 > 3.5 bits; pop 3 > 2.5 bits; pop 4 < 1.5 bits.
- GTO convergence: pop 3 and 4 > 0.85; pop 1 and 2 ≤ 0.65.
- Win-rate variance: pop 4 measurably lower than pop 1; pop 3 intermediate.

Statistical significance: TBD (target: p < 0.05 for timing-entropy separation between pop 1 and pop 3; p < 0.001 for pop 1 vs. pop 4).

---

## 4. Discussion

### Why L1 + human-in-the-loop pushes defenders onto behavioral ground

An L1-only tool is invisible to all process-level and network-level detection mechanisms because it makes no contact with the poker client other than reading pixels from the already-rendered screen. The poker platform has no technical means to distinguish our overlay from a second monitor displaying hand-history notes, a physical notebook, or a mental note the player formed from off-table study.

This forces the platform onto behavioral signals: timing distributions and GTO-convergence rates. Behavioral detection is probabilistic, requires large sample sizes (N ≥ 200 decisions), and is confounded by the human-in-the-loop delay that our architecture deliberately preserves. A human who clicks on our overlay advice introduces their natural reaction-time variance (typ. 250–1 500 ms), keeping timing entropy above the threshold that distinguishes automated input.

The implication for platform defenders is that L1 tools cannot be reliably detected within a single session of normal play. Reliable detection requires multi-session accumulation, which raises the false-positive rate for strong human players who have independently internalized GTO lines. This is not a flaw in detection methodology; it is the fundamental ambiguity that L1+human-in-the-loop is designed to occupy.

### Comparison with L2–L5 tools

Pure bots (L5 input injection) are detectable at N ≈ 50–100 decisions from timing entropy collapse alone. Memory-reading tools (L2) are detectable via anti-cheat kernel drivers if the platform deploys them. Network-intercept tools (L3) are blocked by TLS and server-side timing. By contrast, the L1+human-in-the-loop design has no equivalent single-signal detection path, which is precisely why it serves as a useful research boundary.

---

## 5. Future work

- **Anti-fingerprinting via randomized click jitter.** Adding configurable random delay drawn from a human-like Gaussian before displaying overlay advice would further raise timing entropy. Requires user-consent UX (the user must understand the deliberate delay) and careful calibration to avoid exceeding typical action-clock limits.

- **VLM-based CV replacement.** The current pipeline uses template matching plus OCR. Replacing it with a vision-language model (e.g., a fine-tuned CLIP or GPT-4o-mini vision call) would generalize across poker client skins without per-client calibration profiles. Latency and cost trade-offs require evaluation.

- **6-max generalization.** The current implementation and all experiments are HU only. 6-max introduces multi-way pots, position complexity, and a fundamentally different GTO solution space. Extending the coach backend and CV pipeline to 6-max is the most impactful near-term generalization.

- **Real-money detection studies with platform cooperation.** All results here use play-money data. A controlled study with a cooperating platform (where the platform knowingly seeds the player pool with RTA-assisted accounts) would yield ground-truth labeled data for training more accurate behavioral classifiers. This requires institutional ethics review and explicit platform partnership.

- **Longitudinal fingerprint drift.** As a player internalizes coach recommendations over weeks of RTA-assisted play, their un-assisted GTO convergence rises. This means the convergence fingerprint weakens over time even without the tool running. Modeling this drift is important for long-run detection accuracy claims.
