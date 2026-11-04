import { optimize, rulesFor, type Player } from "./logic.ts";

function check(condition: unknown, message: string) {
  if (!condition) throw new Error(message);
}
function player(id: string, position: Player["position"], points: number): Player {
  return { player_id: id, player_name: id, position, team: "TEST", projected_ppr: points };
}
const roster: Player[] = [
  player("q1","QB",20), player("q2","QB",19),
  player("r1","RB",18), player("r2","RB",17), player("r3","RB",16),
  player("w1","WR",15), player("w2","WR",14), player("w3","WR",13),
  player("t1","TE",12), player("t2","TE",11)
];
Deno.test("standard lineup fills 1QB 2RB 2WR 1TE 1FLEX", () => {
  const result = optimize(roster, rulesFor({format:"standard"}));
  check(result !== null, "Expected legal lineup");
  const selected = result!.selected;
  check(Object.values(selected).flat().length === 7, "Expected seven starters");
  check(selected.RB.length === 3, "Highest FLEX should be RB3");
  check(result!.total === 112, "Incorrect projected PPR total");
});
Deno.test("threeWR requires three wide receivers", () => {
  const result = optimize(roster, rulesFor({format:"threeWR"}));
  check(result !== null && result.selected.WR.length >= 3, "Three WR starters required");
  check(Object.values(result!.selected).flat().length === 8, "Expected eight starters");
});
Deno.test("superflex can select second quarterback", () => {
  const result = optimize(roster, rulesFor({format:"superflex"}));
  check(result !== null && result.selected.QB.length === 2, "Second QB should fill superflex");
});
Deno.test("custom rules accepted and validated", () => {
  const rules = rulesFor({format:"custom",rules:{QB:1,RB:1,WR:1,TE:0,FLEX:0,SUPERFLEX:0}});
  check(optimize(roster,rules)?.total === 53, "Custom total incorrect");
});
Deno.test("invalid custom rules rejected", () => {
  for (const rules of [
    {QB:-1,RB:1,WR:1,TE:1,FLEX:1,SUPERFLEX:0},
    {QB:1,RB:1,WR:1,TE:1,FLEX:1,SUPERFLEX:0.5},
    {QB:1,RB:1,WR:1,TE:1,FLEX:1,SUPERFLEX:0,INVALID:1},
  ]) {
    let rejected=false;
    try { rulesFor({format:"custom",rules}); } catch { rejected=true; }
    check(rejected,"Invalid custom rules should fail");
  }
});
Deno.test("incomplete roster has no legal lineup", () => {
  const result=optimize(roster.filter(p=>p.position!=="TE"),rulesFor({format:"standard"}));
  check(result===null,"Must not invent missing TE");
});
Deno.test("excluded players cannot be selected", () => {
  const filtered=roster.filter(p=>p.player_id!=="r1");
  const result=optimize(filtered,rulesFor({format:"standard"}));
  check(result!==null && !Object.values(result.selected).flat().some(p=>p.player_id==="r1"),"Excluded player selected");
});
Deno.test("deterministic tie break by player ID", () => {
  const rules=rulesFor({format:"custom",rules:{QB:1,RB:0,WR:0,TE:0,FLEX:0,SUPERFLEX:0}});
  const result=optimize([player("z","QB",20),player("a","QB",20)],rules);
  check(result?.selected.QB[0].player_id==="a","Tie-break not deterministic");
});

Deno.test("empty custom lineup rejected without generating billable result", () => {
  let rejected=false;
  try { rulesFor({format:"custom",rules:{QB:0,RB:0,WR:0,TE:0,FLEX:0,SUPERFLEX:0}}); }
  catch { rejected=true; }
  check(rejected,"Empty custom lineup must be rejected");
});
