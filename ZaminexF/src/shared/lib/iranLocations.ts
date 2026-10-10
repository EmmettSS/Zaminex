export type LatLng = [number, number];

export const IRAN_PROVINCE_CENTERS: Record<string, LatLng> = {
  "آذربایجان شرقی": [38.0801, 46.2919],
  "آذربایجان غربی": [37.5527, 45.076],
  "اردبیل": [38.2498, 48.2933],
  "اصفهان": [32.6539, 51.666],
  "البرز": [35.8400, 50.9391],
  "ایلام": [33.6374, 46.4227],
  "بوشهر": [28.9234, 50.8203],
  "تهران": [35.6892, 51.389],
  "چهارمحال و بختیاری": [32.3256, 50.8644],
  "خراسان جنوبی": [32.8664, 59.2211],
  "خراسان رضوی": [36.2605, 59.6168],
  "خراسان شمالی": [37.475, 57.3333],
  "خوزستان": [31.3183, 48.6706],
  "زنجان": [36.6736, 48.4787],
  "سمنان": [35.583, 53.3867],
  "سیستان و بلوچستان": [29.4963, 60.8629],
  "فارس": [29.5918, 52.5837],
  "قزوین": [36.2681, 50.0041],
  "قم": [34.6401, 50.8764],
  "کردستان": [35.3144, 46.9988],
  "کرمان": [30.2839, 57.0834],
  "کرمانشاه": [34.3142, 47.065],
  "کهگیلویه و بویراحمد": [30.6684, 51.588],
  "گلستان": [36.8456, 54.4394],
  "گیلان": [37.2808, 49.5832],
  "لرستان": [33.4878, 48.3558],
  "مازندران": [36.5633, 53.0601],
  "مرکزی": [34.0916, 49.689],
  "هرمزگان": [27.1832, 56.2666],
  "همدان": [34.7983, 48.5147],
  "یزد": [31.8974, 54.3569],
};

export const IRAN_CITY_CENTERS: Record<string, LatLng> = {
  "تهران": [35.6892, 51.389],
  "مشهد": [36.2605, 59.6168],
  "اصفهان": [32.6539, 51.666],
  "کرج": [35.84, 50.9391],
  "شیراز": [29.5918, 52.5837],
  "تبریز": [38.0801, 46.2919],
  "اهواز": [31.3183, 48.6706],
  "قم": [34.6401, 50.8764],
  "کرمانشاه": [34.3142, 47.065],
  "ارومیه": [37.5527, 45.076],
  "رشت": [37.2808, 49.5832],
  "زاهدان": [29.4963, 60.8629],
  "همدان": [34.7983, 48.5147],
  "کرمان": [30.2839, 57.0834],
  "یزد": [31.8974, 54.3569],
  "اردبیل": [38.2498, 48.2933],
  "بندرعباس": [27.1832, 56.2666],
  "ساری": [36.5633, 53.0601],
  "اراک": [34.0916, 49.689],
  "سنندج": [35.3144, 46.9988],
  "زنجان": [36.6736, 48.4787],
  "گرگان": [36.8456, 54.4394],
  "خرم‌آباد": [33.4878, 48.3558],
  "قزوین": [36.2681, 50.0041],
  "سمنان": [35.583, 53.3867],
  "بجنورد": [37.475, 57.3333],
  "بیرجند": [32.8664, 59.2211],
  "شهرکرد": [32.3256, 50.8644],
  "یاسوج": [30.6684, 51.588],
  "بوشهر": [28.9234, 50.8203],
  "ایلام": [33.6374, 46.4227],
};

export const DEFAULT_VIEW_CENTER: LatLng = [36.4, 53.2];
export const DEFAULT_VIEW_ZOOM = 8;

const EQUIVALENT_LETTERS: Record<string, string> = {
  "\u064a": "\u06cc",
  "\u0643": "\u06a9",
  "\u0629": "\u0647",
  "\u0649": "\u06cc",
  "\u0622": "\u0627",
  "\u0623": "\u0627",
  "\u0625": "\u0627",
  "\u0671": "\u0627",
};

const IGNORABLE_CHARACTERS = ["\u200c", "\u200d", "\u0640"];

export function normalizePlaceKey(value?: string | null): string {
  if (!value) return "";
  let text = value.normalize("NFC");
  for (const ch of IGNORABLE_CHARACTERS) text = text.split(ch).join("");
  text = Array.from(text)
    .filter((c) => !(c >= "\u064b" && c <= "\u0652")) // Arabic diacritics
    .map((c) => EQUIVALENT_LETTERS[c] ?? c)
    .join("");
    
  return text.split(/[\s\u200b-\u200f\u2060\ufeff]/).join("");
}

function normalizeCenters(table: Record<string, LatLng>): Record<string, LatLng> {
  const out: Record<string, LatLng> = {};
  for (const [name, center] of Object.entries(table)) {
    out[normalizePlaceKey(name)] = center;
  }
  return out;
}

const NORMALIZED_PROVINCE_CENTERS = normalizeCenters(IRAN_PROVINCE_CENTERS);
const NORMALIZED_CITY_CENTERS = normalizeCenters(IRAN_CITY_CENTERS);

function centerFrom(table: Record<string, LatLng>, name: string): LatLng | undefined {
  const key = normalizePlaceKey(name);
  return key ? table[key] : undefined;
}

type SearchOutcome =
  | { status: "found"; hit: GeocodeHit }
  | { status: "not_found" }
  | { status: "unavailable" };

