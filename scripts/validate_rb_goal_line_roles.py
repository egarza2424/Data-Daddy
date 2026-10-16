"""Research-only RB goal-line role persistence, 2023-25; strictly prior-week features."""
import csv
import gzip
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

YEARS = (2023, 2024, 2025)
OUT = Path('projection-model/validation')
ALIASES = {'LAR':'LA', 'JAX':'JAC', 'WAS':'WSH'}

def norm(x):
    x = str(x or '').strip().upper()
    return ALIASES.get(x, x)

def load_weekly(year):
    path = Path(f'historical-data/player_stats_{year}.csv')
    df = pd.read_csv(path, low_memory=False)
    if 'team' not in df and 'recent_team' in df:
        df['team'] = df.recent_team
    needed = {'player_id','position','week','team','carries','targets','rushing_tds','receiving_tds', 'rushing_yards','receiving_yards','receptions'}
    if missing := needed-set(df.columns):
        raise ValueError(f'{path}: missing {sorted(missing)}')
    if 'season_type' in df:
        df = df[df.season_type.eq('REG')]
    df = df[df.position.eq('RB')].copy()
    df['week'] = pd.to_numeric(df.week,errors='coerce')
    df = df[df.week.between(1,18)]
    df['week'] = df.week.astype(int)
    df['player_id'] = df.player_id.astype(str).str.strip()
    df['team'] = df.team.map(norm)
    for col in ['carries','targets','rushing_tds','receiving_tds','rushing_yards','receiving_yards','receptions']:
        df[col] = pd.to_numeric(df[col],errors='coerce').fillna(0)
    df['ppr'] = df.rushing_tds*6+df.receiving_tds*6+df.rushing_yards/10+df.receiving_yards/10+df.receptions
    if df.duplicated(['player_id','week']).any():
        raise ValueError(f'{year}: duplicate player-week; check stats source')
    return df

def load_pbp(year):
    """Counts actual rushes and targeted passes at 1-5 yards from goal; team totals include all positions."""
    player = defaultdict(lambda: [0,0,0])
    team = defaultdict(lambda: [0,0])
    path = Path(f'historical-data/play_by_play_{year}.csv.gz')
    with gzip.open(path,'rt',encoding='utf-8',newline='') as fh:
        for play in csv.DictReader(fh):
            if play.get('season_type') != 'REG':
                continue
            try:
                if int(float(play.get('season') or 0)) != year:
                    continue
                week = int(float(play.get('week') or 0))
                yard = float(play.get('yardline_100') or 'nan')
            except (TypeError,ValueError):
                continue
            if not (1<=week<=18 and np.isfinite(yard) and 0<yard<=5):
                continue
            t = norm(play.get('posteam'))
            if not t or t in ('NAN','NONE'):
                continue
            if play.get('rush_attempt') == '1':
                pid = str(play.get('rusher_player_id') or '').strip()
                if pid:
                    player[(pid,week)][0]+=1
                    team[(t,week)][0]+=1
                    if play.get('touchdown')=='1' or play.get('rush_touchdown')=='1':
                        player[(pid,week)][2]+=1
            if play.get('pass_attempt')=='1':
                pid = str(play.get('receiver_player_id') or '').strip()
                if pid:
                    player[(pid,week)][1]+=1
                    team[(t,week)][1]+=1
    return player,team

def build(year):
    weekly=load_weekly(year)
    player,team=load_pbp(year)
    rows=[]
    for row in weekly.itertuples(index=False):
        week=int(row.week)
        if week<4:continue
        # Calendar windows prevent future leakage; bye weeks contain no player opportunities.
        prev3=list(range(week-3,week))
        prev1=[week-1]
        def count(weeks,idx):
            return sum(player[(row.player_id,w)][idx] for w in weeks)
        def teamcount(weeks,idx):
            return sum(team[(row.team,w)][idx] for w in weeks)
        rush3=count(prev3,0); target3=count(prev3,1)
        trush3=teamcount(prev3,0); ttarget3=teamcount(prev3,1)
        rush1=count(prev1,0); trush1=teamcount(prev1,0)
        # Unknown denominator is explicitly missing, not a zero share.
        share3=rush3/trush3 if trush3 else np.nan
        share1=rush1/trush1 if trush1 else np.nan
        targetshare3=target3/ttarget3 if ttarget3 else np.nan
        rows.append(dict(season=year,week=week,player_id=row.player_id,team=row.team,
            player_name=getattr(row,'player_display_name',getattr(row,'player_name',row.player_id)),
            prior_games=int(((weekly.player_id==row.player_id)&(weekly.week<week)).sum()),
            prior_inside5_rush3=rush3,prior_inside5_target3=target3,
            team_inside5_rush3=trush3,team_inside5_target3=ttarget3,
            inside5_rush_share3=share3,inside5_target_share3=targetshare3,
            inside5_rush_share1=share1,
            rush_share_change=(share1-share3) if np.isfinite(share1) and np.isfinite(share3) else np.nan,
            next_inside5_rush=player[(row.player_id,week)][0],
            next_inside5_target=player[(row.player_id,week)][1],
            next_inside5_rush_td=player[(row.player_id,week)][2],
            team_next_inside5_rush=team[(row.team,week)][0],
            next_ppr=row.ppr))
    return pd.DataFrame(rows)

def metrics(df,score_col,label):
    result=[]
    for (year,group),g in df.groupby(['season','history_group']):
        # Top-k per week, deterministic tie-break. Ranking uses only pregame features.
        g=g.sort_values(['week',score_col,'player_id'],ascending=[True,False,True])
        for k in (5,10):
            top=g.groupby('week').head(k)
            result.append(dict(season=year,history_group=group,model=label,k=k,
                selections=len(top),weeks=g.week.nunique(),
                inside5_rush_hit_rate=float((top.next_inside5_rush>0).mean()),
                inside5_target_hit_rate=float((top.next_inside5_target>0).mean()),
                rush_td_hit_rate=float((top.next_inside5_rush_td>0).mean()),
                avg_next_inside5_rush=float(top.next_inside5_rush.mean()),
                avg_next_ppr=float(top.next_ppr.mean())))
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    df=pd.concat([build(y) for y in YEARS],ignore_index=True)
    if df.empty:raise RuntimeError('No eligible observations')
    df['history_group']=np.select([df.prior_games<=2,df.prior_games==3],['1-2','3'],default='4+')
    # Explicit baselines and candidate signals; no parameter selection on 2025.
    df['baseline_score']=df.prior_inside5_rush3.astype(float)
    df['share_score']=df.inside5_rush_share3.fillna(-1)
    df['persistence_score']=df.prior_inside5_rush3+2*df.inside5_rush_share3.fillna(0)
    df['target_score']=df.prior_inside5_target3.astype(float)
    # Group-level reporting includes all eligible players, not only goal-line users.
    frames=[df.assign(history_group='all'),df]
    records=[]
    for frame in frames:
        for score,label in [('baseline_score','prior rushing volume'),('share_score','prior rushing share'),
                            ('persistence_score','volume + share'),('target_score','prior target volume')]:
            records+=metrics(frame,score,label)
    df.to_csv(OUT/'rb-goal-line-role-player-weeks.csv',index=False)
    pd.DataFrame(records).to_csv(OUT/'rb-goal-line-role-metrics.csv',index=False)
    print(pd.DataFrame(records).query("season==2025 and history_group=='all'").to_string(index=False))
    print('Research only. No Model F or waiver ranking changes.')
    print('Caveat: only observed player-weeks; inactive players are not in the evaluation universe.')

if __name__=='__main__':main()
