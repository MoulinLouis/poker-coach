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
