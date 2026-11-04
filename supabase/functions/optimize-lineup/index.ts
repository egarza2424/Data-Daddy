// DATA DADDY Pro — development-only server optimizer.
// Not deployed or connected to the website. Uses ONLY approved private snapshots.
import { createClient } from "npm:@supabase/supabase-js@2";

import { rulesFor, optimize, type Player } from "./logic.ts";
import { executeProtectedOptimization } from "./protected_flow.ts";
const UNAVAILABLE = new Set(["OUT", "IR", "INJURED_RESERVE", "INJURY_RESERVE", "PUP", "INACTIVE", "SUSPENDED", "EXEMPT", "EXEMPT_LIST", "RESERVE/EXEMPT", "RESERVE_EXEMPT"]);
const RISKY = new Set(["QUESTIONABLE", "DOUBTFUL", "Q", "D"]);
const POSITIONS = ["QB", "RB", "WR", "TE"] as const;
const reply = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });

Deno.serve(async request => {
  if (request.method !== "POST") return reply(405,{error:"POST required"});
  try {
    const authHeader = request.headers.get("Authorization") || "";
    if (!authHeader.startsWith("Bearer ")) return reply(401,{error:"Sign in required"});
    const url = Deno.env.get("SUPABASE_URL");
    const anon = Deno.env.get("SUPABASE_ANON_KEY");
    const service = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    if (!url || !anon || !service) return reply(503,{error:"Service not configured"});
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
    const ids=input.player_ids as string[];
    const userDb=createClient(url,anon,{global:{headers:{Authorization:authHeader}},auth:{persistSession:false}});
    const gate=await executeProtectedOptimization({
      authenticate: async () => {
        const auth=createClient(url,anon,{auth:{persistSession:false}});
        const {data,error}=await auth.auth.getUser(authHeader.slice(7));
        return !error && Boolean(data.user);
      },
      loadApprovedSnapshot: async () => {
        const {data,error}=await db.from("pro_projection_snapshots")
          .select("id,version").eq("season",season).eq("week",week).eq("status","approved")
          .order("version",{ascending:false}).limit(1);
        if (error) throw new Error("Snapshot lookup unavailable");
        return data?.[0] ?? null;
      },
      validateAndOptimize: async (snapshot) => {
        const [{data:projections,error:projError},{data:statuses,error:statusError}]=await Promise.all([
          db.from("pro_projection_players").select("player_id,player_name,position,team,projected_ppr").eq("snapshot_id",snapshot.id).in("player_id",ids),
          db.from("pro_player_availability").select("player_id,injury_status,roster_status,availability,observed_at").eq("snapshot_id",snapshot.id).in("player_id",ids)
        ]);
        if (projError || statusError) throw new Error("Projection data unavailable");
        if (projections?.length!==ids.length || statuses?.length!==ids.length) throw new Error("Invalid roster: unknown or incomplete players");
        const availability=new Map((statuses||[]).map(row=>[row.player_id,row]));
        const eligible:Player[]=[];
        for (const p of projections||[]) {
          const status=availability.get(p.player_id);
          if (!status) throw new Error("Invalid roster: missing player availability");
          if (!status.observed_at || !["available_reported", "unavailable_reported"].includes(String(status.availability||""))) throw new Error("Player availability unverified");
          const injury=String(status.injury_status||"").trim().toUpperCase();
          const roster=String(status.roster_status||"").trim().toUpperCase();
          if (UNAVAILABLE.has(injury)||UNAVAILABLE.has(roster)||status.availability==="unavailable_reported") continue;
          if (input.strategy==="safe" && RISKY.has(injury)) continue;
          const points=Number(p.projected_ppr);
          if (!Number.isFinite(points)||!POSITIONS.includes(p.position)) throw new Error("Invalid stored projection");
          eligible.push({player_id:p.player_id,player_name:p.player_name,position:p.position,team:p.team,projected_ppr:points});
        }
        const result=optimize(eligible,rules);
        return result ? {snapshot_version:snapshot.version,season,week,strategy:input.strategy,rules,...result} : null;
      },
      consumeAllowance: async () => {
        const {data,error}=await userDb.rpc("pro_consume_tool_use",{p_tool:"lineup_optimizer"});
        if (error) throw new Error("Pro allowance check unavailable");
        const decision=Array.isArray(data)?data[0]:data;
        return {allowed:Boolean(decision?.allowed)};
      }
    });
    return reply(gate.status,gate.status===200?gate.result:{error:gate.error});
  } catch (error) {
    if (error instanceof SyntaxError || error instanceof Error && /Invalid|Custom|Unknown|Too many/.test(error.message))
      return reply(400,{error:error.message});
    if (error instanceof Error && /unavailable|unverified/.test(error.message)) return reply(503,{error:error.message});
    return reply(500,{error:"Unable to optimize lineup"});
  }
});
