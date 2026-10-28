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
 recent=stats.groupby('player_id',as_index=False).agg(recent_games=('week','nunique'),recent_targets=('targets','sum'),recent_receptions=('receptions','sum'),recent_yards=('receiving_yards','sum'))
 wr=wr.merge(recent,on='player_id',how='left',validate='one_to_one')
 for c in ['recent_games','recent_targets','recent_receptions','recent_yards']:wr[c]=wr[c].fillna(0)
 wr['needs_role_verification']=((wr.position_rank<=60)|(wr.projected_position_rank<=60)) & (wr.recent_targets<3)
 wr['review_reason']=wr.apply(lambda r:'LOW_VERIFIED_TARGETS_CHECK_SNAPS_ROUTES_OR_INJURY_OPPORTUNITY' if r.needs_role_verification else 'NOT_FLAGGED',axis=1)
 flagged=wr.loc[wr.needs_role_verification].sort_values('position_rank')
 print(f'Week {week} WR role audit: {len(wr)} WRs, {len(flagged)} need verification')
 print(flagged[['player_name','team','position_rank','projected_position_rank','recent_games','recent_targets','recent_receptions','recent_yards','review_reason']].to_string(index=False))
 out=Path(f'projection-model/validation/2026-week{week}-wr-role-review.csv')
 out.parent.mkdir(parents=True,exist_ok=True)
 wr.to_csv(out,index=False)
 print('Saved',out)
 print('READ ONLY: Target counts do not establish snap counts, routes, or injury-created roles.')
if __name__=='__main__':main()
