"""Experimental Signal 10: public-data trench matchup, no PFF grades.

Input: timestamped, PRE-GAME team-week metrics derived from nflverse play-by-play
and optionally timestamped projected OL starter availability. Metrics are rolling
prior-game rates, not opponent-adjusted individual player grades. Never use
post-kickoff revisions in a backtest. No changes to live model weights.

Required team-metric CSV fields:
 game_id,offense_team,defense_team,kickoff_utc,metric_published_utc,
 offense_pass_plays,offense_sacks_allowed,offense_qb_hits_allowed,
 offense_rushes,offense_rush_successes,
 defense_pass_plays,defense_sacks,defense_qb_hits,
 defense_rushes,defense_rush_stops

All counts must aggregate games PRIOR to kickoff. Sack/hit counts may overlap;
they are independently normalized, then blended, not added as events.
Optional OL projected starters CSV fields:
 game_id,team,position,player_id,expected_start_probability,
 availability_probability,published_utc
Five positions LT LG C RG RT; probabilities for candidates at each position
must sum to 1. Availability is probability of playing, not an injury grade.
"""
import csv
from datetime import datetime, timezone
from pathlib import Path

OL_POS = {'LT','LG','C','RG','RT'}

def stamp(s):
    t=datetime.fromisoformat(str(s).replace('Z','+00:00'))
    if t.tzinfo is None: raise ValueError('Timestamps must include UTC offset')
    return t.astimezone(timezone.utc)

def bounded(x, lo=0., hi=1.): return min(hi,max(lo,x))

def ratio(n,d):
    n,d=float(n),float(d)
    if d<=0 or n<0: raise ValueError('Nonpositive denominator or negative count')
    return bounded(n/d)

def starter_availability(starters,game_id,team,kickoff):
    rows=[r for r in starters if r['game_id']==game_id and r['team']==team and stamp(r['published_utc'])<kickoff]
    if not rows: return None
    latest={}
    for r in sorted(rows,key=lambda x:stamp(x['published_utc'])):
        latest[(r['position'],r['player_id'])]=r
    by_pos={p:[] for p in OL_POS}
    for r in latest.values():
        if r['position'] in OL_POS: by_pos[r['position']].append(r)
    if any(not by_pos[p] for p in OL_POS):return None
    expected=[]
    for pos in sorted(OL_POS):
        choices=by_pos[pos]
        weights=[float(r['expected_start_probability']) for r in choices]
        if abs(sum(weights)-1)>0.02:return None
        avail=[float(r['availability_probability']) for r in choices]
        if any(not 0<=v<=1 for v in weights+avail):raise ValueError('Probability outside [0,1]')
        expected.append(sum(w*a for w,a in zip(weights,avail))/sum(weights))
    return sum(expected)/5

def compute(row,starters=()):
    kickoff=stamp(row['kickoff_utc'])
    if stamp(row['metric_published_utc'])>=kickoff:
        return {'available':False,'reason':'Metrics not published before kickoff'}
    # Historical rates for offense and opposing defense; all inputs pregame.
    off_sack=ratio(row['offense_sacks_allowed'],row['offense_pass_plays'])
    off_hit=ratio(row['offense_qb_hits_allowed'],row['offense_pass_plays'])
    off_run=ratio(row['offense_rush_successes'],row['offense_rushes'])
    def_sack=ratio(row['defense_sacks'],row['defense_pass_plays'])
    def_hit=ratio(row['defense_qb_hits'],row['defense_pass_plays'])
    def_stop=ratio(row['defense_rush_stops'],row['defense_rushes'])
    # All scores are transparent heuristic indices, not PFF grades or fitted probabilities.
    # 50 neutral; + is favorable to offense. Coefficients deliberately provisional.
    pass_edge=50+100*((.65*(.06-off_sack)+.35*(.12-off_hit))
                       -(.65*(def_sack-.06)+.35*(def_hit-.12)))
    run_edge=50+50*((off_run-.42)- (def_stop-.42))
    availability=starter_availability(starters,row['game_id'],row['offense_team'],kickoff)
    # Never invent starter availability. Provide unadjusted metric separately.
    # If complete pregame projections exist, apply a conservative max 10-point adjustment.
    injury_adjustment=None if availability is None else -10*(1-availability)
    pass_score=bounded(pass_edge,0,100)
    run_score=bounded(run_edge,0,100)
    if injury_adjustment is not None:
        pass_score=bounded(pass_score+injury_adjustment,0,100)
        run_score=bounded(run_score+injury_adjustment,0,100)
    return {'available':True,'game_id':row['game_id'],'offense_team':row['offense_team'],
            'defense_team':row['defense_team'], 'pass_score':round(pass_score,2),
            'run_score':round(run_score,2),
            'offense_sack_rate':round(off_sack*100,2),
            'offense_qb_hit_rate':round(off_hit*100,2),
            'offense_rush_success_rate':round(off_run*100,2),
            'defense_sack_rate':round(def_sack*100,2),
            'defense_qb_hit_rate':round(def_hit*100,2),
            'defense_run_stop_rate':round(def_stop*100,2),
            'ol_starter_availability':availability,
            'injury_adjusted':availability is not None,
            'confidence':'lineup_confirmed' if availability is not None else 'team_metrics_only',
            'experimental':True}

def process(metric_csv,starter_csv,output_csv):
    with open(metric_csv,newline='') as f:metrics=list(csv.DictReader(f))
    if starter_csv:
        with open(starter_csv,newline='') as f:starters=list(csv.DictReader(f))
    else:starters=[]
    results=[compute(r,starters) for r in metrics]
    keys=['game_id','offense_team','defense_team','available','pass_score','run_score',
          'offense_sack_rate','offense_qb_hit_rate','offense_rush_success_rate',
          'defense_sack_rate','defense_qb_hit_rate','defense_run_stop_rate',
          'ol_starter_availability','injury_adjusted','confidence','reason','experimental']
    with open(output_csv,'w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(results)
    return results

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--metrics',required=True);p.add_argument('--starters');p.add_argument('--output',required=True)
    a=p.parse_args();process(a.metrics,a.starters,a.output)
