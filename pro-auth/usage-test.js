import { supabase, getSession } from "./auth.js";

const status = document.getElementById("status");
const results = document.getElementById("results");
const buttons = [...document.querySelectorAll("[data-tool]")];
function say(msg) { status.textContent = msg; }
function render(rows) {
  results.replaceChildren();
  for (const tool of ["lineup_optimizer", "player_comparison"]) {
    const row = rows.find(x => x.tool === tool);
    const li = document.createElement("li");
    li.textContent = (tool === "lineup_optimizer" ? "Lineup Optimizer" : "Player Comparison") +
      ": " + (row?.used_count ?? 0) + " of 1 free use consumed";
    results.appendChild(li);
  }
}
async function refresh() {
  const { data: sessionData, error: sessionError } = await getSession();
  if (sessionError || !sessionData.session?.user) {
    buttons.forEach(b => b.disabled = true);
    say("Please sign in at the account preview before testing.");
    return;
  }
  const { data, error } = await supabase.from("pro_tool_usage")
    .select("tool,used_count");
  if (error) { say("Could not read usage: " + error.message); return; }
  render(data ?? []);
  buttons.forEach(b => b.disabled = false);
  say("Signed in. Each test button permanently consumes one free use in the development database.");
}
buttons.forEach(button => button.addEventListener("click", async () => {
  if (!window.confirm("This test will consume your one free " +
    (button.dataset.tool === "lineup_optimizer" ? "Lineup Optimizer" : "Player Comparison") +
    " use. Continue?")) return;
  buttons.forEach(b => b.disabled = true);
  const { data, error } = await supabase.rpc("pro_consume_tool_use", {
    p_tool: button.dataset.tool
  });
  if (error) say("Database error: " + error.message);
  else {
    const result = data?.[0];
    say(result?.allowed ? "Allowed: " + result.reason : "Denied: " + (result?.reason ?? "unknown"));
  }
  buttons.forEach(b => b.disabled = false);
  const { data: usage } = await supabase.from("pro_tool_usage").select("tool,used_count");
  if (usage) render(usage);
}));
refresh();
