"""Read-only J2 receiving-heavy error investigation across 2024 and 2025."""
from pathlib import Path
import pandas as pd

ROOT=Path('projection-model')
results=[]
for season in (2024,2025):
    history=pd.read_csv(ROOT/f'{season}-historical-ppr-dataset.csv')
    predictions=pd.read_csv(ROOT/f'validation/{season}-rb-model-j2-predictions.csv')
    history=history.loc[history.position.eq('RB'),['season','week','player_id','rb_carries_pg','rb_targets_pg']]
    p=predictions.loc[predictions.model.isin(['F_position_specific','J2_RB_role_stability'])]
    d=p.merge(history,on=['season','week','player_id'],how='left',validate='many_to_one')
    d=d.loc[d.rb_targets_pg.ge(5)&d.rb_carries_pg.le(12)].copy()
    d['error']=d.projected_ppr-d.actual_ppr
    d['absolute_error']=d.error.abs()
    if d.empty: raise ValueError(f'No receiving-heavy observations for {season}')
    print(f'\\n{season} receiving-heavy sample, unique player-weeks={d[["week","player_id"]].drop_duplicates().shape[0]}')
    print(d.groupby('model').agg(n=('error','size'),bias=('error','mean'),mae=('absolute_error','mean')).round(3).to_string())
    paired=d.pivot(index=['season','week','player_id','player_name','actual_ppr'],columns='model',values='absolute_error').reset_index()
    paired['j2_minus_f_absolute_error']=paired['J2_RB_role_stability']-paired['F_position_specific']
    print('Largest J2 disadvantages relative to F:')
    print(paired.sort_values('j2_minus_f_absolute_error',ascending=False).head(8).round(3).to_string(index=False))
    paired['season']=season
    results.append(paired)
out=ROOT/'validation/rb-j2-receiving-heavy-outliers-2024-2025.csv'
pd.concat(results,ignore_index=True).to_csv(out,index=False)
print('Saved',out)
print('READ ONLY: No production changes.')
