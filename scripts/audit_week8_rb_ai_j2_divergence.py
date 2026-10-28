"""Read-only Week 8 AI rank vs J2 projected-PPR rank audit."""
from pathlib import Path
import pandas as pd

SOURCE=Path('projection-model/2026-week8-ppr-projections.csv')
OUT=Path('projection-model/validation/2026-week8-rb-ai-j2-divergence.csv')
df=pd.read_csv(SOURCE)
rb=df.loc[df['position'].eq('RB')].copy()
for c in ['position_rank','projected_position_rank','projected_ppr','model_score','opportunity_score','production_score','usage_score','redzone_score','matchup_score','model_confidence_score']:
    rb[c]=pd.to_numeric(rb[c],errors='coerce')
rb['rank_gap_ai_minus_ppr']=rb['position_rank']-rb['projected_position_rank']
rb['absolute_rank_gap']=rb['rank_gap_ai_minus_ppr'].abs()
rb['review_reason']=rb['rank_gap_ai_minus_ppr'].map(lambda x:'AI higher than J2' if x<0 else ('J2 higher than AI' if x>0 else 'Aligned'))
cols=['player_name','team','roster_status','injury_status','position_rank','projected_position_rank','rank_gap_ai_minus_ppr','projected_ppr','model_score','projection_model','opportunity_score','production_score','usage_score','redzone_score','matchup_score','model_confidence_score','review_reason']
OUT.parent.mkdir(parents=True,exist_ok=True)
rb.sort_values('absolute_rank_gap',ascending=False)[cols].to_csv(OUT,index=False)
focus=rb.loc[rb['position_rank'].le(24)|rb['projected_position_rank'].le(24)].sort_values('absolute_rank_gap',ascending=False)
print('WEEK 8 FANTASY-RELEVANT RB RANK GAPS:')
print(focus[cols].head(25).to_string(index=False))
print('Saved',OUT)
print('READ ONLY: No AI scores, weights, projections or rankings changed.')
