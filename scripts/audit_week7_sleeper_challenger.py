"""Week 7 experimental sleeper challenger. Read-only, no external network requests.
Missing evidence stays missing; never convert unknown injury roles into zero opportunity.
Manual screenshot rankings are a frozen user-provided comparison, not a licensed feed.
"""
import csv
import re
from pathlib import Path

BASE=Path("projection-model/2026-week7-ppr-projections.csv")
MANUAL=Path("projection-model/validation/week7-manual-consensus-rankings.csv")
OUT=Path("projection-model/validation/week7-sleeper-challenger-review.csv")
DECISIONS=Path("projection-model/validation/week7-injury-opportunity-decisions.csv")
# Experimental, hand-set scenario inputs (0-100), NOT historically calibrated.
# Do not feed these into live scoring until backtested.
SCENARIO_SCORES={"emanuel wilson":80,"woody marks":75,"zonovan knight":65,"tyler allgeier":55}
ALLEN_SCENARIOS={"hall_active":35,"hall_inactive":85}
CUTOFF={"QB":10,"RB":18,"WR":24,"TE":10}
WATCH={"woody marks","tyler allgeier","zonovan knight"}
ALIASES={"bam knight":"zonovan knight","omar cooper jr":"omar cooper","omar cooper jr.":"omar cooper"}

def norm(s):
    s=" ".join(re.sub(r"[^a-z0-9 ]","",s.casefold()).split())
    return ALIASES.get(s,s)

def val(p,k):
    try:return float(p[k])
    except (KeyError,TypeError,ValueError):return None

def clamp(x):
    return max(0.,min(100.,x))

