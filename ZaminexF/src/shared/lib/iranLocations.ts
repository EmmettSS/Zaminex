// =============================================================================
//  Iran location coordinates + free geocoding helpers
// =============================================================================
// Leaflet needs a [lat, lng] to fly to when a province / city / district is
// selected. Provinces and the major cities have a static, always-available
// reference (no API, no key). Districts and any city not in the table are
// resolved on the fly via Nominatim (OpenStreetMap's free geocoder) with the
// province center as a reliable fallback — so the map always lands somewhere
// sensible even when offline.
// =============================================================================

export type LatLng = [number, number];

/** Approximate centre of each Iranian province, keyed by Persian display name. */
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

/** Common Iranian cities → [lat, lng] (capital + a few large ones). */
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

/** Default view: northern Iran (Tehran area, zoomed to country level). */
export const IRAN_DEFAULT_CENTER: LatLng = [35.6892, 53.0];
export const IRAN_DEFAULT_ZOOM = 5;

/**
 * Resolve a place name to coordinates for free.
 * 1. Checks the static Iran reference tables first (always available).
 * 2. Otherwise geocodes via Nominatim (OSM) — no key, no sign-up.
 *
 * ``context`` scopes the lookup with the parent province / city. This matters
 * most for districts: a neighbourhood name like "گلستان" exists in many
 * cities, so searching the bare name returns an arbitrary match in another
 * province. Qualifying the query with the selected city and province makes
 * Nominatim resolve the exact selected neighbourhood.
 *
 * Returns null when nothing can be resolved.
 */
export async function resolvePlaceCoordinates(
  name: string,
  kind: "province" | "city" | "district",
  context?: { provinceName?: string; cityName?: string }
): Promise<LatLng | null> {
  const clean = (name || "").trim();
  if (!clean) return null;

  if (kind === "province") {
    const c = IRAN_PROVINCE_CENTERS[clean];
    if (c) return c;
  }
  if (kind === "city") {
    const c = IRAN_CITY_CENTERS[clean];
    if (c) return c;
  }

  try {
    const url = new URL("https://nominatim.openstreetmap.org/search");
    // Build a qualified query: most specific name first, then the parent
    // city and province, so a repeated name resolves in the right place.
    const query = [clean];
    if (kind === "district") {
      const city = context?.cityName?.trim();
      const province = context?.provinceName?.trim();
      if (city) query.push(city);
      if (province) query.push(province);
    } else if (kind === "city") {
      const province = context?.provinceName?.trim();
      if (province) query.push(province);
    }
    url.searchParams.set("q", query.join(", "));
    url.searchParams.set("countrycodes", "ir");
    url.searchParams.set("format", "jsonv2");
    url.searchParams.set("limit", "1");
    const res = await fetch(url.toString(), {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (Array.isArray(data) && data.length > 0) {
      const lat = parseFloat(data[0].lat);
      const lon = parseFloat(data[0].lon);
      if (!Number.isNaN(lat) && !Number.isNaN(lon)) return [lat, lon];
    }
  } catch {
    // offline / blocked → fall through to null (caller uses province center)
  }
  return null;
}
