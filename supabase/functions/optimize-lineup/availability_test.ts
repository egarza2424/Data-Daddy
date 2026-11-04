import {eligibility, type AvailabilityRow} from "./availability.ts";
const base:AvailabilityRow={availability:"available_reported",observed_at:"2026-11-04T18:00:00Z",injury_status:null,roster_status:null};
function assert(value:unknown,message:string){if(!value)throw new Error(message)}
Deno.test("verified available player is eligible",()=>assert(eligibility(base,"best")==="eligible","Expected eligible"));
Deno.test("reported unavailable player excluded",()=>assert(eligibility({...base,availability:"unavailable_reported"},"best")==="excluded","Expected excluded"));
Deno.test("OUT and IR are excluded",()=>{for(const injury_status of ["OUT","IR","INACTIVE"])assert(eligibility({...base,injury_status},"best")==="excluded","Excluded injury "+injury_status)});
Deno.test("suspended roster status excluded",()=>assert(eligibility({...base,roster_status:"SUSPENDED"},"best")==="excluded","Suspended player selected"));
Deno.test("questionable eligible for best, excluded for safe",()=>{const row={...base,injury_status:"QUESTIONABLE"};assert(eligibility(row,"best")==="eligible","Best should allow questionable");assert(eligibility(row,"safe")==="excluded","Safe should exclude questionable")});
Deno.test("doubtful excluded for safe",()=>assert(eligibility({...base,injury_status:"DOUBTFUL"},"safe")==="excluded","Doubtful player selected"));
Deno.test("unknown availability fails closed",()=>{for(const availability of [null,"unknown",""]){let failed=false;try{eligibility({...base,availability},"best")}catch{failed=true}assert(failed,"Unknown availability accepted")}});
Deno.test("missing or invalid observation timestamp fails closed",()=>{for(const observed_at of [null,"","invalid"]){let failed=false;try{eligibility({...base,observed_at},"best")}catch{failed=true}assert(failed,"Unverified timestamp accepted")}});
