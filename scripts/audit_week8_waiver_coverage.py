"""Review-only diagnostic for Week 8 waiver candidate coverage.

Uses the same player_lookup/opportunity_volume and scheduled-game exclusion
as build_waiver_wire.py. Does not modify scores, eligibility or live outputs.
"""
import csv
import json
from pathlib import Path

from build_waiver_wire import (fetch_nfl_schedule, normalized_name, load_ownership,
                               fetch_espn_ownership, ownership_summary,
                               rank_eligible_candidates)

SOURCE = Path("nfl-stats.json")
OUT = Path("projection-model/validation/2026-week8-waiver-coverage-diagnostic.csv")
WATCH = ["Antonio Williams", "Caleb Douglas", "Chig Okonkwo", "Seth McGowan"]
def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    season = int(data["season"])
    target = int(data["target_week"])
    players = data.get("player_lookup", {})
    opp = data.get("opportunity_volume", {})
    weeks, _, _, _ = fetch_nfl_schedule(season)
    saved_ownership = load_ownership()
    try:
        espn, _, _ = fetch_espn_ownership(players)
        espn_error = None
    except Exception as exc:
        espn, espn_error = {}, str(exc)
    candidate_pool = []
    for pid, player in players.items():
        position = player.get('position')
        if position not in {'QB', 'RB', 'WR', 'TE'}:
            continue
        games = sorted((g for g in opp.get(pid, {}).get('games', [])
                        if int(g.get('season') or 0) == season),
                       key=lambda g: int(g.get('week') or 0), reverse=True)
        if not games:
            continue
        latest_week = int(games[0].get('week') or 0)
        team = str(player.get('team') or '').upper()
        schedule_team = 'LA' if team == 'LAR' else team
        if any(w in weeks.get(schedule_team, set())
               for w in range(latest_week + 1, target)):
            continue
        latest = float(games[0].get('opportunity_value') or 0)
        previous = [float(g.get('opportunity_value') or 0) for g in games[1:4]]
        baseline = sum(previous) / len(previous) if previous else None
        ownership = dict(saved_ownership.get(pid, {}))
        ownership.update(espn.get(pid, {}))
        candidate_pool.append({
            'player_id': pid, 'name': player.get('name'), 'position': position,
            'latest_opportunity': latest,
            'opportunity_change': round(latest - baseline, 2) if baseline is not None else None,
            'recent_average_ppr': data.get('recent_player_performance', {}).get(pid, {}).get('average_ppr'),
            **ownership_summary(ownership),
        })
    ranked = rank_eligible_candidates(candidate_pool)
    by_id = {c['player_id']: c for c in ranked}
    rows = []
    for name in WATCH:
        matched = [(pid,p) for pid,p in players.items()
                   if normalized_name(p.get("name")) == normalized_name(name)]
        if not matched:
            rows.append({"name":name,"source_player_present":False,
                         "reason":"ABSENT_FROM_PLAYER_LOOKUP"})
            continue
        for pid,p in matched:
            games = sorted((g for g in opp.get(pid,{}).get("games",[])
                            if int(g.get("season") or 0)==season),
                           key=lambda g:int(g.get("week") or 0),reverse=True)
            latest = int(games[0].get("week") or 0) if games else None
            team = str(p.get("team") or "").upper()
            scheduled = "LA" if team=="LAR" else team
            missed = [w for w in range((latest or 0)+1,target)
                      if w in weeks.get(scheduled,set())] if latest else []
            reason = ("NO_SEASON_OPPORTUNITY_GAMES" if not games else
                      "SKIPPED_AFTER_MISSED_SCHEDULED_WEEK" if missed else
                      "PASSED_INITIAL_SOURCE_FILTER")
            ownership = dict(saved_ownership.get(pid, {}))
            ownership.update(espn.get(pid, {}))
            summary = ownership_summary(ownership)
            ranked_player = by_id.get(pid, {})
            preliminary_rank = ranked_player.get('preliminary_waiver_rank')
            rows.append({"name":name,"source_player_present":True,
                         "player_id":pid,"team":team,"position":p.get("position"),
                         "latest_recorded_week":latest,
                         "missed_scheduled_weeks":";".join(map(str,missed)),
                         "reason":reason,
                         "ownership_eligible":summary.get("ownership_eligible"),
                         "average_rostered":summary.get("average_rostered"),
                         "ownership_source_count":summary.get("ownership_source_count"),
                         "preliminary_rank":preliminary_rank,
                         "waiver_evidence_score":ranked_player.get("waiver_evidence_score"),
                         "top50_exported":preliminary_rank is not None and preliminary_rank <= 50,
                         "ownership_diagnostic":("ESPN_FETCH_FAILED: "+espn_error if espn_error else
                                                 "NO_VERIFIED_OWNERSHIP" if summary.get("ownership_eligible") is None else
                                                 "AT_OR_ABOVE_65_PERCENT" if summary.get("ownership_eligible") is False else
                                                 "ELIGIBLE_CHECK_RANK_AND_TOP50_EXPORT"),
                         "note":"Later ownership/availability checks may still exclude player"})
    OUT.parent.mkdir(parents=True,exist_ok=True)
    columns=["name","source_player_present","player_id","team","position",
             "latest_recorded_week","missed_scheduled_weeks","reason",
             "ownership_eligible","average_rostered","ownership_source_count",
             "ownership_diagnostic","preliminary_rank","waiver_evidence_score",
             "top50_exported","note"]
    with OUT.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    for r in rows: print(r)
    print("Saved",OUT,"— review only; no live changes")
if __name__=="__main__": main()
