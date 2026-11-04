import { executeProtectedOptimization, type GateDependencies } from "./protected_flow.ts";
function assert(condition: unknown, message: string) { if (!condition) throw new Error(message); }
function harness(options: { authenticated?: boolean; approved?: boolean; legal?: boolean; pro?: boolean; remainingFree?: number } = {}) {
  const calls: string[] = [];
  let remaining = options.remainingFree ?? 1;
  const pro = options.pro ?? false;
  const deps: GateDependencies<{id:string}> = {
    async authenticate() { calls.push("auth"); return options.authenticated ?? true; },
    async loadApprovedSnapshot() { calls.push("snapshot"); return (options.approved ?? true) ? {id:"approved"} : null; },
    async validateAndOptimize() { calls.push("optimize"); return (options.legal ?? true) ? {total:112} : null; },
    async consumeAllowance() { calls.push("allowance"); if (pro) return {allowed:true}; if (remaining<=0) return {allowed:false}; remaining--; return {allowed:true}; },
  };
  return { calls, run: () => executeProtectedOptimization(deps), remaining: () => remaining };
}
Deno.test("unauthenticated request denied without database reads or allowance", async () => {
  const h=harness({authenticated:false});
  assert((await h.run()).status===401,"Expected 401");
  assert(h.calls.join(",")==="auth","Must stop at authentication");
});
Deno.test("draft or missing snapshot denied without consuming allowance", async () => {
  const h=harness({approved:false});
  assert((await h.run()).status===409,"Expected 409");
  assert(h.remaining()===1 && !h.calls.includes("allowance"),"Free use consumed");
});
Deno.test("invalid or incomplete lineup does not consume allowance", async () => {
  const h=harness({legal:false});
  assert((await h.run()).status===422,"Expected 422");
  assert(h.remaining()===1 && !h.calls.includes("allowance"),"Free use consumed");
});
Deno.test("free user gets one successful use", async () => {
  const h=harness();
  assert((await h.run()).status===200,"First free use should succeed");
  assert(h.remaining()===0,"First use not consumed");
  assert((await h.run()).status===402,"Second free use must be denied");
});
Deno.test("already exhausted free user denied", async () => {
  const h=harness({remainingFree:0});
  assert((await h.run()).status===402,"Expected payment required");
});
Deno.test("Pro subscriber receives unlimited uses", async () => {
  const h=harness({pro:true,remainingFree:0});
  for (let i=0;i<5;i++) assert((await h.run()).status===200,"Pro request denied");
  assert(h.remaining()===0,"Pro should not consume free balance");
});
Deno.test("authorization and allowance sequencing is deterministic", async () => {
  const h=harness();
  await h.run();
  assert(h.calls.join(",")==="auth,snapshot,optimize,allowance","Incorrect security order");
});
