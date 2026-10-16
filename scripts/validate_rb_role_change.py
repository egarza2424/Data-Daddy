"""Pregame RB role-change detection research. Does not modify Model F.

For each observed RB player-week, features use only earlier weeks. Outcome is
that week's realized PPR / workload. Rows with no prior observed game are
excluded; 1/2/3/4+ prior-game groups are reported separately.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path('projection-model/validation')
YEARS = (2023, 2024, 2025)
TEAM_ALIASES = {'LAR':'LA','JAX':'JAC','WAS':'WSH'}


def normalize(x):
    return TEAM_ALIASES.get(str(x).strip().upper(), str(x).strip().upper())


def read_season(year):
    path = Path(f'historical-data/player_stats_{year}.csv')
    d = pd.read_csv(path, low_memory=False)
    if 'team' not in d and 'recent_team' in d:
        d['team'] = d['recent_team']
    if 'carries' not in d and 'rushing_attempts' in d:
        d['carries'] = d['rushing_attempts']
    required = {'week','player_id','position','team','carries','targets',
                'receptions','rushing_yards','rushing_tds','receiving_yards','receiving_tds'}
    missing = required-set(d.columns)
    if missing:
        raise ValueError(f'{path} missing {sorted(missing)}')
    if 'season_type' in d:
        d = d.loc[d.season_type.eq('REG')].copy()
    d['week'] = pd.to_numeric(d.week, errors='coerce')
    d = d.loc[d.week.between(1,18)].copy()
    d['week'] = d.week.astype(int)
    d['player_id'] = d.player_id.astype(str).str.strip()
    d['team'] = d.team.map(normalize)
    for c in ('carries','targets','receptions','rushing_yards','rushing_tds',
              'receiving_yards','receiving_tds'):
        d[c] = pd.to_numeric(d[c], errors='coerce').fillna(0)
    d['opportunities'] = d.carries + d.targets
    d['ppr'] = (d.rushing_yards/10 + d.rushing_tds*6 + d.receptions +
                d.receiving_yards/10 + d.receiving_tds*6)
    # Team denominator includes all positions, never just RBs.
    team = d.groupby(['team','week']).opportunities.sum().rename('team_opportunities')
    d = d.join(team, on=['team','week'])
    d['share'] = np.where(d.team_opportunities.gt(0),d.opportunities/d.team_opportunities,np.nan)
    rb = d.loc[d.position.eq('RB')].sort_values(['player_id','week']).copy()
    if rb.duplicated(['player_id','week']).any():
        raise ValueError(f'{year}: duplicate RB player-week; resolve source before analysis')
    rows = []
    for pid,g in rb.groupby('player_id'):
        g = g.sort_values('week')
        for i in range(1,len(g)):
            current = g.iloc[i]
            if current.week < 4:
                continue
            prior = g.iloc[max(0,i-4):i]
            # Require recent observed play; don't call an old role a current role.
            if current.week-prior.iloc[-1].week > 2:
                continue
            n = len(prior)
            recent = prior.tail(min(2,n))
            old = prior.iloc[:-len(recent)]
            # No earlier comparison means trend is UNKNOWN, not zero.
            delta = float(recent.opportunities.mean()-old.opportunities.mean()) if len(old) else np.nan
            share_delta = float(recent.share.mean()-old.share.mean()) if len(old) else np.nan
            carry_delta = float(recent.carries.mean()-old.carries.mean()) if len(old) else np.nan
            target_delta = float(recent.targets.mean()-old.targets.mean()) if len(old) else np.nan
            prior_avg = float(prior.opportunities.mean())
            ppr_avg = float(prior.ppr.mean())
            rows.append(dict(season=year,week=int(current.week),player_id=pid,
                player_name=current.get('player_display_name',current.get('player_name',pid)),
                team=current.team,prior_games=n,history_group=str(n) if n<4 else '4+',
                prior_avg_opportunities=prior_avg,prior_avg_ppr=ppr_avg,
                opportunity_delta=delta,share_delta=share_delta,
                carries_delta=carry_delta,targets_delta=target_delta,
                actual_opportunities=float(current.opportunities),actual_ppr=float(current.ppr),
                opportunity_jump=int(current.opportunities >= prior_avg+5),
                ppr_breakout=int(current.ppr >= 15 and current.ppr >= ppr_avg+5)))
    return pd.DataFrame(rows)


def evaluate(df):
    # Fixed, interpretable pre-registered rules; no tuning on the test seasons.
    # One-game history: recent volume only. 2+ games: prior volume + role growth.
    d = df.copy()
    d['baseline_flag'] = (d.prior_avg_opportunities >= 12).astype(int)
    growth = (d.opportunity_delta >= 3) | (d.share_delta >= .05)
    d['role_change_flag'] = ((d.prior_avg_opportunities >= 12) |
        (growth.fillna(False) & (d.prior_avg_opportunities >= 5))).astype(int)
    metrics=[]
    for (year,group),part in d.groupby(['season','history_group']):
        for target in ('opportunity_jump','ppr_breakout'):
            y=part[target].to_numpy(int)
            for model in ('baseline_flag','role_change_flag'):
                p=part[model].to_numpy(int)
                tp=int(((p==1)&(y==1)).sum()); fp=int(((p==1)&(y==0)).sum())
                fn=int(((p==0)&(y==1)).sum()); tn=int(((p==0)&(y==0)).sum())
                metrics.append(dict(season=year,history_group=group,target=target,rule=model,
                    rows=len(part),positives=int(y.sum()),flagged=int(p.sum()),TP=tp,FP=fp,FN=fn,TN=tn,
                    precision=tp/(tp+fp) if tp+fp else np.nan,
                    recall=tp/(tp+fn) if tp+fn else np.nan,
                    base_rate=float(y.mean()),lift=(tp/(tp+fp))/y.mean() if tp+fp and y.mean()>0 else np.nan))
    return d,pd.DataFrame(metrics)


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    frames=[read_season(y) for y in YEARS]
    df=pd.concat(frames,ignore_index=True)
    if df.empty:
        raise RuntimeError('No eligible player-weeks')
    detail,metrics=evaluate(df)
    detail.to_csv(ROOT/'rb-role-change-player-weeks.csv',index=False)
    metrics.to_csv(ROOT/'rb-role-change-metrics.csv',index=False)
    print(metrics.to_string(index=False))
    print('NOTE: 1-game trends are unknown; short-history rows are never imputed as negative trends.')
    print('Outcome labels are research definitions, not production Model F scores.')

if __name__=='__main__':
    main()
