"""Read-only walk-forward J2 bias by pregame rushing/receiving opportunity, 2025."""
from pathlib import Path
import pandas as pd
ROOT=Path('projection-model')
hist=pd.read_csv(ROOT/'2025-historical-ppr-dataset.csv')
pred=pd.read_csv(ROOT/'validation/2025-rb-model-j2-predictions.csv')
hist=hist.loc[hist.position.eq('RB'),['season','week','player_id','rb_carries_pg','rb_targets_pg','rb_receptions_pg','rb_rush_yards_pg','rb_receiving_yards_pg']]
pred=pred.loc[pred.model.isin(['J2_RB_role_stability','F_position_specific'])].copy()
d=pred.merge(hist,on=['season','week','player_id'],how='left',validate='many_to_one')
if d[['rb_carries_pg','rb_targets_pg','rb_receptions_pg']].isna().any().any(): raise ValueError('Missing historical pregame workloads')
# Classification uses only pregame recent workload, never actual result.
d['role_group']='balanced'
d.loc[(d.rb_carries_pg>=12)&(d.rb_targets_pg<=3),'role_group']='rushing-heavy'
d.loc[(d.rb_targets_pg>=5)&(d.rb_carries_pg<=12),'role_group']='receiving-heavy'
# Pregame-only high-volume, low-efficiency rushing subgroup.
# Historical recent rushing yards / carries, never game-week outcomes.
d['recent_ypc']=d.rb_rush_yards_pg.div(d.rb_carries_pg.where(d.rb_carries_pg.gt(0)))
d['volume_efficiency_group']='other'
d.loc[d.rb_carries_pg.ge(12)&d.recent_ypc.lt(4.0),'volume_efficiency_group']='high-volume-low-efficiency'
d.loc[d.rb_carries_pg.ge(12)&d.recent_ypc.ge(4.0),'volume_efficiency_group']='high-volume-higher-efficiency'
d['error']=d.projected_ppr-d.actual_ppr
d['absolute_error']=d.error.abs()
summary=d.groupby(['model','role_group'],as_index=False).agg(n=('error','size'),bias=('error','mean'),mae=('absolute_error','mean'),avg_projection=('projected_ppr','mean'),avg_actual=('actual_ppr','mean'))
print('2025 WALK-FORWARD PREGAME ROLE GROUPS (bias > 0 means overprojection):')
print(summary.round(3).to_string(index=False))
wide=summary.pivot(index='role_group',columns='model',values='mae')
if {'J2_RB_role_stability','F_position_specific'}.issubset(wide.columns):
 print('J2 minus F MAE (negative means J2 better):')
 print((wide['J2_RB_role_stability']-wide['F_position_specific']).round(3).to_string())
out=ROOT/'validation/2025-rb-j2-rush-receive-bias.csv'
summary.to_csv(out,index=False)
print('Saved',out)
# Compare models within pregame volume/efficiency groups, including sample size.
volume_summary=d.loc[d.volume_efficiency_group.ne('other')].groupby(['model','volume_efficiency_group'],as_index=False).agg(n=('error','size'),bias=('error','mean'),mae=('absolute_error','mean'),avg_projection=('projected_ppr','mean'),avg_actual=('actual_ppr','mean'))
print('2025 PREGAME HIGH-VOLUME RUSHING EFFICIENCY GROUPS (4.0 YPC cutoff):')
print(volume_summary.round(3).to_string(index=False))
volume_out=ROOT/'validation/2025-rb-j2-volume-efficiency-bias.csv'
volume_summary.to_csv(volume_out,index=False)
print('Saved',volume_out)
# Independent 2024 check and pooled 2024-2025 sample; preserve 2025 outputs above.
comparisons=[d.assign(season_audit=2025)]
for season in (2024,):
 history_path=ROOT/f'{season}-historical-ppr-dataset.csv'
 prediction_path=ROOT/f'validation/{season}-rb-model-j2-predictions.csv'
 if not history_path.exists() or not prediction_path.exists():
  raise FileNotFoundError(f'Missing historical validation inputs for {season}')
 h=pd.read_csv(history_path)
 p=pd.read_csv(prediction_path)
 h=h.loc[h.position.eq('RB'),['season','week','player_id','rb_carries_pg','rb_targets_pg','rb_rush_yards_pg']]
 p=p.loc[p.model.isin(['J2_RB_role_stability','F_position_specific'])].copy()
 x=p.merge(h,on=['season','week','player_id'],how='left',validate='many_to_one')
 if x[['rb_carries_pg','rb_targets_pg','rb_rush_yards_pg']].isna().any().any():
  raise ValueError(f'Missing pregame workload for {season}')
 x['recent_ypc']=x.rb_rush_yards_pg.div(x.rb_carries_pg.where(x.rb_carries_pg.gt(0)))
 x['volume_efficiency_group']='other'
 x.loc[x.rb_carries_pg.ge(12)&x.recent_ypc.lt(4.0),'volume_efficiency_group']='high-volume-low-efficiency'
 x.loc[x.rb_carries_pg.ge(12)&x.recent_ypc.ge(4.0),'volume_efficiency_group']='high-volume-higher-efficiency'
 x['error']=x.projected_ppr-x.actual_ppr
 x['absolute_error']=x.error.abs()
 comparisons.append(x.assign(season_audit=season))
combined=pd.concat(comparisons,ignore_index=True)
subset=combined.loc[combined.volume_efficiency_group.ne('other')]
for season_label, group in [('2024',subset.loc[subset.season_audit.eq(2024)]),('2024-2025',subset)]:
 report=group.groupby(['model','volume_efficiency_group'],as_index=False).agg(n=('error','size'),bias=('error','mean'),mae=('absolute_error','mean'),avg_projection=('projected_ppr','mean'),avg_actual=('actual_ppr','mean'))
 print(f'{season_label} HISTORICAL HIGH-VOLUME EFFICIENCY CHECK:')
 print(report.round(3).to_string(index=False))
 output=ROOT/f'validation/{season_label}-rb-j2-volume-efficiency-bias.csv'
 report.to_csv(output,index=False)
 print('Saved',output)
print('READ ONLY: No production changes.')
