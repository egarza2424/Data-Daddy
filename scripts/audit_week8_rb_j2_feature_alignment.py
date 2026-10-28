"""Read-only audit: recent RB workload vs J2 feature values and PPR predictions."""
import pandas as pd
from pathlib import Path

root=Path('projection-model')
f=pd.read_csv(root/'validation/2026-live-rb-j2-features-audit.csv')
p=pd.read_csv(root/'2026-week8-ppr-projections.csv')
names=['Braelon Allen','Emanuel Wilson','Ashton Jeanty','Chase Brown','Tony Pollard']
cols=['rb_prior_games','rb_carries_pg','rb_targets_pg','rb_receptions_pg','rb_rush_yards_pg','rb_receiving_yards_pg','rb_redzone_carries_pg','rb_redzone_targets_pg','rb_season_games']
needed=['player_name','team','j2_match_status']+cols
missing=set(needed)-set(f.columns)
if missing: raise ValueError(f'Missing J2 feature columns: {sorted(missing)}')
out=f.loc[f['player_name'].isin(names),needed].merge(
 p.loc[p['position'].eq('RB'),['player_name','team','position_rank','projected_position_rank','projected_ppr','projection_model']],
 on=['player_name','team'],how='left',validate='one_to_one')
if set(out['player_name'])!=set(names): raise ValueError('Missing audit players')
print('J2 INPUT FEATURE ALIGNMENT — WEEK 8:')
print(out.to_string(index=False))
print('READ ONLY: Feature inspection does not validate projected accuracy or change model values.')
