import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY } from "./config.js";

export const supabase = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
  auth: { autoRefreshToken: true, persistSession: true, detectSessionInUrl: true }
});

export async function signUp(email, password) {
  return supabase.auth.signUp({ email, password, options: { emailRedirectTo: window.location.href.split('#')[0].split('?')[0] } });
}
export async function signIn(email, password) {
  return supabase.auth.signInWithPassword({ email, password });
}
export async function signOut() { return supabase.auth.signOut(); }
export async function getSession() { return supabase.auth.getSession(); }
export async function resetPassword(email) {
  return supabase.auth.resetPasswordForEmail(email, { redirectTo: window.location.href.split('#')[0].split('?')[0] });
}
