"""Read-only Week 8 WR usage audit; does not change production rankings."""
from pathlib import Path
import pandas as pd
SOURCE=Path('projection-model/2026-week8-ppr-projections.csv')
URL='https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.csv'
watch=['Austin Trammell','Tim Jones','Dylan Drummond']
ranking=pd.read_csv(SOURCE,dtype={'player_id':str})
ranking=ranking.loc[ranking.position.eq('WR') & ranking.player_name.isin(watch)].copy()
if set(ranking.player_name)!=set(watch): raise ValueError('Missing target WRs')
stats=pd.read_csv(URL,dtype={'player_id':str})
stats=stats.loc[pd.to_numeric(stats.week,errors='coerce').between(1,7)].copy()
cols=['player_id','week','targets','receptions','receiving_yards']
if any(c not in stats for c in cols): raise ValueError('Missing weekly stats columns')
stats=stats[cols]
for col in ['targets','receptions','receiving_yards']:
 stats[col]=pd.to_numeric(stats[col],errors='coerce').fillna(0)
for _,p in ranking.sort_values('position_rank').iterrows():
 s=stats.loc[stats.player_id.eq(str(p.player_id))].sort_values('week')
 print(f"\\n{p.player_name} ({p.team}) AI WR{p.position_rank} / PPR WR{p.projected_position_rank}; opportunity={p.opportunity_score}, usage={p.usage_score}")
 if s.empty: print('NO MATCHED WEEKLY STAT ROWS: identity or participation needs review')
 else:
  print(s.to_string(index=False))
  recent=s.loc[s.week.ge(5)]
  print(f'Weeks 5-7 matched targets={recent.targets.sum():.0f}, catches={recent.receptions.sum():.0f}, receiving yards={recent.receiving_yards.sum():.0f}')
print('NOTE: No weekly stat row does not prove zero snaps; snap counts not measured here.')
print('READ ONLY: No scores, rankings or projections changed.')
