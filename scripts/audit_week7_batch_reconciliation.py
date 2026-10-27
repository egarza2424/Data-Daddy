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
    season_stats = actual[actual.season == 2026].copy()
    actual = season_stats[season_stats.week == args.week].copy()
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
        value = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", value)
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
    # Report verified suffix variants only when actual statistics truly join.
    for source_name, actual_name, pos in [("Aaron Jones Sr.", "Aaron Jones", "RB"), ("Kyle Pitts Sr.", "Kyle Pitts", "TE")]:
        rows = merged[(merged.player_name == source_name) & (merged.position == pos)]
        candidates = actual[(actual.player_display_name == actual_name) & (actual.position == pos)]
        if len(rows) == 1 and len(candidates) == 1 and pd.notna(rows.iloc[0].actual_ppr):
            print(f"VERIFIED: {source_name} -> {actual_name}: {rows.iloc[0].actual_ppr:.2f} PPR")
        else:
            print(f"REQUIRES REVIEW: {source_name} -> {actual_name}; exact normalized join unavailable")
    print("Excluded ambiguous prediction identities:", len(pred) - len(safe_pred))
    ambiguous = pred[pred.identity.duplicated(keep=False)]
    if not ambiguous.empty:
        print("\nAMBIGUOUS PREDICTION IDENTITIES:")
        print(ambiguous[["player_name", "position", "player_id", "identity"]].to_string(index=False))
    missing = merged[(merged.actual_rank.isna()) & ((merged.position_rank <= merged.position.map(CAPS)) | (merged.projected_position_rank <= merged.position.map(CAPS)))]
    if not missing.empty:
        print("\nUNMATCHED TOP-CUTOFF PLAYERS:")
        print(missing[["player_name", "position", "team", "position_rank", "projected_position_rank"]].to_string(index=False))

    # Export every unresolved identity together, without treating missing stats as DNP.
    eligible_mask = (merged.position_rank <= merged.position.map(CAPS)) | (merged.projected_position_rank <= merged.position.map(CAPS))
    unresolved = merged[eligible_mask & merged.actual_rank.isna()].copy()
    unresolved["review_status"] = "UNVERIFIED_NO_STATS_MATCH"
    unresolved["audit_treatment"] = "EXCLUDE_FROM_OFFICIAL_METRIC_PENDING_PARTICIPATION_CHECK"
    ambiguous = pred[pred.identity.duplicated(keep=False)].copy()
    ambiguous["review_status"] = "AMBIGUOUS_DUPLICATE_PREDICTION_IDENTITY"
    OUT.mkdir(parents=True, exist_ok=True)
    unresolved.to_csv(OUT / "2026-week7-unresolved-players-review.csv", index=False)
    ambiguous.to_csv(OUT / "2026-week7-ambiguous-identities-review.csv", index=False)
    print("Unresolved records:", len(unresolved), "| Ambiguous prediction rows:", len(ambiguous))
    print("IMPORTANT: missing nflverse row does NOT establish inactivity.")
    # Inspect likely name variants from actual statistics without auto-accepting them.
    import difflib
    if not unresolved.empty:
        print("\\nCANDIDATE ACTUAL-STATS NAMES (DIAGNOSTIC ONLY):")
        for _, row in unresolved.iterrows():
            pool = actual[actual.position == row.position]
            names = pool.player_display_name.dropna().astype(str).unique().tolist()
            candidates = difflib.get_close_matches(str(row.player_name), names, n=4, cutoff=0.48)
            details = []
            for candidate_name in candidates:
                candidate_rows = pool[pool.player_display_name == candidate_name]
                for _, candidate in candidate_rows.iterrows():
                    details.append(f"{candidate_name} [{candidate.get('recent_team', '?')}] {candidate.actual_ppr:.2f} PPR")
            print(f"{row.player_name} ({row.team}/{row.position}): " + ("; ".join(details) if details else "NO CLOSE NAME IN STATS"))

    # Distinguish players entirely absent from season stats from Week 7-only gaps.
    season_stats["identity"] = season_stats["player_display_name"].map(key) + "|" + season_stats["position"].astype(str)
    print("\\nUNMATCHED PLAYER SEASON-HISTORY DIAGNOSTIC:")
    for _, row in unresolved.iterrows():
        history = season_stats[season_stats.identity == row.identity]
        weeks = sorted(pd.to_numeric(history.week, errors="coerce").dropna().astype(int).unique().tolist())
        print(f"{row.player_name} ({row.position}): season_weeks={weeks if weeks else 'NONE'}; week7_stat_row=NO; participation=UNVERIFIED")
    # Flag coverage anomalies separately from performance, without rewriting predictions.
    schedule_candidates = unresolved[["player_name", "position", "team", "identity", "position_rank", "projected_position_rank"]].copy()
    season_keys = set(season_stats.identity.dropna())
    schedule_candidates["season_stats_presence"] = schedule_candidates.identity.map(lambda k: "SEEN_OTHER_WEEKS" if k in season_keys else "NO_2026_STATS")
    schedule_candidates["week7_participation"] = "NOT_VERIFIED"
    schedule_candidates["possible_reason"] = "BYE_OR_INACTIVE_OR_INJURED_OR_DATA_GAP"
    schedule_candidates.to_csv(OUT / "2026-week7-participation-review.csv", index=False)
    print("Participation review exported; do not infer DNP from missing weekly rows.")
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
