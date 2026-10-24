"""Read-only test of public RotoBaller Week 7 PPR table coverage.

No live scoring changes. Do not store or redistribute the source's full rankings.
"""
import csv
import re
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

URL = "https://www.rotoballer.com/week-7-ppr-overall-rankings-for-fantasy-football-weekend-updates-2026/1973956"
PROJECTIONS = Path("projection-model/2026-week7-ppr-projections.csv")
OUT = Path("projection-model/validation/week7-rotoballer-coverage-review.csv")
ALIASES = {"zonovan knight": "bam knight", "omar cooper": "omar cooper jr.", "ted hurst iii": "ted hurst"}
CUTOFFS = {"QB":10, "RB":18, "WR":24, "TE":10}

def norm(name):
    n = re.sub(r"[^a-z0-9 ]", "", name.casefold())
    n = " ".join(n.split())
    return ALIASES.get(n, n)

class Tables(HTMLParser):
    def __init__(self):
        super().__init__(); self.tables=[]; self.table=None; self.row=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=="table": self.table=[]
        elif self.table is not None and tag=="tr": self.row=[]
        elif self.row is not None and tag in ("td","th"): self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()));self.cell=None
        elif tag=="tr" and self.row is not None:
            if self.row:self.table.append(self.row)
            self.row=None
        elif tag=="table" and self.table is not None:
            self.tables.append(self.table);self.table=None

def main():
    with PROJECTIONS.open(newline="",encoding="utf-8") as f:
        projections=list(csv.DictReader(f))
    req=urllib.request.Request(URL,headers={"User-Agent":"DataDaddyReadOnlyCoverageAudit/1.0 (GitHub Actions; no bulk replication)"})
    try:
        with urllib.request.urlopen(req,timeout=25) as resp:
            status=resp.status
            html=resp.read(5_000_000).decode("utf-8","replace")
    except Exception as exc:
        print("SOURCE FETCH FAILED:",type(exc).__name__,str(exc)[:250])
        print("No source ranks or production scores were changed.")
        return
    parser=Tables();parser.feed(html)
    rankings=[]
    for table in parser.tables:
        for cells in table:
            # Expected RotoBaller article columns: Tier | Rank | Player Name | Pos
            for i in range(max(0,len(cells)-3)):
                if cells[i].isdigit() and cells[i+1].isdigit() and cells[i+3] in CUTOFFS:
                    rankings.append((int(cells[i+1]),cells[i+2],cells[i+3]))
                    break
    rankings=sorted(set(rankings))
    by_position=Counter()
    source={}
    for overall,name,pos in rankings:
        by_position[pos]+=1
        source.setdefault((norm(name),pos),(overall,by_position[pos]))
    rows=[]
    for p in projections:
        pos=p["position"]
        if pos not in CUTOFFS:continue
        try:
            ai=float(p["position_rank"]);ppr=float(p["projected_position_rank"])
        except (ValueError,TypeError):continue
        if ppr<=CUTOFFS[pos]:continue
        watch=(norm(p["player_name"]),pos) in {("woody marks","RB"),("tyler allgeier","RB"),("bam knight","RB")}
        if ppr<=ai and not watch:continue
        match=source.get((norm(p["player_name"]),pos))
        rows.append(dict(player_name=p["player_name"],position=pos,team=p["team"],
            source_match=bool(match),source_position_rank=match[1] if match else "",
            data_daddy_ai_rank=int(ai),market_vs_ai_rank_advantage=match[1]-ai if match else "",
            injury_watch=watch))
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open("w",newline="",encoding="utf-8") as f:
        fields=["player_name","position","team","source_match","source_position_rank","data_daddy_ai_rank","market_vs_ai_rank_advantage","injury_watch"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    covered=sum(r["source_match"] for r in rows)
    print("HTTP status:",status,"| HTML tables:",len(parser.tables),"| parsed PPR rows:",len(rankings))
    print("Parsed by position:",dict(by_position))
    print("Candidate coverage:",covered,"/",len(rows),f"({covered/len(rows):.1%})" if rows else "")
    print("Coverage target >=80%:",covered>=0.8*len(rows) if rows else False)
    # Report a practical fantasy-relevant subset separately; never remove
    # unmatched rows or redefine the full-pool coverage denominator.
    practical=[r for r in rows if r["injury_watch"] or (
        (r["position"]=="QB" and r["data_daddy_ai_rank"]<=24) or
        (r["position"]=="RB" and r["data_daddy_ai_rank"]<=48) or
        (r["position"]=="WR" and r["data_daddy_ai_rank"]<=60) or
        (r["position"]=="TE" and r["data_daddy_ai_rank"]<=24)
    )]
    practical_found=sum(r["source_match"] for r in practical)
    print("Practical shortlist coverage (AI rank QB24/RB48/WR60/TE24, plus injury watches):",
          practical_found,"/",len(practical),
          f"({practical_found/len(practical):.1%})" if practical else "")
    print("Practical shortlist unmatched:")
    for r in practical:
        if not r["source_match"]:
            print(f" - {r['player_name']} | {r['position']} | {r['team']} | AI rank {r['data_daddy_ai_rank']}")
    for pos in CUTOFFS:
        subset=[r for r in rows if r["position"]==pos]
        found=sum(r["source_match"] for r in subset)
        print(f"{pos} coverage: {found}/{len(subset)}")
    missing=[r for r in rows if not r["source_match"]]
    print("Unmatched candidate names (investigate spelling, suffixes, missing source coverage):")
    for r in missing:
        print(f" - {r['player_name']} | {r['position']} | {r['team']} | DD AI rank {r['data_daddy_ai_rank']}")
    for r in rows:
        if r["injury_watch"]:print("Injury watch:",r["player_name"],"source rank:",r["source_position_rank"] or "missing")
    print("Review CSV:",OUT)
    print("This is an experimental, one-time access test; verify source permissions before recurring use.")
    print("No production scores, rankings or projections changed.")

if __name__=="__main__":main()
