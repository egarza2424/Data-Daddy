// Offline structural checks of the integrated handler and protected flow.
// These checks do not replace real HTTP/Supabase integration tests.
const handler=await Deno.readTextFile(new URL("./index.ts",import.meta.url));
const flow=await Deno.readTextFile(new URL("./protected_flow.ts",import.meta.url));
function contains(source:string,part:string){if(!source.includes(part))throw new Error("Missing: "+part)}
function before(source:string,a:string,b:string){contains(source,a);contains(source,b);if(source.indexOf(a)>=source.indexOf(b))throw new Error("Incorrect order: "+a+" / "+b)}
Deno.test("handler invokes shared protected flow",()=>{contains(handler,"executeProtectedOptimization({");contains(handler,'from "./protected_flow.ts"')});
Deno.test("authentication occurs before snapshot lookup in protected flow",()=>{before(flow,"await deps.authenticate()","await deps.loadApprovedSnapshot()")});
Deno.test("approved snapshot is required",()=>{contains(handler,'.eq("status","approved")');before(flow,"if (!snapshot)","await deps.validateAndOptimize(snapshot)")});
Deno.test("roster IDs validated before protected flow invocation",()=>{before(handler,"new Set(input.player_ids).size","executeProtectedOptimization({")});
Deno.test("roster completeness verified before optimization",()=>{before(handler,"projections?.length!==ids.length","const result=optimize(")});
Deno.test("illegal lineup rejected before consuming allowance",()=>{before(flow,"if (!result)","await deps.consumeAllowance()")});
Deno.test("denied allowance blocks successful response",()=>{before(flow,"if (!allowance.allowed)","return { status: 200, result }")});
Deno.test("allowance uses user token rather than service role",()=>{contains(handler,"headers:{Authorization:authHeader}");contains(handler,'p_tool:"lineup_optimizer"');contains(handler,"createClient(url,service");if(handler.includes('db.rpc("pro_consume_tool_use"'))throw new Error("Service role must not consume allowance")});
