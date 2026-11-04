// Testable request authorization and allowance sequencing.
// No Supabase credentials, network requests, or production data.
export type Decision = { allowed: boolean };
export type GateDependencies<T> = {
  authenticate: () => Promise<boolean>;
  loadApprovedSnapshot: () => Promise<T | null>;
  validateAndOptimize: (snapshot: T) => Promise<unknown | null>;
  consumeAllowance: () => Promise<Decision>;
};
export type GateResult = { status: number; error?: string; result?: unknown };
export async function executeProtectedOptimization<T>(deps: GateDependencies<T>): Promise<GateResult> {
  if (!(await deps.authenticate())) return { status: 401, error: "Sign in required" };
  const snapshot = await deps.loadApprovedSnapshot();
  if (!snapshot) return { status: 409, error: "No approved projection snapshot" };
  const result = await deps.validateAndOptimize(snapshot);
  if (!result) return { status: 422, error: "No legal lineup" };
  const allowance = await deps.consumeAllowance();
  if (!allowance.allowed) return { status: 402, error: "Free use exhausted" };
  return { status: 200, result };
}
