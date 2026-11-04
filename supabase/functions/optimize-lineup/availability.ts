// Availability decisions are fail-closed: no unverified player can enter a lineup.
export type AvailabilityRow = {
  availability: string | null;
  observed_at: string | null;
  injury_status: string | null;
  roster_status: string | null;
};
const UNAVAILABLE = new Set(["OUT", "IR", "INJURED_RESERVE", "INJURY_RESERVE", "PUP", "INACTIVE", "SUSPENDED", "EXEMPT", "EXEMPT_LIST", "RESERVE/EXEMPT", "RESERVE_EXEMPT"]);
const RISKY = new Set(["QUESTIONABLE", "DOUBTFUL", "Q", "D"]);
export function eligibility(row: AvailabilityRow, strategy: "best" | "safe"): "eligible" | "excluded" {
  if (!row.observed_at || !Number.isFinite(Date.parse(row.observed_at)) ||
      !["available_reported", "unavailable_reported"].includes(String(row.availability || "")))
    throw new Error("Player availability unverified");
  const injury=String(row.injury_status||"").trim().toUpperCase();
  const roster=String(row.roster_status||"").trim().toUpperCase();
  if (row.availability==="unavailable_reported" || UNAVAILABLE.has(injury) || UNAVAILABLE.has(roster))
    return "excluded";
  if (strategy==="safe" && RISKY.has(injury)) return "excluded";
  return "eligible";
}