def main():
    with BASE.open(newline="",encoding="utf-8") as f: players=list(csv.DictReader(f))
    with MANUAL.open(newline="",encoding="utf-8") as f:
        manual={(norm(r["player_name"]),r["position"]):int(r["rank"]) for r in csv.DictReader(f)}
    with DECISIONS.open(newline="",encoding="utf-8") as f:
        decisions={(norm(x["player_name"]),x["position"],x["team"]):x for x in csv.DictReader(f)}
    rows=[]
    for p in players:
        pos=p.get("position")
        if pos not in CUTOFF:continue
        ai,ppr=val(p,"position_rank"),val(p,"projected_position_rank")
        if ai is None or ppr is None:continue
        if ppr<=CUTOFF[pos] or (ppr<=ai and norm(p["player_name"]) not in WATCH):continue
        # Five user-requested weights: 30 injury, 25 external advantage,
        # 20 projected workload, 10 matchup, 15 production.
        # Injury remains unknown without independently confirmed beneficiary role.
        decision=decisions.get((norm(p["player_name"]),pos,p["team"]))
        injury=None
        if decision and decision["opportunity_decision"]=="CONFIRMED_OPPORTUNITY":
            injury=SCENARIO_SCORES.get(norm(p["player_name"]))
        # Allen's QUESTIONABLE starter is explicitly two scenarios, not one
        # assumed availability outcome.
        allen=(norm(p["player_name"])=="braelon allen" and decision is not None)
        knight=(norm(p["player_name"])=="zonovan knight" and decision is not None)
        market=manual.get((norm(p["player_name"]),pos))
        external=clamp(50+5*(market-ai)) if market is not None else None
        # Disagreement alone is not evidence of upside. Require workload
        # support before granting a large market-disagreement bonus.
        opp=val(p,"opportunity_score");usage=val(p,"usage_score")
        workload=(.5*opp+.5*usage) if opp is not None and usage is not None else None
        if external is not None and workload is not None:
            external=min(external,workload)
        matchup=val(p,"matchup_score");environment=val(p,"scoring_environment_score")
        game=(.7*matchup+.3*environment) if matchup is not None and environment is not None else None
        production=val(p,"production_score")
        components={"injury":(30,injury),"external":(25,external),"workload":(20,workload),"matchup":(10,game),"production":(15,production)}
        known=sum(weight*score/100 for weight,score in components.values() if score is not None)
        missing=sum(weight for weight,score in components.values() if score is None)
        # Interval, not a falsely precise 0-100 score. Unknown components can
        # contribute between zero and their full weights.
        flags=[]
        if injury is None:flags.append("INJURY_SCENARIO_UNRESOLVED" if allen else "INJURY_ROLE_UNVERIFIED")
        if injury is not None:flags.append("INJURY_SCORE_EXPERIMENTAL_NOT_CALIBRATED")
        if allen:flags.append("SCENARIO_WORKLOAD_UNRESOLVED_NO_SINGLE_SCORE")
        if knight:flags.append("NEW_ROLE_WORKLOAD_NOT_REFLECTED_IN_HISTORY")
        if market is not None and workload is not None and clamp(50+5*(market-ai))>workload:
            flags.append("EXTERNAL_ADVANTAGE_CAPPED_BY_WORKLOAD")
        if external is None:flags.append("MANUAL_CONSENSUS_MISSING")
        if val(p,"model_confidence_score") is not None and val(p,"model_confidence_score")<50:
            flags.append("LOW_MODEL_CONFIDENCE")
        if norm(p["player_name"])=="braelon allen":flags.append("BREECE_HALL_QUESTIONABLE_CHECK_INACTIVES")
        if norm(p["player_name"])=="emanuel wilson":flags.append("CHARBONNET_OUT_HOLANI_QUESTIONABLE")
        if pos=="TE":flags.append("VERIFY_ROUTES_TARGETS")
        rows.append(dict(player_name=p["player_name"],position=pos,team=p["team"],
            ai_rank=int(ai),ppr_rank=int(ppr),manual_rank=market if market is not None else "",
            injury_score=injury if injury is not None else "",injury_score_hall_active=ALLEN_SCENARIOS["hall_active"] if allen else "",
            injury_score_hall_inactive=ALLEN_SCENARIOS["hall_inactive"] if allen else "",
            scenario_score_hall_active="",
            scenario_score_hall_inactive="",
            scenario_hall_active_lower=round(known-(20*workload/100 if workload is not None else 0)+30*ALLEN_SCENARIOS["hall_active"]/100,2) if allen else "",
            scenario_hall_active_upper=round(known-(20*workload/100 if workload is not None else 0)+30*ALLEN_SCENARIOS["hall_active"]/100+20,2) if allen else "",
            scenario_hall_inactive_lower=round(known-(20*workload/100 if workload is not None else 0)+30*ALLEN_SCENARIOS["hall_inactive"]/100,2) if allen else "",
            scenario_hall_inactive_upper=round(known-(20*workload/100 if workload is not None else 0)+30*ALLEN_SCENARIOS["hall_inactive"]/100+20,2) if allen else "",
            external_score=round(external,2) if external is not None else "",
            workload_score=round(workload,2) if workload is not None else "",
            matchup_score=round(game,2) if game is not None else "",
            production_score=round(production,2) if production is not None else "",
            score_lower_bound=round(known,2),score_upper_bound=round(known+missing,2),
            missing_weight_pct=missing,review_flags=";".join(flags),production_changed=False))
    rows.sort(key=lambda r:(r["missing_weight_pct"],-r["score_lower_bound"]))
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ["player_name"]);w.writeheader();w.writerows(rows)
    print("WEEK 7 SLEEPER CHALLENGER — READ ONLY (30/25/20/10/15)")
    print("Candidates:",len(rows),"| manual consensus matches:",sum(bool(r["manual_rank"]) for r in rows))
    print("Experimental injury scores applied only to confirmed-role decision rows; Allen has separate Hall-active and Hall-inactive scenarios.")
    print("These scores are illustrative assumptions, not validated injury-opportunity measurements.")
    print("Allen scenarios now report workload-uncertain intervals, not misleading single scores.")
    print("Knight flagged for inherited-role usage lag; no fabricated touch projection.")
    print("Market disagreement credit is capped by projected workload; this is a diagnostic guardrail, not a validated production formula.")
    print("Intervals reflect missing evidence; lower bounds are NOT comparable production sleeper scores.")
    for r in rows[:20]:
        print(f'{r["player_name"]} ({r["position"]} {r["team"]}): [{r["score_lower_bound"]:.1f}, {r["score_upper_bound"]:.1f}] | missing {r["missing_weight_pct"]}% | {r["review_flags"]}')
    print("Saved:",OUT)
    print("No production rankings, projections, or sleeper scores changed.")

if __name__=="__main__":main()
