"""Recurring read-only WR eligibility audit for every published projection week."""
import argparse
from pathlib import Path
import pandas as pd

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--week',type=int,default=None)
 args=parser.parse_args()
 files=list(Path('projection-model').glob('2026-week*-ppr-projections.csv'))
 if not files: raise SystemExit('No projection files')
 week=args.week or max(int(p.name.split('-week')[1].split('-')[0]) for p in files)
 source=Path(f'projection-model/2026-week{week}-ppr-projections.csv')
 df=pd.read_csv(source,dtype={'player_id':str})
 wr=df.loc[df.position.eq('WR')].copy()
 stats=pd.read_csv('historical-data/player_stats_2026.csv',dtype={'player_id':str})
 stats=stats.loc[pd.to_numeric(stats.week,errors='coerce').between(max(1,week-3),week-1)].copy()
 for col in ['targets','receptions','receiving_yards']:
  stats[col]=pd.to_numeric(stats[col],errors='coerce').fillna(0)
 print('Ranking ID examples:',wr[['player_name','player_id']].head(4).to_dict('records'))
 print('Stats ID examples:',stats[['player_id']].head(4).to_dict('records'))
 import re
 def norm(v):
  v=re.sub(r'\\s+(jr\\.?|sr\\.?|ii|iii|iv)$','',str(v).lower().strip())
  return re.sub(r'[^a-z0-9]','',v)
 if 'player_display_name' not in stats.columns or 'team' not in stats.columns:
  raise ValueError('Missing name/team fields required for safe identity resolution')
 wr['match_name']=wr.player_name.map(norm)
 wr['match_team']=wr.team.astype(str).str.upper().replace({'LA':'LAR','JAC':'JAX','WSH':'WAS'})
 stats['match_name']=stats.player_display_name.map(norm)
 stats['match_team']=stats.team.astype(str).str.upper().replace({'LA':'LAR','JAC':'JAX','WSH':'WAS'})
 groups=stats.groupby(['match_name','match_team'])
 names=stats.groupby('match_name')
 records=[]
 for row in wr.itertuples(index=False):
  key=(row.match_name,row.match_team)
  subset=groups.get_group(key) if key in groups.groups else stats.iloc[0:0]
  status='matched_name_team'
  if subset.empty:
   subset=names.get_group(row.match_name) if row.match_name in names.groups else stats.iloc[0:0]
   status='matched_name_only'
  unique_ids=subset.player_id.dropna().unique()
  if len(unique_ids)!=1:
   records.append({'player_id':row.player_id,'stats_id_matched':False,'match_status':'ambiguous' if len(unique_ids)>1 else 'unmatched'})
   continue
  records.append({'player_id':row.player_id,'stats_id_matched':True,'match_status':status,
    'recent_games':subset.week.nunique(),'recent_targets':subset.targets.sum(),
    'recent_receptions':subset.receptions.sum(),'recent_yards':subset.receiving_yards.sum(),
    'gsis_id':str(unique_ids[0])})
 matched=pd.DataFrame(records)
 if matched.loc[matched.stats_id_matched,'gsis_id'].duplicated().any():
  raise ValueError('Multiple ranking WRs resolved to the same GSIS ID')
 wr=wr.merge(matched,on='player_id',how='left',validate='one_to_one')
 for col in ['recent_games','recent_targets','recent_receptions','recent_yards']:wr[col]=wr[col].fillna(0)
 wr['generic_fallback_profile']=(wr.opportunity_score.eq(50)&wr.usage_score.eq(20)&wr.production_score.le(20))
 wr['needs_role_verification']=((wr.position_rank<=60)|(wr.projected_position_rank<=60)) & ((wr.stats_id_matched & (wr.recent_targets<3)) | wr.generic_fallback_profile)
 wr['review_reason']=wr.apply(lambda r:'GENERIC_FALLBACK_PROFILE_REQUIRES_ROLE_EVIDENCE' if r.generic_fallback_profile else ('UNRESOLVED_IDENTITY_NO_USAGE_CONCLUSION' if not r.stats_id_matched else ('LOW_VERIFIED_TARGETS_CHECK_SNAPS_ROUTES_OR_INJURY_OPPORTUNITY' if r.needs_role_verification else 'NOT_FLAGGED')),axis=1)
 print('Resolved identities:',int(wr.stats_id_matched.sum()),'/',len(wr))
 if wr.stats_id_matched.sum()<len(wr)*0.5:
  print('WARNING: Low ID match rate; no ranking eligibility decisions supported.')
 flagged=wr.loc[wr.needs_role_verification].sort_values('position_rank')
 print(f'Week {week} WR role audit: {len(wr)} WRs, {len(flagged)} need verification')
 print(flagged[['player_name','team','position_rank','projected_position_rank','recent_games','recent_targets','recent_receptions','recent_yards','review_reason']].to_string(index=False))
 out=Path(f'projection-model/validation/2026-week{week}-wr-role-review.csv')
 out.parent.mkdir(parents=True,exist_ok=True)
 wr.to_csv(out,index=False)
 print('Saved',out)
 print('READ ONLY: Target counts do not establish snap counts, routes, or injury-created roles.')
if __name__=='__main__':main()
