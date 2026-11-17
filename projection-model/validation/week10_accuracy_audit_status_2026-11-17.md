# Week 10 (2026) accuracy audit — review only

Started: 2026-11-17. Status: **BLOCKED — not publishable as completed accuracy**.

## Available evidence
- `model-snapshots/2026-11-14-pregame-ppr-projections.csv`: 351 frozen rows; metadata explicitly states `requires per-game kickoff verification`.
- `data/actual-ppr-2026.json`: 319 Week 10 actual-player records in the repository at audit initiation.
- `projection-model/2026-week10-ppr-projections.csv` differs from the frozen snapshot: e.g., Dak Prescott 17.43 current vs 19.43 frozen; Tyler Shough 17.71 current vs 18.71 frozen. The frozen snapshot is **not yet proven** to reflect all final approved manual pregame overrides.
- `model-validation/2026-week10-validation.csv` was not found.

## Required before publishing Week 10 to Performance Tracker
1. Establish final per-game kickoff-frozen rankings and PPR values, including approved manual overrides, from dated audit evidence. Do not replace frozen values with postgame changes.
2. Reconcile actual PPR records by player, position and team, including unmatched and zero-point cases. Verify participation, in-game injuries, and data completeness.
3. Calculate QB/RB/WR/TE matched counts, MAE, bias, top-24 QB/TE and top-36 RB/WR overlap, plus biggest hits and misses.
4. Validate waiver and sleeper picks were recorded before kickoff; omit unverified picks.
5. Publish `model-validation/2026-week10-validation.csv` and related outcome reports only after quality gates pass; verify website rendering.

No model weights, rankings, or live projections were changed by this status report.
