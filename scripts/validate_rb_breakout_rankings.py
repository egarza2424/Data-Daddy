"""Research-only, pregame RB breakout ranking validation. Never edits production."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

FEATURES=['prior_avg_opportunities','prior_avg_ppr','opportunity_delta','share_delta','carries_delta','targets_delta']

def load(path):
    df=pd.read_csv(path)
    needed={'season','week','player_id','prior_games','ppr_breakout','opportunity_jump',*FEATURES}
    missing=needed-set(df.columns)
    if missing: raise ValueError(f'Missing columns: {sorted(missing)}')
    for col in ['season','week','prior_games','ppr_breakout','opportunity_jump',*FEATURES]:
        df[col]=pd.to_numeric(df[col],errors='coerce')
    df=df.dropna(subset=['season','week','player_id','prior_games','ppr_breakout']).copy()
    df=df[df.prior_games>=1].copy()
    if df.duplicated(['season','week','player_id']).any():
        raise ValueError('Duplicate season/week/player rows')
    # Unknown trends remain missing, never interpreted as evidence of decline.
    for col in ['opportunity_delta','share_delta','carries_delta','targets_delta']:
        df[col+'_known']=df[col].notna().astype(int)
    return df

def rank_score(df,variant):
    # Rank-percentiles are calculated within each pregame player pool, without targets.
    group=df.groupby(['season','week'])
    def pct(col):
        return group[col].rank(pct=True,method='average').fillna(0.5)
    base=pct('prior_avg_opportunities')
    if variant=='workload': return base
    if variant=='production': return pct('prior_avg_ppr')
    # Missing trends contribute no positive bonus, rather than a negative value.
    growth=df.opportunity_delta.clip(lower=0).fillna(0)
    share=df.share_delta.clip(lower=0).fillna(0)
    targets=df.targets_delta.clip(lower=0).fillna(0)
    carries=df.carries_delta.clip(lower=0).fillna(0)
    def bonus(values):
        return values.groupby([df.season,df.week]).rank(pct=True).where(values.gt(0),0).fillna(0)
    growth_score=bonus(growth)
    share_score=bonus(share)
    target_score=bonus(targets)
    carry_score=bonus(carries)
    if variant=='growth': return 0.5*base+0.5*growth_score
    if variant=='balanced': return 0.4*base+0.3*growth_score+0.2*share_score+0.1*target_score
    if variant=='receiving': return 0.35*base+0.25*growth_score+0.15*share_score+0.25*target_score
    if variant=='rushing': return 0.35*base+0.25*growth_score+0.15*share_score+0.25*carry_score
    raise ValueError(variant)

def evaluate(df,variant,k,target='ppr_breakout'):
    x=df.copy()
    x['score']=rank_score(x,variant)
    x=x.sort_values(['season','week','score','player_id'],ascending=[True,True,False,True])
    x['rank']=x.groupby(['season','week']).cumcount()+1
    top=x[x['rank']<=k]
    return {'variant':variant,'k':k,'target':target,'weeks':x.groupby(['season','week']).ngroups,
            'picks':len(top),'hits':int(top[target].sum()),
            'precision_at_k':float(top[target].mean()) if len(top) else np.nan,
            'base_rate':float(x[target].mean()),
            'lift':float(top[target].mean()/x[target].mean()) if x[target].mean()>0 and len(top) else np.nan}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,default=Path('projection-model/validation/rb-role-change-player-weeks.csv'))
    parser.add_argument('--out',type=Path,default=Path('projection-model/validation'))
    args=parser.parse_args()
    df=load(args.input)
    if not {2023,2024,2025}.issubset(set(df.season)):
        raise ValueError('Expected 2023, 2024, and 2025 historical seasons')
    variants=['workload','production','growth','balanced','receiving','rushing']
    # Select using 2023-24 only. 2025 must not influence model choice.
    development=df[df.season.isin([2023,2024])]
    selection=pd.DataFrame([evaluate(development,v,k) for v in variants for k in (10,20)])
    # Pick challenger by development P@10, then P@20, fixed tie-break order.
    candidate=selection[selection.variant.isin(['growth','balanced','receiving','rushing'])]
    pivot=candidate.pivot(index='variant',columns='k',values='precision_at_k')
    winner=pivot.sort_values([10,20],ascending=False,kind='stable').index[0]
    chosen=['workload','production',winner]
    records=[]
    for year in (2023,2024,2025):
        season=df[df.season==year]
        for history,part in [('all',season),('1-2',season[season.prior_games<=2]),('3',season[season.prior_games==3]),('4+',season[season.prior_games>=4])]:
            if part.empty: continue
            for target in ('ppr_breakout','opportunity_jump'):
                for k in (10,20):
                    for variant in chosen:
                        records.append({'season':year,'history_group':history,**evaluate(part,variant,k,target)})
    args.out.mkdir(parents=True,exist_ok=True)
    selection.to_csv(args.out/'rb-breakout-development-search.csv',index=False)
    pd.DataFrame(records).to_csv(args.out/'rb-breakout-ranking-metrics.csv',index=False)
    ranked=df.copy()
    ranked['baseline_score']=rank_score(df,'workload')
    ranked['breakout_score']=rank_score(df,winner)
    ranked=ranked.sort_values(['season','week','breakout_score','player_id'],ascending=[True,True,False,True])
    ranked['breakout_rank']=ranked.groupby(['season','week']).cumcount()+1
    ranked.to_csv(args.out/'rb-breakout-ranked-player-weeks.csv',index=False)
    print(f'Development-selected challenger: {winner}')
    print(pd.DataFrame(records).query("season==2025 and history_group=='all' and target=='ppr_breakout'").to_string(index=False))
    print('Research only; no production changes. Rankings are per season/week, not global.')

if __name__=='__main__': main()
