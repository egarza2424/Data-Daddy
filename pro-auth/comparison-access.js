// Development preview only. Browser-side gating is not a secure payment boundary.
import { supabase, getSession } from "./auth.js";

export async function consumeComparisonAllowance() {
  const { data: session, error: sessionError } = await getSession();
  if (sessionError || !session?.session?.user) {
    return { allowed: false, message: "Please sign in to DATA DADDY Pro before comparing players." };
  }
  const { data, error } = await supabase.rpc("pro_consume_tool_use", {
    p_tool: "player_comparison"
  });
  if (error) return { allowed: false, message: "Access check failed. Please try again." };
  const decision = data?.[0];
  if (decision?.allowed) return { allowed: true };
  return { allowed: false, message: "Your free Player Comparison use has been used. Pro subscriptions are not available yet." };
}
