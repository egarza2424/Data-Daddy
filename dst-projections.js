/* Week 8 D/ST projections — same filter and visual system as positional PPR. */
(function(){
"use strict";
const data=[["LA Rams","LA","LAC",6.67],["Chicago Bears","CHI","SEA",6.62],["Atlanta Falcons","ATL","TB",6.55],["Pittsburgh Steelers","PIT","CLE",6.5],["Tampa Bay Buccaneers","TB","ATL",6.47],["Jacksonville Jaguars","JAX","IND",6.21],["Cincinnati Bengals","CIN","TEN",6.2],["Cleveland Browns","CLE","PIT",6.19],["New England Patriots","NE","MIA",6.13],["Detroit Lions","DET","MIN",6.05],["Seattle Seahawks","SEA","CHI",6.03],["Las Vegas Raiders","LV","NYJ",5.53],["Minnesota Vikings","MIN","DET",5.29],["LA Chargers","LAC","LA",5.28],["Denver Broncos","DEN","KC",5.2]];
const actualScores={"LA":9,"ATL":2,"PIT":16,"TB":13,"JAX":19,"CIN":5,"CLE":3,"NE":7,"DET":6,"LV":9,"MIN":6,"LAC":3,"DEN":2};
const dstButton=document.querySelector("[data-dst-projection]");
const dstPanel=document.getElementById("dstProjectionPanel");
const playerWrapper=document.getElementById("playerProjectionWrapper");
const pagination=document.getElementById("projectionPagination");
const search=document.getElementById("projectionSearch");
const table=document.getElementById("dstProjectionTableBody");
const cards=document.getElementById("dstProjectionMobileCards");
if(!dstButton||!dstPanel||!playerWrapper||!pagination||!table||!cards)return;
let selected=false;
function draw(){
 const q=(search?.value||"").trim().toLowerCase();
 const list=data.filter(r=>(r[0]+" "+r[1]+" "+r[2]+" D/ST").toLowerCase().includes(q));
 table.replaceChildren();cards.replaceChildren();
 for(const r of list){
  const tr=document.createElement("tr");
  for(const v of [data.indexOf(r)+1,r[0],r[3].toFixed(2),"D/ST",r[1],r[2],Object.prototype.hasOwnProperty.call(actualScores,r[1])?actualScores[r[1]].toFixed(2):"—","Experimental"]){
   const td=document.createElement("td");td.textContent=String(v);tr.appendChild(td);
  }table.appendChild(tr);
  const card=document.createElement("div");card.className="projection-mobile-card";
  const heading=document.createElement("strong");heading.textContent="#"+(data.indexOf(r)+1)+" "+r[0];
  const details=document.createElement("p");details.textContent="D/ST · "+r[1]+" vs "+r[2]+" · "+r[3].toFixed(2)+" projected pts · Actual PPR: "+(Object.prototype.hasOwnProperty.call(actualScores,r[1])?actualScores[r[1]].toFixed(2):"—");
  card.append(heading,details);cards.appendChild(card);
 }
 if(!list.length){const tr=document.createElement("tr");const td=document.createElement("td");td.colSpan=8;td.textContent="No matching D/ST projections.";tr.appendChild(td);table.appendChild(tr);}
}
function setDst(active){
 selected=active;dstPanel.hidden=!active;playerWrapper.hidden=active;pagination.hidden=active;
 dstButton.classList.toggle("active",active);dstButton.setAttribute("aria-pressed",String(active));
 if(active){document.querySelectorAll("[data-projection-position]").forEach(b=>b.classList.remove("active"));draw();}
}
dstButton.addEventListener("click",()=>setDst(true));
document.querySelectorAll("[data-projection-position]").forEach(b=>b.addEventListener("click",()=>setDst(false)));
search?.addEventListener("input",()=>{if(selected)draw();});
})();