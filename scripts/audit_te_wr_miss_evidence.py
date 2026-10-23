"""Read-only triage of TE/WR ranking misses; does not infer injury causes."""
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
pred["actual_rank"] = pred.groupby(["season", "week", "position"]).actual_ppr.rank(method="min", ascending=False)
pred["projected_rank"] = pred.groupby(["season", "week", "position"]).projected_ppr.rank(method="min", ascending=False)
pred["rank_miss"] = pred.projected_rank - pred.actual_rank
histories = {(s, pid, team): group.sort_values("week")
             for (s, pid, team), group in stats.groupby(["season", "player_id", "team"])}
out = []
for position, group in pred.groupby("position"):
    for direction, selected in (("under_ranked", group.nlargest(8, "rank_miss")),
                                ("over_ranked", group.nsmallest(8, "rank_miss"))):
        for row in selected.itertuples(index=False):
            history = histories.get((row.season, row.player_id, row.team))
            prior = history.loc[history.week.lt(row.week)].tail(3) if history is not None else pd.DataFrame()
            current = history.loc[history.week.eq(row.week)] if history is not None else pd.DataFrame()
            name = getattr(row, "player_name", None)
            if not name and history is not None:
                for col in ("player_display_name", "player_name"):
                    if col in history.columns:
                        name = history.iloc[-1][col]
                        break
            out.append({
                "season": row.season, "week": row.week, "position": position,
                "player_id": row.player_id, "player_name": name or "unresolved",
                "team": row.team, "direction": direction,
                "actual_rank": row.actual_rank, "projected_rank": row.projected_rank,
                "actual_ppr": row.actual_ppr, "projected_ppr": row.projected_ppr,
                "prior_targets": ",".join(str(int(x)) for x in prior["targets"].tolist()),
                "current_game_stats_record": bool(len(current)),
                "current_game_targets": int(current.targets.sum()) if len(current) else None,
                "pregame_availability_verified": False,
                "teammate_absence_verified": False,
                "role_change_verified": False,
                "in_game_injury_verified": False,
                "cause": "unverified",
            })
report = pd.DataFrame(out)
if len(report) != 32:
    raise RuntimeError(f"Expected 32 ranking misses, got {len(report)}")
print("Historical TE/WR miss triage: 32 player-weeks")
print("Current-game stats are postgame observations, not proof of active/inactive status.")
print("All availability, injury, teammate absence, and role-change causes remain UNVERIFIED.")
for row in report.itertuples(index=False):
    print(f"{row.position} {row.direction} W{row.week} {row.player_name} ({row.team}) "
          f"rank={row.projected_rank:.0f}->{row.actual_rank:.0f} "
          f"PPR={row.projected_ppr:.2f}->{row.actual_ppr:.2f} "
          f"prior_targets=[{row.prior_targets}] "
          f"game_stats_record={row.current_game_stats_record} "
          f"game_targets={row.current_game_targets} cause=unverified")
print("Read-only audit. No live data or model changes.")
