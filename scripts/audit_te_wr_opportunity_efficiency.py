"""Read-only TE/WR opportunity efficiency and multi-TE team diagnostic.

Pregame features: prior 3 player appearances only; historical raw 2025 stats.
The multi-TE proxy uses prior-week teammate target participation, not personnel formations.
"""
import pandas as pd

stats = pd.read_csv("historical-data/player_stats_2025.csv", low_memory=False)
pred = pd.read_csv("projection-model/2025-ppr-walkforward-predictions.csv")
pred = pred.loc[pred.model.eq("F_position_specific") & pred.position.isin(["TE", "WR"])].copy()
for frame in (stats, pred):
    frame["player_id"] = frame.player_id.astype(str)
for c in ["week", "season", "targets", "receptions", "receiving_yards", "receiving_tds", "carries"]:
    if c not in stats:
        raise SystemExit(f"Missing raw column {c}")
    stats[c] = pd.to_numeric(stats[c], errors="coerce").fillna(0)
stats = stats.loc[stats.position.isin(["TE", "WR"])].copy()
stats["catch_rate"] = stats.receptions / stats.targets.clip(lower=1)
stats["yards_per_target"] = stats.receiving_yards / stats.targets.clip(lower=1)
stats["target_work"] = stats.targets + stats.carries
# Pregame team TE activity is a proxy for multiple TEs receiving targets,
# not evidence of 2-TE or 3-TE personnel formations.
team_te = stats.loc[stats.position.eq("TE")].groupby(
    ["season", "week", "team"], as_index=False).agg(
    te_players_targeted=("targets", lambda x: int((x >= 2).sum())),
    te_total_targets=("targets", "sum"))
history = {(season, pid): g.sort_values("week") for (season, pid), g in stats.groupby(["season", "player_id"])}
te_team_history = {(season, team): g.sort_values("week") for (season, team), g in team_te.groupby(["season", "team"])}
records = []
for r in pred.itertuples(index=False):
    prior = history.get((r.season, r.player_id))
    prior = prior.loc[prior.week.lt(r.week)].tail(3) if prior is not None else None
    if prior is None or len(prior) < 2:
        continue
    recent = prior.loc[prior.targets.gt(0)]
    team_prior = te_team_history.get((r.season, r.team))
    team_prior = team_prior.loc[team_prior.week.lt(r.week)].tail(3) if team_prior is not None else None
    records.append({
        "position": r.position, "week": r.week, "player_id": r.player_id,
        "projected_ppr": r.projected_ppr, "actual_ppr": r.actual_ppr,
        "recent_targets": prior.targets.mean(),
        "recent_catch_rate": recent.receptions.sum() / max(recent.targets.sum(), 1),
        "recent_yards_per_target": recent.receiving_yards.sum() / max(recent.targets.sum(), 1),
        "multi_te_target_games": int((team_prior.te_players_targeted >= 2).sum()) if team_prior is not None else 0,
        "te_team_weeks": len(team_prior) if team_prior is not None else 0
    })
df = pd.DataFrame(records)
if df.empty:
    raise SystemExit("No eligible pregame player history")
df["error"] = (df.projected_ppr - df.actual_ppr).abs()
df["target_band"] = pd.cut(df.recent_targets, [-1, 2, 5, 8, float("inf")],
                            labels=["0-2", "2-5", "5-8", ">8"])
df["efficiency_band"] = pd.cut(df.recent_yards_per_target, [-1, 5, 8, float("inf")],
                                labels=["<=5", "5-8", ">8"])
print("Historical matched TE/WR player-weeks:", len(df))
print("\\nTargets x receiving efficiency (pregame history):")
print(df.groupby(["position", "target_band", "efficiency_band"], observed=True).agg(
    n=("error", "size"), actual_ppr=("actual_ppr", "mean"),
    projected_ppr=("projected_ppr", "mean"), mae=("error", "mean")).round(3).to_string())
te = df.loc[df.position.eq("TE") & df.te_team_weeks.ge(2)].copy()
te["multiple_te_targeted"] = te.multi_te_target_games.ge(2)
print("\\nTE team receiving distribution proxy (2+ TEs with 2+ targets in 2+ of last 3 games):")
print(te.groupby("multiple_te_targeted").agg(
    n=("error", "size"), targets=("recent_targets", "mean"),
    actual_ppr=("actual_ppr", "mean"), projected_ppr=("projected_ppr", "mean"),
    mae=("error", "mean")).round(3).to_string())
print("\\nObservational audit only; target efficiency is descriptive, not causal.")
print("No live score, projection, rank, or weight modifications.")
