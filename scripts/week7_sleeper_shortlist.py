"""Week 7 actionable sleeper shortlist, read-only and explicitly evidence-gated."""
import csv
from pathlib import Path
P=Path("projection-model/2026-week7-ppr-projections.csv")
M=Path("projection-model/2026-week7-market-consensus.csv")
I=Path("projection-model/validation/injury-opportunity-candidates.csv")
def load(p):
 with p.open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def num(x):
 try:return float(x)
 except:return None
def norm(name):
 import re
 return re.sub(r"[^a-z0-9]","",re.sub(r"\s+(jr\.?|sr\.?|ii|iii|iv)$","",str(name).casefold().strip()))
def key(x):return (norm(x["player_name"]),x["position"],x["team"])
p=load(P);m=load(M);inj=load(I)
market={key(x):x for x in m if x.get("season")=="2026" and x.get("week")=="7"}
injury={}
for x in inj:
 if x.get("season")=="2026" and x.get("week")=="7":injury.setdefault((norm(x["candidate_name"]),x["candidate_position"],x["team"]),[]).append(x)
names={"Omar Cooper","Germie Bernard","Keenan Allen","Kendre Miller","Tyler Higbee","Colby Parkinson","Will Mallory","Michael Mayer","C.J. Stroud","Aaron Rodgers","Braelon Allen","Zonovan Knight","Woody Marks","Dameon Pierce","Jordan Mason","Antonio Williams","Jaylin Noel","Ryan Flournoy"}
results=[]
for x in p:
 if norm(x["player_name"]) not in {norm(n) for n in names}:continue
 e=injury.get(key(x),[])
 role=any(z.get("role_confidence")=="CONFIRMED" and z.get("approved_for_scoring","").lower()=="true" for z in e)
 mk=market.get(key(x),{})
 er=num(mk.get("ecr_position_rank"))
 ar=num(x.get("position_rank"));pr=num(x.get("projected_position_rank"))
 results.append((x["player_name"],x["position"],x["team"],x.get("projected_ppr"),ar,pr,er,len(e),role))
results.sort(key=lambda r:(r[1],r[5] if r[5] is not None else 999))
print("WEEK 7 SLEEPER SHORTLIST — REVIEW, NOT PUBLISHED RANKING")
for x in results:print(f"{x[0]:22} {x[1]:2} {x[2]:3} PPR={x[3]:>6} AIrank={str(x[4]):>5} PPRrank={str(x[5]):>5} ECR={str(x[6]):>5} injury_evidence={x[7]} role_approved={x[8]}")
print("Missing names:",", ".join(sorted({n for n in names if norm(n) not in {norm(x[0]) for x in results}})) or "none")
print("NOTE: market CSV source verification and ownership eligibility required before publishing.")
print("No live sleeper score, ranking, projection, or injury status changed.")
