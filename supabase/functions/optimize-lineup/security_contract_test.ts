// Offline security contract checks. These inspect the undeployed handler's
// control-flow ordering; they do NOT simulate Supabase or prove billing security.
const source = await Deno.readTextFile(new URL("./index.ts", import.meta.url));
function requireOrder(first: string, second: string) {
  const a=source.indexOf(first), b=source.indexOf(second);
  if (a<0 || b<0 || a>=b) throw new Error("Expected security ordering: "+first+" before "+second);
}
Deno.test("authentication precedes private snapshot access", () => {
  requireOrder('auth.auth.getUser(', 'db.from("pro_projection_snapshots")');
});
Deno.test("approved snapshot required before player lookup", () => {
  requireOrder('.eq("status","approved")', 'db.from("pro_projection_players")');
  requireOrder('if (!snapshots?.length)', 'db.from("pro_projection_players")');
});
Deno.test("player IDs are validated before database reads", () => {
  requireOrder('new Set(input.player_ids).size', 'db.from("pro_projection_snapshots")');
});
Deno.test("roster completeness checked before optimization", () => {
  requireOrder('projections?.length!==ids.length', 'const result=optimize(');
});
Deno.test("illegal lineups rejected before allowance consumption", () => {
  requireOrder('if (!result)', '.rpc("pro_consume_tool_use"');
});
Deno.test("allowance decision gates successful response", () => {
  requireOrder('.rpc("pro_consume_tool_use"', 'if (!decision?.allowed)');
  requireOrder('if (!decision?.allowed)', 'return reply(200,');
});
Deno.test("user token used for allowance RPC", () => {
  if (!source.includes('headers:{Authorization:authHeader}')) throw new Error("Missing user-scoped authorization");
  if (!source.includes('p_tool:"lineup_optimizer"')) throw new Error("Wrong tool allowance");
});
Deno.test("service role is used only for private data reads", () => {
  if (!source.includes('createClient(url,service')) throw new Error("Private snapshot access missing");
  if (source.includes('db.rpc("pro_consume_tool_use"')) throw new Error("Allowance must not be consumed with service role");
});
