import { supabase, signUp, signIn, signOut, getSession, resetPassword } from "./auth.js";
const $ = id => document.getElementById(id);
let mode = "login";
let busy = false;
const message = (text, error = false) => { $("message").textContent = text; $("message").classList.remove("hidden"); $("message").classList.toggle("error", error); };
function setMode(next) {
  mode = next; $("message").classList.add("hidden");
  $("tabs").classList.toggle("hidden", next === "reset" || next === "update");
  $("tab-login").setAttribute("aria-selected", String(next === "login"));
  $("tab-signup").setAttribute("aria-selected", String(next === "signup"));
  $("heading").textContent = ({ login: "Welcome back", signup: "Create your free account", reset: "Reset your password", update: "Choose a new password" })[next];
  $("email-row").classList.toggle("hidden", next === "update");
  $("password-row").classList.toggle("hidden", next === "reset");
  $("email").required = next !== "update";
  $("password").required = next !== "reset";
  $("password").autocomplete = next === "login" ? "current-password" : "new-password";
  $("submit").textContent = ({login:"Log in",signup:"Create account",reset:"Send reset email",update:"Update password"})[next];
  $("forgot").classList.toggle("hidden", next !== "login");
  $("back").classList.toggle("hidden", next !== "reset");
}
$("tab-login").addEventListener("click", () => setMode("login"));
$("tab-signup").addEventListener("click", () => setMode("signup"));
$("forgot").addEventListener("click", () => setMode("reset"));
$("back").addEventListener("click", () => setMode("login"));
function showSession(session) {
  const signedIn = !!session?.user;
  $("signed-in").classList.toggle("hidden", !signedIn || mode === "update");
  $("account-form").classList.toggle("hidden", signedIn && mode !== "update");
  $("tabs").classList.toggle("hidden", signedIn || mode === "reset" || mode === "update");
  $("heading").textContent = signedIn && mode !== "update" ? "You're signed in" : ({login:"Welcome back",signup:"Create your free account",reset:"Reset your password",update:"Choose a new password"})[mode];
  $("account-name").textContent = signedIn ? "Signed in as " + (session.user.email || "DATA DADDY member") : "";
  $("forgot").classList.toggle("hidden", signedIn || mode !== "login");
}
$("account-form").addEventListener("submit", async event => {
  event.preventDefault(); if (busy) return; busy = true; $("submit").disabled = true; $("message").classList.add("hidden");
  const email = $("email").value.trim(), password = $("password").value;
  try {
    let result;
    if (mode === "signup") result = await signUp(email, password);
    else if (mode === "login") result = await signIn(email, password);
    else if (mode === "reset") result = await resetPassword(email);
    else result = await supabase.auth.updateUser({ password });
    if (result.error) throw result.error;
    if (mode === "signup") message("Check your email for a confirmation link. Confirm your address before logging in.");
    else if (mode === "reset") message("If an account exists for that email, you'll receive a password reset link.");
    else if (mode === "update") { setMode("login"); message("Password updated successfully."); }
    else { message("Logged in successfully."); showSession((await getSession()).data.session); }
  } catch (err) { message(err?.message || "Something went wrong. Please try again.", true); }
  finally { busy = false; $("submit").disabled = false; }
});
$("logout").addEventListener("click", async () => {
  const {error} = await signOut(); if (error) message(error.message,true); else {setMode("login");showSession(null);message("Logged out.");}
});
supabase.auth.onAuthStateChange((event, session) => {
  if (event === "PASSWORD_RECOVERY") { setMode("update"); showSession(session); }
  else if (mode !== "update") showSession(session);
});
const { data, error } = await getSession();
if (error) message("Could not load session: " + error.message, true);
else if (mode !== "update") showSession(data.session);
