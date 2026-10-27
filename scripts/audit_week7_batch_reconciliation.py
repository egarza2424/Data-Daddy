#!/usr/bin/env python3
"""Review-only Week 7 AI-vs-PPR audit. Never updates live predictions."""
import argparse
import io
from pathlib import Path
import requests
import pandas as pd

REPO = "egarza2424/Data-Daddy"
REF = "8f06bfd4e1fba8ccf1b89b6de5179adf986c338d"
CAPS = {"QB": 24, "TE": 24, "RB": 36, "WR": 36}
OUT = Path("projection-model/validation")
URLS = [
    "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.csv",
    "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.csv.gz",
]

def get_csv(url):
    response = requests.get(url, timeout=90)
    response.raise_for_status()
    return pd.read_csv(io.BytesIO(response.content), low_memory=False)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", type=int, default=7)
    args = parser.parse_args()
    raw = f"https://raw.githubusercontent.com/{REPO}/{REF}/projection-model/2026-week7-ppr-projections.csv"
    pred = get_csv(raw)
    actual = None
    errors = []
    for url in URLS:
        try:
            candidate = get_csv(url)
            if {"season", "week", "player_id", "fantasy_points_ppr"}.issubset(candidate.columns):
                actual = candidate
                break
            errors.append(f"{url}: missing required columns")
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    if actual is None:
        raise SystemExit("No authoritative stats dataset available; no outputs written. " + " | ".join(errors))
    actual = actual[(actual.season == 2026) & (actual.week == args.week)].copy()
    if actual.empty:
        raise SystemExit("Week 7 stats are not populated; no outputs written.")
    actual["player_id"] = actual["player_id"].astype(str)
    pred["player_id"] = pred["player_id"].astype(str)
    actual["position"] = actual["position"].astype(str)
    actual["actual_ppr"] = pd.to_numeric(actual["fantasy_points_ppr"], errors="coerce")
    actual = actual[actual.position.isin(CAPS) & actual.actual_ppr.notna()].copy()
    actual = actual.sort_values(["position", "actual_ppr", "player_id"], ascending=[True, False, True])
    actual["actual_rank"] = actual.groupby("position")["actual_ppr"].rank(method="min", ascending=False)
    # Match unique exact normalized player names + position, never fuzzy identities.
    import re
    import unicodedata
    if "player_display_name" not in actual.columns:
        raise SystemExit("Missing player_display_name; cannot match safely.")
    def key(value):
        value = unicodedata.normalize("NFKD", str(value))
        value = "".join(c for c in value if not unicodedata.combining(c)).lower()
        value = re.sub(r"\\b(jr|sr|ii|iii|iv)\\b", "", value)
        return re.sub(r"[^a-z0-9]", "", value)
    actual["identity"] = actual["player_display_name"].map(key) + "|" + actual["position"]
    pred["identity"] = pred["player_name"].map(key) + "|" + pred["position"]
    # Refuse duplicate keys on either side to prevent incorrect joins.
    safe_actual = actual[~actual.identity.duplicated(keep=False)]
    safe_pred = pred[~pred.identity.duplicated(keep=False)].copy()
    merged = safe_pred.merge(safe_actual[["identity", "actual_ppr", "actual_rank"]],
                             on="identity", how="left", validate="one_to_one", indicator=True)
    merged["match_status"] = merged["_merge"].map({"both": "matched_unique_name_position", "left_only": "unmatched", "right_only": "unexpected"})
    merged = merged.drop(columns=["_merge"])
    print("Excluded ambiguous prediction identities:", len(pred) - len(safe_pred))
    ambiguous = pred[pred.identity.duplicated(keep=False)]
    if not ambiguous.empty:
        print("\nAMBIGUOUS PREDICTION IDENTITIES:")
        print(ambiguous[["player_name", "position", "player_id", "identity"]].to_string(index=False))
    missing = merged[(merged.actual_rank.isna()) & ((merged.position_rank <= merged.position.map(CAPS)) | (merged.projected_position_rank <= merged.position.map(CAPS)))]
    if not missing.empty:
        print("\nUNMATCHED TOP-CUTOFF PLAYERS:")
        print(missing[["player_name", "position", "team", "position_rank", "projected_position_rank"]].to_string(index=False))

    summary = []
    for position, cutoff in CAPS.items():
        subset = merged[merged.position == position].copy()
        eligible = subset[(subset.position_rank <= cutoff) | (subset.projected_position_rank <= cutoff)]
        common = eligible[(eligible.position_rank <= cutoff) & (eligible.projected_position_rank <= cutoff) & eligible.actual_rank.notna()]
        summary.append({
            "position": position, "cutoff": cutoff, "predictions": len(subset),
            "eligible_union": len(eligible), "unmatched_eligible": int(eligible.actual_rank.isna().sum()),
            "common_matched": len(common),
            "ai_mae_common": round((common.position_rank - common.actual_rank).abs().mean(), 3),
            "ppr_mae_common": round((common.projected_position_rank - common.actual_rank).abs().mean(), 3),
        })
    OUT.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUT / "2026-week7-batch-reconciliation-review.csv", index=False)
    pd.DataFrame(summary).to_csv(OUT / "2026-week7-batch-ai-vs-ppr-review.csv", index=False)
    print(pd.DataFrame(summary).to_string(index=False))
    print("Review-only outputs saved. Unmatched IDs require manual crosswalk; no zero scores or exclusions inferred.")
    print("No historical snapshots, live rankings, model weights, or website files changed.")

if __name__ == "__main__":
    main()
