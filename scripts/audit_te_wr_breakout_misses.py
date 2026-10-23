"""Read-only audit of largest historical TE/WR ranking misses and prior opportunity."""
import pandas as pd

pred = pd.read_csv("projection-model/2025-ppr-walkforward-predictions.csv", low_memory=False)
stats = pd.read_csv("historical-data/player_stats_2025.csv", low_memory=False)
pred = pred[pred.model.eq("F_position_specific") & pred.position.isin(["TE", "WR"])].copy()
stats = stats[stats.position.isin(["TE", "WR"])].copy()
for frame in (pred, stats):
    frame["player_id"] = frame.player_id.astype(str)
    frame["week"] = pd.to_numeric(frame.week)
    frame["season"] = pd.to_numeric(frame.season)
stats["targets"] = pd.to_numeric(stats.targets, errors="coerce").fillna(0)
for column in ("receptions", "receiving_yards"):
    if column in stats:
        stats[column] = pd.to_numeric(stats[column], errors="coerce").fillna(0)
histories = {(s, p, t): g.sort_values("week") for (s, p, t), g in stats.groupby(["season", "player_id", "team"])}
pred["actual_rank"] = pred.groupby(["season", "week", "position"]).actual_ppr.rank(ascending=False, method="min")
pred["projected_rank"] = pred.groupby(["season", "week", "position"]).projected_ppr.rank(ascending=False, method="min")
pred["rank_miss"] = pred.projected_rank - pred.actual_rank
pred["ppr_miss"] = pred.actual_ppr - pred.projected_ppr
print("Rank miss > 0 means player finished higher than projected.")
for pos, group in pred.groupby("position"):
    print(f"\\n{pos}: biggest under-ranked breakout weeks")
    for r in group.nlargest(8, "rank_miss").itertuples(index=False):
        history = histories.get((r.season, r.player_id, r.team))
        prior = history.loc[history.week.lt(r.week)].tail(3) if history is not None else pd.DataFrame()
        target_values = prior.targets.tolist() if len(prior) else []
        target_weeks = prior.week.tolist() if len(prior) else []
        name = getattr(r, "player_name", None)
        if name is None and history is not None and "player_display_name" in history:
            name = history.player_display_name.iloc[-1]
        if name is None and history is not None and "player_name" in history:
            name = history.player_name.iloc[-1]
        print(f"  week={r.week} id={r.player_id} name={name or 'unresolved'} team={r.team} "
              f"actual_rank={r.actual_rank:.0f} projected_rank={r.projected_rank:.0f} "
              f"actual_PPR={r.actual_ppr:.2f} projected_PPR={r.projected_ppr:.2f} "
              f"prior_weeks={target_weeks} prior_targets={target_values}")
    print(f"{pos}: biggest over-ranked weeks")
    for r in group.nsmallest(8, "rank_miss").itertuples(index=False):
        history = histories.get((r.season, r.player_id, r.team))
        prior = history.loc[history.week.lt(r.week)].tail(3) if history is not None else pd.DataFrame()
        name = getattr(r, "player_name", None)
        if name is None and history is not None and "player_display_name" in history:
            name = history.player_display_name.iloc[-1]
        if name is None and history is not None and "player_name" in history:
            name = history.player_name.iloc[-1]
        print(f"  week={r.week} id={r.player_id} name={name or 'unresolved'} team={r.team} "
              f"actual_rank={r.actual_rank:.0f} projected_rank={r.projected_rank:.0f} "
              f"actual_PPR={r.actual_ppr:.2f} projected_PPR={r.projected_ppr:.2f} "
              f"prior_targets={prior.targets.tolist() if len(prior) else []}")
print("Descriptive historical audit; causes such as injury/route changes not inferred without evidence.")
