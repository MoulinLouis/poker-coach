# Threat Model

**Document scope**: heads-up no-limit hold'em, play-money or sandbox environments only. No real-money targets are addressed. Multi-table configurations are out of scope.

---

## 1. Attack-surface matrix

The layers below follow the standard RTA taxonomy from L0 (hardware) to L5 (input injection). For each layer we characterize the capability available to an attacker, the legality and detectability posture from the platform's perspective, and this tool's stance.

| Layer | Name | Attacker capability | Platform detectability | This tool's stance |
|-------|------|--------------------|-----------------------|--------------------|
| L0 | Hardware | Physical card-marking, RFID skimming, hole-card cameras. Requires physical access to the table or card room. | High — requires presence; defeated by standard casino countermeasures. | Out of scope. Physical access not assumed. |
| L1 | Screen read | Capture the player's own monitor via OS screenshot or camera. No modification of any process or binary. | Low — the poker room cannot observe what is on the player's screen or what software is running outside their client. | **This is the only layer we use.** `grab_window` takes an OS screenshot of the poker client window. No other process is touched. |
| L2 | OS / process | Hook into the poker client process, read memory, inject DLLs, use kernel drivers. | Medium — anti-cheat drivers, memory-integrity checks, or code-signing requirements can block or detect this. Some platforms deploy userland anti-cheat (similar to HWID bans). | **Explicitly rejected.** We do not attach to, inspect, or modify any process. |
| L3 | Network | Intercept or replay the poker client's network traffic; decrypt TLS to read hole cards before dealing animation. | Medium to high — TLS pinning, protocol obfuscation, and server-side timing checks make this detectable. Also illegal under most jurisdictions (CFAA, Computer Misuse Act). | **Explicitly rejected.** No network interception. The coach backend communicates only with the Anthropic/OpenAI API, never with the poker room's servers. |
| L4 | Client DOM | Manipulate the poker client's UI layer (e.g., a browser-based client via JavaScript injection or a native GUI via accessibility APIs) to extract state programmatically. | Low to medium for JS injection; higher for accessibility-API scraping if the platform hooks those events. | **Explicitly rejected.** We use only pixel-level CV on the rendered screen. No DOM access, no accessibility-API queries. |
| L5 | Input injection | Automate mouse clicks or keyboard input to place bets without human involvement. Converts the tool from "overlay" to "bot". | Medium — bot detection measures (timing analysis, jitter, cursor trajectory heuristics) are specifically designed to catch this. | **Explicitly rejected.** The user always clicks. Removing human agency collapses the paper's L1-only argument and escalates the ethical category. |

---

## 2. Defender assumptions

We model the poker platform as an adversary with the following observational capability:

- **Action timing**: the platform can record the exact timestamp of every player action. It can compute inter-action latencies, session-level histograms, and compare against population baselines.
- **Action patterns**: the platform sees every action (fold/call/raise/size) and can compute convergence toward known GTO solutions. Unusual GTO-alignment over large sample sizes is a signal.
- **Win/loss variance**: unusually low variance (especially in spots where recreational players lose EV) is detectable over sufficient sample sizes.
- **Network fingerprint**: the platform can observe client IP, connection timing, and packet inter-arrival distributions. It cannot observe what other applications are running on the same host.
- **API rate-limit distributions**: if the platform's own API is being queried (e.g., for game state), anomalous polling rates are observable.

The platform **cannot**:
- See the player's screen or read pixels from the player's display.
- Enumerate the player's running processes or installed software.
- Read the player's RAM or intercept intra-host traffic.
- Access the player's local filesystem.

---

## 3. Attacker assumptions

For the purposes of this research we assume the player (attacker from the platform's perspective) has:

- **Full root / administrator access** on their own machine. They can install any software, run any process, and read any file on that machine.
- **Visual access** to the poker client's rendered output. They can screenshot it, crop it, and process the pixels.
- **No ability to modify the poker client binary** or patch its memory at runtime. Any such modification is out of scope and out of scope for this paper.
- **No ability to intercept or modify the poker client's network traffic**. We assume TLS is intact and the attacker has no MITM position on the path to the poker room's servers.
- **No physical proximity** to any other player or dealer. This is online poker only.

---

## 4. Scope

| Dimension | In scope | Out of scope |
|-----------|----------|--------------|
| Game format | Heads-up no-limit hold'em | 6-max, full ring, tournaments, PLO, mixed games |
| Money | Play money, sandbox / demo environments | Real-money tables |
| Platform type | Any client that renders cards as visible pixels on the player's screen | Server-side rendered or encrypted display protocols |
| Attack layer | L1 (screen read) only | L0, L2, L3, L4, L5 |
| Automation | Advice display only; human performs all actions | Any form of auto-clicking or action queuing |

---

## 5. Limitations

**Sample-size floor for behavioral fingerprinting.** The GTO-convergence fingerprint requires N ≥ 200 decisions before it reliably separates the RTA-assisted population from a strong human player. A single session of 50–80 hands provides 100–160 decisions, meaning a one-session sample is near but below the reliable detection threshold. Over multiple sessions the signal accumulates.

**No multi-table support.** State tracking is per-session and single-table. A user running two simultaneous HU tables would require two independent RTA instances with no shared state, and the behavioral fingerprint calculations do not account for multi-table variance reduction.

**No GTO-delta instrumentation for non-HU-coach platforms.** The `convergence_score` metric is calibrated against the coach's own recommendations. A platform using a different GTO solver (e.g., PioSolver, GTO+) would require recalibration of baseline convergence expectations before the comparison is valid.

**Human reaction time adds irreducible variance.** The human-in-the-loop delay between overlay display and click is the primary mechanism that preserves timing entropy above the detection threshold. Any change to the UX that reduces this delay (e.g., a hotkey that fires immediately on overlay display) would push the timing distribution toward the "pure bot" cluster and erode the L1-only defense.

**No real-money detection studies.** All empirical results in this paper are from play-money or sandbox environments. The behavioral fingerprint thresholds may differ on real-money tables where human timing is affected by stake-level anxiety.
