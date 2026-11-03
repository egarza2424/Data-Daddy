// Development preview only. Do not treat browser gating as payment security.
import { supabase, getSession } from "./auth.js";

export async function consumeLineupAllowance() {
  const { data: session, error: sessionError } = await getSession();
  if (sessionError || !session?.session?.user) {
    return { allowed: false, message: "Please sign in to DATA DADDY Pro before optimizing." };
  }
  const { data, error } = await supabase.rpc("pro_consume_tool_use", {
    p_tool: "lineup_optimizer"
  });
  if (error) return { allowed: false, message: "Access check failed. Please try again." };
  const decision = data?.[0];
  if (decision?.allowed) return { allowed: true };
  return { allowed: false, message: "Your free Lineup Optimizer use has been used. Pro subscriptions are not available yet." };
}
