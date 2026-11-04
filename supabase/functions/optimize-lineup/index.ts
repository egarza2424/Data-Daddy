// DATA DADDY Pro — development-only server optimizer.
// Not deployed or connected to the website. Uses ONLY approved private snapshots.
import { createClient } from "npm:@supabase/supabase-js@2";

type Position = "QB" | "RB" | "WR" | "TE";
type Rules = Record<Position | "FLEX" | "SUPERFLEX", number>;
type Player = { player_id: string; player_name: string; position: Position; team: string; projected_ppr: number };
const POSITIONS: Position[] = ["QB", "RB", "WR", "TE"];
const PRESETS: Record<string, Rules> = {
  standard: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, SUPERFLEX: 0 },
  threeWR: { QB: 1, RB: 2, WR: 3, TE: 1, FLEX: 1, SUPERFLEX: 0 },
  superflex: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, SUPERFLEX: 1 },
};
const UNAVAILABLE = new Set(["OUT", "IR", "INJURED_RESERVE", "INJURY_RESERVE", "PUP", "INACTIVE", "SUSPENDED", "EXEMPT", "EXEMPT_LIST", "RESERVE/EXEMPT", "RESERVE_EXEMPT"]);
const RISKY = new Set(["QUESTIONABLE", "DOUBTFUL", "Q", "D"]);
const reply = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
function rulesFor(body: Record<string, unknown>): Rules {
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
function optimize(players: Player[], rules: Rules) {
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

Deno.serve(async request => {
  if (request.method !== "POST") return reply(405,{error:"POST required"});
  try {
    const authHeader = request.headers.get("Authorization") || "";
    if (!authHeader.startsWith("Bearer ")) return reply(401,{error:"Sign in required"});
    const url = Deno.env.get("SUPABASE_URL");
    const anon = Deno.env.get("SUPABASE_ANON_KEY");
    const service = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    if (!url || !anon || !service) return reply(503,{error:"Service not configured"});
    const auth = createClient(url,anon,{auth:{persistSession:false}});
    const { data: userResult, error: authError } = await auth.auth.getUser(authHeader.slice(7));
    if (authError || !userResult.user) return reply(401,{error:"Invalid session"});
    const body = await request.json();
    if (!body || typeof body !== "object" || Array.isArray(body)) return reply(400,{error:"Invalid request"});
    const input = body as Record<string,unknown>;
    const rules = rulesFor(input);
    if (!Array.isArray(input.player_ids) || input.player_ids.length<1 || input.player_ids.length>100 ||
        input.player_ids.some(id=>typeof id!=="string" || !id || id.length>128) ||
        new Set(input.player_ids).size!==input.player_ids.length) return reply(400,{error:"Invalid player IDs"});
    if (input.strategy !== "best" && input.strategy !== "safe") return reply(400,{error:"Invalid strategy"});
    const season=input.season, week=input.week;
    if (!Number.isInteger(season) || (season as number)<2020 || !Number.isInteger(week) || (week as number)<1 || (week as number)>22)
      return reply(400,{error:"Invalid season or week"});

    const db=createClient(url,service,{auth:{persistSession:false}});
    const {data: snapshots,error: snapError}=await db.from("pro_projection_snapshots")
      .select("id,version").eq("season",season).eq("week",week).eq("status","approved")
      .order("version",{ascending:false}).limit(1);
    if (snapError) return reply(503,{error:"Snapshot lookup unavailable"});
    if (!snapshots?.length) return reply(409,{error:"No approved projection snapshot for this week"});
    const snapshotId=snapshots[0].id;
    const ids=input.player_ids as string[];
    const [{data: projections,error: projError},{data: statuses,error: statusError}]=await Promise.all([
      db.from("pro_projection_players").select("player_id,player_name,position,team,projected_ppr").eq("snapshot_id",snapshotId).in("player_id",ids),
      db.from("pro_player_availability").select("player_id,injury_status,roster_status,availability").eq("snapshot_id",snapshotId).in("player_id",ids),
    ]);
    if (projError || statusError) return reply(503,{error:"Projection data unavailable"});
    if (projections?.length!==ids.length || statuses?.length!==ids.length) return reply(400,{error:"Roster contains unknown or incomplete players"});
    const availability=new Map((statuses||[]).map(row=>[row.player_id,row]));
    const eligible:Player[]=[];
    for (const p of projections||[]) {
      const status=availability.get(p.player_id);
      if (!status) return reply(400,{error:"Missing player availability"});
      const injury=String(status.injury_status||"").trim().toUpperCase();
      const roster=String(status.roster_status||"").trim().toUpperCase();
      if (UNAVAILABLE.has(injury)||UNAVAILABLE.has(roster)||status.availability==="unavailable_reported") continue;
      if (input.strategy==="safe" && RISKY.has(injury)) continue;
      const points=Number(p.projected_ppr);
      if (!Number.isFinite(points) || !POSITIONS.includes(p.position)) return reply(503,{error:"Invalid stored projection"});
      eligible.push({player_id:p.player_id,player_name:p.player_name,position:p.position,team:p.team,projected_ppr:points});
    }
    const result=optimize(eligible,rules);
    if (!result) return reply(422,{error:"No legal lineup for these players and rules"});
    // Consume allowance ONLY after a legal lineup is found. RPC must be atomic.
    // This is a development-only implementation; do not deploy before integration/security tests.
    const userDb=createClient(url,anon,{global:{headers:{Authorization:authHeader}},auth:{persistSession:false}});
    const {data: allowance,error: allowanceError}=await userDb.rpc("pro_consume_tool_use",{p_tool:"lineup_optimizer"});
    if (allowanceError) return reply(503,{error:"Pro allowance check unavailable"});
    const decision=Array.isArray(allowance)?allowance[0]:allowance;
    if (!decision?.allowed) return reply(402,{error:"Free use exhausted. Upgrade to DATA DADDY Pro."});
    return reply(200,{snapshot_version:snapshots[0].version,season,week,strategy:input.strategy,rules,...result});
  } catch (error) {
    if (error instanceof SyntaxError || error instanceof Error && /Invalid|Custom|Unknown|Too many/.test(error.message))
      return reply(400,{error:error.message});
    return reply(500,{error:"Unable to optimize lineup"});
  }
});
