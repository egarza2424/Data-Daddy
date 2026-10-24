"""Audit raw 2026 game logs and sample-window sensitivity before any AI rerank.
Read-only, no player-specific ranking floor or manual score changes.
"""
import json
from pathlib import Path
P=Path("nfl-stats.json")
WATCH={"justin jefferson","courtland sutton","nico collins"}
def norm(s):return " ".join(str(s or "").lower().replace(".","").split())
def locate(obj):
    if isinstance(obj,list):
        if obj and isinstance(obj[0],dict) and any("player_display_name" in x or "receiving_yards" in x for x in obj[:10]):yield obj
        for x in obj[:4]:yield from locate(x)
    elif isinstance(obj,dict):
        for k,v in obj.items():
            if k in ("weekly_stats","weeklyStats","player_stats","stats","players","weekly_player_stats","data") or isinstance(v,list):
                yield from locate(v)
def main():
    d=json.loads(P.read_text(encoding="utf-8"))
    print("Feed metadata:",{k:v for k,v in d.items() if k in ("target_week","updated","season","generated_at")})
    print("Top-level keys:",list(d)[:35])
    candidates=list(locate(d))
    print("Potential weekly arrays:",[(len(a),list(a[0])[:12]) for a in candidates[:8] if a])
    rows=max(candidates,key=len) if candidates else []
    for name in sorted(WATCH):
        games=[x for x in rows if norm(x.get("player_display_name") or x.get("player_name") or x.get("name"))==name and int(x.get("season") or 0)==2026]
        games.sort(key=lambda x:int(x.get("week") or 0),reverse=True)
        print("\n",name,"2026 matched games",len(games))
        for x in games[:7]:
            print({k:x.get(k) for k in ("season","week","team","position","targets","receptions","receiving_yards","receiving_tds","carries","rushing_yards","rushing_tds")})
        if games:
            for window in (3,5,7):
                subset=games[:window]
                pts=[float(x.get("receptions") or 0)+float(x.get("receiving_yards") or 0)/10+6*float(x.get("receiving_tds") or 0)+float(x.get("rushing_yards") or 0)/10+6*float(x.get("rushing_tds") or 0) for x in subset]
                print("window",window,"games",len(subset),"targets/game",round(sum(float(x.get("targets") or 0) for x in subset)/len(subset),2),"PPR/game",round(sum(pts)/len(pts),2))
    print("READ ONLY: do not force Jefferson top 10 without confirming source and backtest.")
if __name__=="__main__":main()
