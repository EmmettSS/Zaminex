export const CONSULTANT_MARKER_COLORS: string[] = [
  "#0BB68A",
  "#EF4444",
  "#3B82F6",
  "#F59E0B",
  "#8B5CF6",
  "#EC4899",
  "#14B8A6",
  "#F97316",
  "#6366F1",
  "#84CC16",
  "#06B6D4",
  "#A855F7",
  "#E11D48",
  "#22C55E",
  "#EAB308",
  "#64748B",
];

export const CONSULTANT_FALLBACK_COLOR = "#94A3B8";

export function consultantMarkerColor(
  id: string | number | null | undefined,
  ids: Array<string | number | null | undefined>
): string {
  if (id === null || id === undefined || id === "") return CONSULTANT_FALLBACK_COLOR;
  const key = String(id);

  const unique: string[] = [];
  const seen = new Set<string>();
  ids.forEach((x) => {
    if (x === null || x === undefined || x === "") return;
    const s = String(x);
    if (!seen.has(s)) {
      seen.add(s);
      unique.push(s);
    }
  });

  unique.sort((a, b) => {
    const na = Number(a);
    const nb = Number(b);
    if (Number.isFinite(na) && Number.isFinite(nb)) return na - nb;
    return a.localeCompare(b);
  });

  const index = unique.indexOf(key);
  if (index === -1) return CONSULTANT_FALLBACK_COLOR;
  return CONSULTANT_MARKER_COLORS[index % CONSULTANT_MARKER_COLORS.length];
}
