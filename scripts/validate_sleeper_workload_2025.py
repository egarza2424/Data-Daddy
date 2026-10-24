"""2025 held-out feasibility audit for a workload-aware sleeper challenger.

Uses only player statistics from weeks strictly BEFORE the target week.
This does NOT backtest the proposed injury score: verified pregame OUT labels,
beneficiary assignments, and historical market ranks are not yet available.
Baseline is the existing 2025 Model F projected PPR, not the live JS sleeper score.
"""
from pathlib import Path
import pandas as pd
import numpy as np

PRED=Path("projection-model/2025-ppr-walkforward-predictions.csv")
STATS=Path("historical-data/player_stats_2025.csv")
OUT=Path("projection-model/validation/2025-sleeper-workload-heldout.csv")
p=pd.read_csv(PRED,low_memory=False)
p=p.loc[p.model.eq("F_position_specific") & p.position.isin(["RB","WR","TE","QB"])].copy()
s=pd.read_csv(STATS,low_memory=False)
for df in (p,s):
    df["player_id"]=df.player_id.astype(str)
    df["week"]=pd.to_numeric(df.week,errors="coerce")
    df["season"]=pd.to_numeric(df.season,errors="coerce")
for col in ("carries","targets"):
    if col not in s.columns:raise SystemExit(f"Missing {col} in historical stats")
    s[col]=pd.to_numeric(s[col],errors="coerce").fillna(0)
for col in ("projected_ppr","actual_ppr"):
    p[col]=pd.to_numeric(p[col],errors="coerce")
s=s.loc[s.position.isin(["RB","WR","TE","QB"])].copy()
s["opps"]=s.carries+s.targets
hist={}
for (season,pid),g in s.groupby(["season","player_id"]):
    hist[(season,pid)]=g.sort_values("week")[["week","opps"]]
rows=[]
for r in p.itertuples(index=False):
    if pd.isna(r.projected_ppr) or pd.isna(r.actual_ppr):continue
    history=hist.get((r.season,r.player_id))
    if history is None:continue
    prior=history.loc[history.week.lt(r.week)].tail(4)
    if len(prior)<2:continue
    rows.append(dict(week=int(r.week),position=r.position,player_id=r.player_id,
        player_name=r.player_name,actual_ppr=float(r.actual_ppr),
        projected_ppr=float(r.projected_ppr),prior_games=len(prior),
        prior_opps=float(prior.opps.mean())))
df=pd.DataFrame(rows)
if df.empty:raise SystemExit("No matched held-out historical rows")
# Week >= 10 holds out later weeks; no weight fitting is performed.
df=df.loc[df.week.ge(10)].copy()
if df.empty:raise SystemExit("No week 10+ rows with >=2 pregame observations")
# Compare within position/week only, to avoid cross-position workload distortion.
df["baseline_rank"]=df.groupby(["week","position"]).projected_ppr.rank(ascending=False,method="min")
df["workload_rank"]=df.groupby(["week","position"]).prior_opps.rank(ascending=False,method="min")
df["actual_rank"]=df.groupby(["week","position"]).actual_ppr.rank(ascending=False,method="min")
# A deliberately simple proxy: mean of percentile ranks, not the 30/25/20/10/15
# proposal; it tests whether historical usage can help identify productive players.
df["base_pct"]=df.groupby(["week","position"]).projected_ppr.rank(pct=True)
df["work_pct"]=df.groupby(["week","position"]).prior_opps.rank(pct=True)
df["proxy"]=.8*df.base_pct+.2*df.work_pct
df["proxy_rank"]=df.groupby(["week","position"]).proxy.rank(ascending=False,method="min")
df["base_error"]=(df.baseline_rank-df.actual_rank).abs()
df["proxy_error"]=(df.proxy_rank-df.actual_rank).abs()
OUT.parent.mkdir(parents=True,exist_ok=True)
df.to_csv(OUT,index=False)
print("2025 WEEK 10+ HISTORICAL WORKLOAD FEASIBILITY AUDIT")
print("Rows:",len(df),"weeks:",sorted(df.week.unique().tolist()))
print("BASELINE: existing Model F PPR rank; PROXY: 80% baseline percentile + 20% prior-four-game workload percentile")
print("NOT the live Sleeper Score and NOT a backtest of injury-created opportunity.")
print("Mean rank error: baseline",round(df.base_error.mean(),3),"proxy",round(df.proxy_error.mean(),3))
for pos,sub in df.groupby("position"):
    print(pos,"n",len(sub),"baseline",round(sub.base_error.mean(),3),"proxy",round(sub.proxy_error.mean(),3))
    for k in ([12,24] if pos in ("RB","WR") else [12]):
        actual=sub.actual_rank.le(k)
        if actual.sum():
            print(" top",k,"actual recall: baseline",round((sub.loc[actual,"baseline_rank"]<=k).mean(),3),
                  "proxy",round((sub.loc[actual,"proxy_rank"]<=k).mean(),3))
print("GATE: Historical verified pregame starter OUT/QUESTIONABLE, beneficiary role, and contemporaneous market ranks required before injury-weight validation or production promotion.")
print("Saved",OUT,"; no production files changed.")
