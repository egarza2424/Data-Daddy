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
print('READ ONLY: No production changes.')
