"""Read-only readiness audit for the proposed 30/25/20/10/15 sleeper model."""
import csv
from collections import Counter
from pathlib import Path

ROOT = Path("projection-model")
P = ROOT / "2026-week7-ppr-projections.csv"
M = ROOT / "2026-week7-market-consensus.csv"
I = ROOT / "validation/injury-opportunity-candidates.csv"
OUT = ROOT / "validation/week7-sleeper-challenger-readiness.csv"
CUTOFF = {"QB":10,"RB":18,"WR":24,"TE":10}
ALIASES = {"bam knight":"zonovan knight"}
def read(path):
    with path.open(newline="",encoding="utf-8") as f:
        return list(csv.DictReader(f))
def key(name, position, team):
    n = name.strip().casefold()
    return (ALIASES.get(n,n),position.strip().upper(),team.strip().upper())
def num(value):
    try: return float(value)
    except (TypeError,ValueError): return None
def main():
    projections,market,injuries=read(P),read(M),read(I)
    market_by_key={key(x["player_name"],x["position"],x["team"]):x for x in market if x["season"]=="2026" and x["week"]=="7"}
    injury_by_key={}
    for x in injuries:
        if x["season"]=="2026" and x["week"]=="7":
            injury_by_key.setdefault(key(x["candidate_name"],x["candidate_position"],x["team"]),[]).append(x)
    rows=[]
    for p in projections:
        pos=p["position"];pr=num(p["projected_position_rank"]);ar=num(p["position_rank"])
        if pos not in CUTOFF or pr is None or ar is None or pr<=CUTOFF[pos]:continue
        k=key(p["player_name"],pos,p["team"])
        e=injury_by_key.get(k,[])
        reviewed=k in {key("Woody Marks","RB","HOU"),key("Tyler Allgeier","RB","ARI"),key("Zonovan Knight","RB","ARI")}
        if pr<=ar and not reviewed:continue
        market_row=market_by_key.get(k)
        rank=num(market_row["ecr_position_rank"]) if market_row else None
        role=any(x.get("role_confidence")=="CONFIRMED" and x.get("approved_for_scoring","").lower()=="true" for x in e)
        rows.append(dict(player_name=p["player_name"],position=pos,team=p["team"],ai_rank=int(ar),ppr_rank=int(pr),
          injury_watch=reviewed,injury_evidence_rows=len(e),injury_role_approved=role,
          weekly_market_rank_available=rank is not None,market_rank=rank if rank is not None else "",
          market_rank_advantage=(rank-ar) if rank is not None else "",
          proposed_score_ready=bool(rank is not None and role and reviewed),
          blocking_reason=("Missing external weekly rank; " if rank is None else "")+
            ("Injury role not approved; " if reviewed and not role else "")+
            ("No reviewed injury opportunity" if not reviewed else "")))
    OUT.parent.mkdir(parents=True,exist_ok=True)
    fields=["player_name","position","team","ai_rank","ppr_rank","injury_watch","injury_evidence_rows","injury_role_approved","weekly_market_rank_available","market_rank","market_rank_advantage","proposed_score_ready","blocking_reason"]
    with OUT.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print("Review candidates:",len(rows))
    print("External weekly rank coverage:",sum(r["weekly_market_rank_available"] for r in rows),"/",len(rows))
    print("Reviewed injury watches:",sum(r["injury_watch"] for r in rows))
    print("Reviewed injury watches with approved roles:",sum(r["injury_watch"] and r["injury_role_approved"] for r in rows))
    print("Proposed scores approved:",sum(r["proposed_score_ready"] for r in rows))
    print("Injury watch details:")
    for r in rows:
        if r["injury_watch"]:print(" -",r["player_name"],r["team"],"ECR:",r["market_rank"] or "unavailable","role approved:",r["injury_role_approved"])
    print("Saved",OUT,"— no production changes")
if __name__=="__main__":main()