async function geocodeSearch(
  query: string,
  viewbox: string | null,
  bounded: boolean
): Promise<SearchOutcome> {
  const params = new URLSearchParams();
  params.set("q", query);
  if (viewbox) {
    params.set("viewbox", viewbox);
    if (bounded) params.set("bounded", "1");
  }

  let res: Response;
  try {
    res = await fetch(`/common/api/geocode/?${params.toString()}`, {
      headers: { Accept: "application/json" },
      credentials: "include",
    });
  } catch {
    return { status: "unavailable" };
  }
  if (!res.ok) return { status: "unavailable" };

  let data: unknown;
  try {
    data = await res.json();
  } catch {
    return { status: "unavailable" };
  }
  if (!Array.isArray(data)) return { status: "unavailable" };

  const row = data[0] as
    | { lat?: unknown; lon?: unknown; address?: Record<string, string> }
    | undefined;
  const lat = Number(row?.lat);
  const lon = Number(row?.lon);
  if (!row || !Number.isFinite(lat) || !Number.isFinite(lon)) {
    return { status: "not_found" };
  }
  return { status: "found", hit: { lat, lon, address: row.address || undefined } };
}

function provinceViewbox(provinceName?: string): string | null {
  const c = provinceName ? centerFrom(NORMALIZED_PROVINCE_CENTERS, provinceName) : null;
  if (!c) return null;
  const [lat, lng] = c;
  const halfLat = 2.2;
  const halfLng = 3.5;
  return [
    (lng - halfLng).toFixed(2),
    (lat + halfLat).toFixed(2),
    (lng + halfLng).toFixed(2),
    (lat - halfLat).toFixed(2),
  ].join(",");
}

export type GeocodeHit = {
  lat: number;
  lon: number;
  address?: Record<string, string>;
};

export function buildQueryVariants(
  name: string,
  kind: "city" | "district",
  context?: { provinceName?: string; cityName?: string }
): string[] {
  const clean = (name || "").trim();
  const province = context?.provinceName?.trim();
  const city = context?.cityName?.trim();
  if (!clean) return [];
  const variants: string[] = [];
  if (kind === "district") {
    if (city && province) variants.push(`${clean}, ${city}, ${province}`);
    if (province) variants.push(`${clean}, ${province}`);
  } else if (province) {
    variants.push(`${clean}, ${province}`);
  }
  variants.push(clean);
  return variants;
}

export function variantIsFullyQualified(
  variant: string,
  kind: "city" | "district",
  context?: { provinceName?: string; cityName?: string }
): boolean {
  const province = context?.provinceName?.trim();
  const city = context?.cityName?.trim();
  if (kind === "district") {
    return (!city || variant.includes(city)) && (!province || variant.includes(province));
  }
  return !province || variant.includes(province);
}

export function acceptsResult(
  hit: GeocodeHit,
  province: string | undefined,
  fullyQualified: boolean
): boolean {
  if (fullyQualified) return true;
  if (!province) return true;
  const values = Object.values(hit.address || {})
    .map((v) => normalizePlaceKey(String(v)))
    .filter(Boolean);
  if (values.length === 0) return true;
  const wanted = normalizePlaceKey(province);
  for (const value of values) {
    for (const other of Object.keys(NORMALIZED_PROVINCE_CENTERS)) {
      if (other !== wanted && value === other) return false;
    }
  }
  return true;
}

export type ResolveOutcome =
  | { status: "found"; location: LatLng }
  | { status: "not_found" }
  | { status: "unavailable" };

const NOT_FOUND: ResolveOutcome = { status: "not_found" };
const UNAVAILABLE: ResolveOutcome = { status: "unavailable" };

export async function resolvePlace(
  name: string,
  kind: "province" | "city" | "district",
  context?: { provinceName?: string; cityName?: string },
  options?: { variants?: boolean }
): Promise<ResolveOutcome> {
  const clean = (name || "").trim();
  if (!clean) return NOT_FOUND;

  const province = context?.provinceName?.trim() || undefined;
  const city = context?.cityName?.trim() || undefined;
  const viewbox = provinceViewbox(province);

  if (kind === "province") {
    const center = centerFrom(NORMALIZED_PROVINCE_CENTERS, clean);
    if (center) return { status: "found", location: center };
    const outcome = await geocodeSearch(clean, null, false);
    if (outcome.status === "unavailable") return UNAVAILABLE;
    return outcome.status === "found"
      ? { status: "found", location: [outcome.hit.lat, outcome.hit.lon] }
      : NOT_FOUND;
  }
  if (kind === "city") {
    const center = centerFrom(NORMALIZED_CITY_CENTERS, clean);
    if (center) return { status: "found", location: center };
  }

  if (!options?.variants) {
    const variants = buildQueryVariants(clean, kind === "city" ? "city" : "district", context);
    for (const variant of variants) {
      const outcome = await geocodeSearch(variant, viewbox, false);
      if (outcome.status === "unavailable") return UNAVAILABLE;
      if (outcome.status === "found") {
        return { status: "found", location: [outcome.hit.lat, outcome.hit.lon] };
      }
    }
    return NOT_FOUND;
  }

  for (const variant of buildQueryVariants(clean, kind, context)) {
    const fullyQualified = variantIsFullyQualified(variant, kind, context);
    const outcome = await geocodeSearch(variant, viewbox, !fullyQualified);
    if (outcome.status === "unavailable") return UNAVAILABLE;
    if (outcome.status === "found" && acceptsResult(outcome.hit, province, fullyQualified)) {
      return { status: "found", location: [outcome.hit.lat, outcome.hit.lon] };
    }
  }
  return NOT_FOUND;
}

export async function resolvePlaceCoordinates(
  name: string,
  kind: "province" | "city" | "district",
  context?: { provinceName?: string; cityName?: string },
  options?: { variants?: boolean }
): Promise<LatLng | null> {
  const outcome = await resolvePlace(name, kind, context, options);
  return outcome.status === "found" ? outcome.location : null;
}
