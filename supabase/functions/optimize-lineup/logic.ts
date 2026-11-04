// Pure, testable optimizer logic. No database, credentials, or network access.
export type Position = "QB" | "RB" | "WR" | "TE";
export type Rules = Record<Position | "FLEX" | "SUPERFLEX", number>;
export type Player = { player_id: string; player_name: string; position: Position; team: string; projected_ppr: number };
const POSITIONS: Position[] = ["QB", "RB", "WR", "TE"];
const PRESETS: Record<string, Rules> = {
  standard: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, SUPERFLEX: 0 },
  threeWR: { QB: 1, RB: 2, WR: 3, TE: 1, FLEX: 1, SUPERFLEX: 0 },
  superflex: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, SUPERFLEX: 1 },
};
const UNAVAILABLE = new Set(["OUT", "IR", "INJURED_RESERVE", "INJURY_RESERVE", "PUP", "INACTIVE", "SUSPENDED", "EXEMPT", "EXEMPT_LIST", "RESERVE/EXEMPT", "RESERVE_EXEMPT"]);
const RISKY = new Set(["QUESTIONABLE", "DOUBTFUL", "Q", "D"]);
const reply = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
export function rulesFor(body: Record<string, unknown>): Rules {
  const format = body.format;
  if (typeof format !== "string" || !["standard", "threeWR", "superflex", "custom"].includes(format)) throw new Error("Invalid lineup format");
  if (format !== "custom") return { ...PRESETS[format] };
  if (!body.rules || typeof body.rules !== "object" || Array.isArray(body.rules)) throw new Error("Custom lineup rules required");
  const supplied = body.rules as Record<string, unknown>;
  if (Object.keys(supplied).some(k => ![...POSITIONS, "FLEX", "SUPERFLEX"].includes(k))) throw new Error("Unknown lineup slot");
  const result = {} as Rules;
  for (const key of [...POSITIONS, "FLEX", "SUPERFLEX"] as (keyof Rules)[]) {
    const n = supplied[key];
    if (!Number.isInteger(n) || (n as number) < 0 || (n as number) > 8) throw new Error("Custom slot counts must be integers from 0 to 8");
    result[key] = n as number;
  }
  if (Object.values(result).reduce((a,b)=>a+b,0) > 20) throw new Error("Too many starters");
  return result;
}
function allocations(n: number, positions: Position[]): Record<Position, number>[] {
  const out: Record<Position, number>[] = [];
  function visit(i: number, remaining: number, current: Record<string, number>) {
    if (i === positions.length - 1) { out.push({ ...current, [positions[i]]: remaining } as Record<Position, number>); return; }
    for (let v=0; v<=remaining; v++) visit(i+1,remaining-v,{...current,[positions[i]]:v});
  }
  visit(0,n,{});
  return out;
}
export function optimize(players: Player[], rules: Rules) {
  const groups = Object.fromEntries(POSITIONS.map(pos => [pos, players.filter(p=>p.position===pos).sort((a,b)=>b.projected_ppr-a.projected_ppr || a.player_id.localeCompare(b.player_id))])) as Record<Position, Player[]>;
  let best: { total: number; selected: Record<Position, Player[]>; flexAllocation: Record<Position,number>; superflexAllocation: Record<Position,number> } | null = null;
  for (const flex of allocations(rules.FLEX, ["RB","WR","TE"]))
    for (const sf of allocations(rules.SUPERFLEX, POSITIONS)) {
      const required = Object.fromEntries(POSITIONS.map(pos => [pos, rules[pos]+(flex[pos]||0)+(sf[pos]||0)])) as Record<Position,number>;
      if (POSITIONS.some(pos=>groups[pos].length<required[pos])) continue;
      const selected = Object.fromEntries(POSITIONS.map(pos=>[pos,groups[pos].slice(0,required[pos])])) as Record<Position,Player[]>;
      const total = POSITIONS.flatMap(pos=>selected[pos]).reduce((sum,p)=>sum+p.projected_ppr,0);
      if (!best || total>best.total) best={total,selected,flexAllocation:flex,superflexAllocation:sf};
    }
  return best;
}

