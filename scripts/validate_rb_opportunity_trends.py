"""Isolated pregame RB opportunity-trend research; never updates live projections."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

BASE = ['opportunity_score','production_score','usage_score','redzone_score','model_confidence_score']
ALIASES = {'LAR':'LA','JAX':'JAC','WAS':'WSH'}

def key(x):
    return ALIASES.get(str(x).strip().upper(),str(x).strip().upper())

def evaluate(year, root):
    hist = pd.read_csv(root / f'projection-model/{year}-historical-ppr-dataset.csv',low_memory=False)
    stats = pd.read_csv(root / f'historical-data/player_stats_{year}.csv',low_memory=False)
    stats.columns = stats.columns.str.strip()
    required = {'week','player_id','position','team','carries','targets'}
    if missing := required - set(stats.columns):
        raise ValueError(f'{year} missing weekly stat fields: {sorted(missing)}')
    stats = stats.loc[stats.position.eq('RB')].copy()
    stats['week'] = pd.to_numeric(stats.week,errors='coerce')
    stats['player_id'] = stats.player_id.astype(str).str.strip()
    stats['team'] = stats.team.map(key)
    for col in ('carries','targets'):
        stats[col] = pd.to_numeric(stats[col],errors='coerce').fillna(0)
    stats = stats.dropna(subset=['week']).sort_values(['week','player_id'])
    stats['week'] = stats.week.astype(int)
    # Team totals require ALL positions; use original weekly file, not RB-only stats.
    full = pd.read_csv(root / f'historical-data/player_stats_{year}.csv',usecols=['week','team','carries','targets'])
    full['week'] = pd.to_numeric(full.week,errors='coerce')
    full = full.dropna(subset=['week'])
    full['week'] = full.week.astype(int)
    full['team'] = full.team.map(key)
    for col in ('carries','targets'):
        full[col] = pd.to_numeric(full[col],errors='coerce').fillna(0)
    totals = full.groupby(['team','week'])[['carries','targets']].sum().rename(columns={'carries':'team_carries','targets':'team_targets'})
    stats = stats.join(totals,on=['team','week'])
    stats['opportunities'] = stats.carries + stats.targets
    stats['team_opportunities'] = stats.team_carries + stats.team_targets
    stats['role_share'] = np.where(stats.team_opportunities>0,stats.opportunities/stats.team_opportunities,np.nan)
    hist = hist.loc[hist.position.eq('RB')].copy()
    hist['player_id'] = hist.player_id.astype(str).str.strip()
    hist['week'] = pd.to_numeric(hist.week,errors='coerce')
    hist['team'] = hist.team.map(key)
    features=[]
    by_player = {pid:group.sort_values('week') for pid,group in stats.groupby('player_id')}
    for row in hist.itertuples(index=False):
        if pd.isna(row.week):
            continue
        week=int(row.week)
        games=by_player.get(row.player_id)
        if games is None:
            continue
        prior=games.loc[games.week.lt(week)].tail(4)
        # Last two available games vs preceding two; require 4 games to establish trend.
        if len(prior)<4:
            continue
        older,newer=prior.iloc[:2],prior.iloc[2:]
        if older.role_share.isna().any() or newer.role_share.isna().any():
            continue
        # Prevent stale role trends when a player missed recent calendar weeks.
        if week-int(newer.week.max())>2:
            continue
        features.append({'player_id':row.player_id,'week':week,'team':row.team,
                         'opportunity_trend':float(newer.opportunities.mean()-older.opportunities.mean()),
                         'role_share_trend':float(newer.role_share.mean()-older.role_share.mean()),
                         'prior_games':len(prior)})
    f=pd.DataFrame(features)
    if f.empty:
        raise ValueError(f'{year}: no eligible pregame trend records')
    # Merge on player/week only; team changes are allowed, but trend is based on prior games.
    df=hist.merge(f,on=['player_id','week'],how='inner',suffixes=('','_trend'))
    for col in BASE+['actual_ppr','opportunity_trend','role_share_trend']:
        df[col]=pd.to_numeric(df[col],errors='coerce')
    df=df.replace([np.inf,-np.inf],np.nan).dropna(subset=BASE+['actual_ppr','opportunity_trend','role_share_trend'])
    train=df[df.week.between(4,12)].copy()
    test=df[df.week.between(13,18)].copy()
    if len(train)<40 or len(test)<30:
        raise ValueError(f'{year}: insufficient common train/test rows ({len(train)}/{len(test)})')
    variants={'Model F baseline':BASE,'Opportunity trend':BASE+['opportunity_trend'],
              'Role-share trend':BASE+['role_share_trend']}
    summary=[]
    actual=test.actual_ppr.to_numpy(float)
    for name,cols in variants.items():
        xtrain=np.c_[np.ones(len(train)),train[cols].to_numpy(float)]
        xtest=np.c_[np.ones(len(test)),test[cols].to_numpy(float)]
        coef=np.linalg.lstsq(xtrain,train.actual_ppr.to_numpy(float),rcond=None)[0]
        pred=xtest@coef
        label={'Model F baseline':'baseline_prediction','Opportunity trend':'opportunity_prediction','Role-share trend':'role_prediction'}[name]
        test[label]=pred
        rho=spearmanr(pred,actual).statistic
        summary.append({'season':year,'model':name,'MAE':round(float(np.mean(np.abs(pred-actual))),4),
                        'RMSE':round(float(np.sqrt(np.mean((pred-actual)**2))),4),
                        'Spearman':round(float(rho),4) if np.isfinite(rho) else np.nan,
                        'train_rows':len(train),'test_rows':len(test)})
    out=root/'projection-model/validation'
    out.mkdir(parents=True,exist_ok=True)
    columns=['week','player_id','player_name','team','actual_ppr','opportunity_trend','role_share_trend','prior_games',
             'baseline_prediction','opportunity_prediction','role_prediction']
    test[columns].to_csv(out/f'{year}-rb-opportunity-trends-backtest.csv',index=False)
    pd.DataFrame(summary).to_csv(out/f'{year}-rb-opportunity-trends-summary.csv',index=False)
    return summary

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path('.'))
    args=parser.parse_args()
    all_rows=[]
    for year in (2023,2024,2025):
        all_rows.extend(evaluate(year,args.root))
    summary=pd.DataFrame(all_rows)
    summary.to_csv(args.root/'projection-model/validation/2023-2025-rb-opportunity-trends-summary.csv',index=False)
    print(summary.to_string(index=False))
    print('Research only. Production model unchanged. Limited-history players excluded, not assigned negative trends.')

if __name__=='__main__':
    main()
