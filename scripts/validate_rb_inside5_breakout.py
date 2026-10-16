"""Inside-5 RB pregame research: rushes, targets, team share and next-week breakout ranking."""
import csv,gzip
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

OUT=Path("projection-model/validation")
def read_pbp(year):
    player=defaultdict(lambda: [0,0])
    team=defaultdict(lambda: [0,0])
    p=Path(f"historical-data/play_by_play_{year}.csv.gz")
    with gzip.open(p,"rt",encoding="utf-8",newline="") as f:
        for play in csv.DictReader(f):
            if play.get("season_type")!="REG":continue
            try:
                w=int(float(play.get("week") or 0))
                yard=float(play.get("yardline_100") or "nan")
            except ValueError:continue
            if not (1<=w<=18 and np.isfinite(yard) and 0<=yard<=5):continue
            t=str(play.get("posteam") or "").strip().upper()
            t={"LAR":"LA","JAX":"JAC","WAS":"WSH"}.get(t,t)
            rush=play.get("rush_attempt")=="1"
            target=play.get("pass_attempt")=="1" and bool(play.get("receiver_player_id"))
            if rush:
                pid=str(play.get("rusher_player_id") or "").strip()
                if pid:
                    player[(pid,w)][0]+=1
                    team[(t,w)][0]+=1
            if target:
                pid=str(play.get("receiver_player_id") or "").strip()
                player[(pid,w)][1]+=1
                team[(t,w)][1]+=1
    return player,team

def main():
    df=pd.read_csv(OUT/"rb-breakout-ranked-player-weeks.csv")
    required={"season","week","player_id","team","breakout_score","baseline_score","ppr_breakout","prior_games"}
    if missing:=required-set(df.columns):raise ValueError(f"Missing {sorted(missing)}")
    rows={}
    for year,g in df.groupby("season"):
        player,team=read_pbp(int(year))
        for idx,row in g.iterrows():
            w=int(row.week);pid=str(row.player_id);t=str(row.team).upper()
            t={"LAR":"LA","JAX":"JAC","WAS":"WSH"}.get(t,t)
            weeks=range(max(1,w-3),w)
            rush=sum(player[(pid,k)][0] for k in weeks)
            targets=sum(player[(pid,k)][1] for k in weeks)
            trush=sum(team[(t,k)][0] for k in weeks)
            ttarg=sum(team[(t,k)][1] for k in weeks)
            rows[idx]=(rush,targets,trush,ttarg,(rush+targets)/(trush+ttarg) if trush+ttarg else np.nan)
    cols=["inside5_rush_3w","inside5_targets_3w","team_inside5_rush_3w","team_inside5_targets_3w","inside5_share_3w"]
    df[cols]=pd.DataFrame.from_dict(rows,orient="index",columns=cols).reindex(df.index)
    # Two fixed challengers: bonus for goal-line rush and target opportunity.
    group=df.groupby(["season","week"])
    def pct(col):return group[col].rank(pct=True).fillna(.5)
    for name,weight in [("inside5_10pct",.1),("inside5_20pct",.2)]:
        signal=.5*pct("inside5_rush_3w")+.3*pct("inside5_targets_3w")+.2*pct("inside5_share_3w")
        df[name]=(1-weight)*df.breakout_score+weight*signal
    df.to_csv(OUT/"rb-inside5-breakout-player-weeks.csv",index=False)
    results=[]
    for year,season in df.groupby("season"):
        for name in ["baseline_score","breakout_score","inside5_10pct","inside5_20pct"]:
            ordered=season.sort_values(["week",name,"player_id"],ascending=[True,False,True])
            for k in [10,20]:
                top=ordered.groupby("week").head(k)
                results.append(dict(season=year,variant=name,k=k,weeks=season.week.nunique(),
                                    picks=len(top),hits=int(top.ppr_breakout.sum()),
                                    precision=float(top.ppr_breakout.mean())))
    summary=pd.DataFrame(results)
    summary.to_csv(OUT/"rb-inside5-breakout-ranking-metrics.csv",index=False)
    print(summary.to_string(index=False))
    print("Research only. No production edits. Goal-line signals use prior three calendar weeks.")
if __name__=="__main__":main()
