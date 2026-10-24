"""Historical RB absence/beneficiary screening, NOT verified injury backtest.
No game-week outcomes are used to infer pregame starter status or beneficiary role.
"""
from pathlib import Path
import pandas as pd

SRC=Path("historical-data/player_stats_2025.csv")
OUT=Path("projection-model/validation/2025-rb-absence-role-review.csv")
df=pd.read_csv(SRC,low_memory=False)
team="recent_team" if "recent_team" in df else "team"
name="player_display_name" if "player_display_name" in df else "player_name"
for col in ["season","week","carries","targets"]:
    if col not in df:raise SystemExit(f"Missing required column: {col}")
    df[col]=pd.to_numeric(df[col],errors="coerce").fillna(0)
df=df[df.position.eq("RB")].copy()
df["opps"]=df.carries+df.targets
rows=[]
for (season,t),g in df.groupby(["season",team]):
    weeks=sorted(g.week.unique())
    for w in weeks:
        previous=g[g.week.lt(w)&g.week.ge(w-4)]
        if previous.week.nunique()<2:continue
        prior=previous.groupby("player_id",as_index=False).agg(
            prior_opps=("opps","sum"),prior_games=("week","nunique"),
            player_name=(name,"last"))
        prior["prior_per_game"]=prior.prior_opps/prior.prior_games
        prior=prior.sort_values("prior_per_game",ascending=False)
        if prior.empty or prior.iloc[0].prior_per_game<8:continue
        lead=prior.iloc[0]
        current=g[g.week.eq(w)]
        if str(lead.player_id) in set(current.player_id.astype(str)):continue
        # Absence in game logs is not a verified injury or pregame OUT.
        for _,b in prior.iloc[1:].iterrows():
            observed=current[current.player_id.astype(str).eq(str(b.player_id))]
            if observed.empty:continue
            observed_opps=float(observed.opps.sum())
            rows.append(dict(season=int(season),week=int(w),team=t,
                missing_prior_leader=lead.player_name,leader_prior_opps_per_game=round(float(lead.prior_per_game),2),
                candidate=b.player_name,candidate_prior_opps_per_game=round(float(b.prior_per_game),2),
                candidate_observed_opps=observed_opps,
                observed_opportunity_change=round(observed_opps-float(b.prior_per_game),2),
                pregame_injury_status="UNVERIFIED",beneficiary_role="UNVERIFIED",
                eligible_for_injury_score=False))
out=pd.DataFrame(rows)
OUT.parent.mkdir(parents=True,exist_ok=True)
out.to_csv(OUT,index=False)
print("2025 RB ABSENCE REVIEW (NOT PREGAME INJURY VALIDATION)")
print("Candidate rows:",len(out))
if not out.empty:
    print("Missing-leader team-weeks:",out[["season","week","team","missing_prior_leader"]].drop_duplicates().shape[0])
    print("Observed candidate opportunity change mean:",round(out.observed_opportunity_change.mean(),2))
print("No injury status inferred from game logs. Observed target-week outcomes are diagnostic only, never pregame features.")
print("NEXT GATE: match timestamped pregame inactive reports and independently verified beneficiary roles before testing injury weights.")
print("Saved",OUT,"; no live changes.")
