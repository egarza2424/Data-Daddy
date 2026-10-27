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
    # Source-verified Week 7 inactive list, kept separate from frozen predictions.
    # Sources: https://www.thescore.com/nfl/news/3629831/nfl-week-7-inactives-see-whos-in-and-out
    #          https://www.fantasypros.com/nfl/players/inactives.php
    #          https://www.fftoday.com/nfl/26-inactives-wk7.html
    verified_inactive = {
        "breecehall|RB", "davidmontgomery|RB", "tylerwarren|TE", "jeremiyahlove|RB",
        "emekaegbuka|WR", "rasheerice|WR", "devontasmith|WR",
    }
    participation_review = schedule_candidates.copy()
    participation_review["verified_week7_status"] = participation_review.identity.map(
        lambda identity: "CONFIRMED_INACTIVE" if identity in verified_inactive else "UNVERIFIED"
    )
    participation_review["accuracy_treatment"] = participation_review.verified_week7_status.map(
        lambda status: "EXCLUDE_CONFIRMED_NONPARTICIPANT" if status == "CONFIRMED_INACTIVE" else "HOLD_FOR_VERIFICATION"
    )
    participation_review["source_urls"] = participation_review.verified_week7_status.map(
        lambda status: "https://www.thescore.com/nfl/news/3629831/nfl-week-7-inactives-see-whos-in-and-out ; https://www.fftoday.com/nfl/26-inactives-wk7.html" if status == "CONFIRMED_INACTIVE" else ""
    )
    participation_review["review_note"] = participation_review.identity.map({
        "jeremiyahlove|RB": "OUT ankle; NFL Week 7 injury report",
        "pierrestrong|RB": "No Week 7 stats row; Josh Jacobs returned; participation still unverified",
        "dominiclovett|WR": "No season stats; investigate why ranked WR29; do not erase historical miss",
        "malikturner|WR": "No season stats; investigate why ranked WR35; do not erase historical miss",
        "xaviergipson|WR": "No season stats; investigate why ranked WR34; do not erase historical miss",
    }).fillna("")
    participation_review.to_csv(OUT / "2026-week7-participation-review.csv", index=False)
    print("Verified inactives:", int((participation_review.verified_week7_status == "CONFIRMED_INACTIVE").sum()))
    print("Still unverified:", int((participation_review.verified_week7_status == "UNVERIFIED").sum()))
    summary = []
    for position, cutoff in CAPS.items():
        subset = merged[merged.position == position].copy()
        eligible = subset[(subset.position_rank <= cutoff) | (subset.projected_position_rank <= cutoff)]
        common = eligible[(eligible.position_rank <= cutoff) & (eligible.projected_position_rank <= cutoff) & eligible.actual_rank.notna()]
        union_matched = eligible[eligible.actual_rank.notna()].copy()
        ai_union_mae = (union_matched.position_rank - union_matched.actual_rank).abs().mean()
        ppr_union_mae = (union_matched.projected_position_rank - union_matched.actual_rank).abs().mean()
        one_sided = union_matched[(union_matched.position_rank <= cutoff) != (union_matched.projected_position_rank <= cutoff)]

        summary.append({
            "position": position, "cutoff": cutoff, "predictions": len(subset),
            "eligible_union": len(eligible), "unmatched_eligible": int(eligible.actual_rank.isna().sum()),
            "common_matched": len(common),
            "union_matched": len(union_matched), "one_sided_matched": len(one_sided),
            "ai_mae_union": round(ai_union_mae, 3), "ppr_mae_union": round(ppr_union_mae, 3),
            "ai_mae_common": round((common.position_rank - common.actual_rank).abs().mean(), 3),
            "ppr_mae_common": round((common.projected_position_rank - common.actual_rank).abs().mean(), 3),
        })
    OUT.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUT / "2026-week7-batch-reconciliation-review.csv", index=False)
    pd.DataFrame(summary).to_csv(OUT / "2026-week7-batch-ai-vs-ppr-review.csv", index=False)
    # Review-only SVG; do not publish to the website while coverage is incomplete.
    chart = pd.DataFrame(summary)
    width, height = 860, 400
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="860" height="400" viewBox="0 0 860 400">',
           '<rect width="860" height="400" fill="#101725"/>',
           '<text x="32" y="38" fill="#fff" font-family="Arial" font-size="22" font-weight="bold">Week 7 AI Score vs PPR Rankings</text>',
           '<text x="32" y="61" fill="#b5c0d2" font-family="Arial" font-size="13">Provisional union-of-top-cutoffs positional rank MAE (lower is better)</text>']
    for idx, (_, r) in enumerate(chart.iterrows()):
        y = 100 + idx * 70
        svg.append(f'<text x="32" y="{y+23}" fill="#fff" font-family="Arial" font-size="17">{r.position} top {int(r.cutoff)} (n={int(r.union_matched)})</text>')
        for offset, metric, color, label in [(0, r.ai_mae_union, "#45b5f6", "AI"), (25, r.ppr_mae_union, "#f6a94b", "PPR")]:
            bar_width = max(0, float(metric) / 22 * 480)
            svg.append(f'<rect x="265" y="{y+offset}" width="{bar_width:.1f}" height="19" rx="4" fill="{color}"/>')
            svg.append(f'<text x="{275+bar_width:.1f}" y="{y+offset+15}" fill="#fff" font-family="Arial" font-size="13">{label} {float(metric):.3f}</text>')
    svg.append('<text x="32" y="386" fill="#f3b2a8" font-family="Arial" font-size="12">NOT FOR PUBLICATION: unresolved participation, duplicate identity, and unverified participation</text>')
    svg.append('</svg>')
    (OUT / "2026-week7-ai-vs-ppr-PROVISIONAL.svg").write_text("\\n".join(svg), encoding="utf-8")
    chart["publication_status"] = "BLOCKED_PENDING_PARTICIPATION_AND_IDENTITY_REVIEW"
    chart["methodology"] = "union_of_either_top_cutoff_with_actual_stats; includes one-sided top-cutoff misses; common-player figures retained as diagnostic"
    chart.to_csv(OUT / "2026-week7-graph-methodology-review.csv", index=False)
    print("Generated review-only SVG with union-of-cutoffs metrics. NOT published: participation and identity checks remain.")
    print(pd.DataFrame(summary).to_string(index=False))
    print("Review-only outputs saved. Unmatched IDs require manual crosswalk; no zero scores or exclusions inferred.")
    print("No historical snapshots, live rankings, model weights, or website files changed.")

if __name__ == "__main__":
    main()
