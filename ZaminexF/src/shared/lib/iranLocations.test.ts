import { afterEach, describe, expect, it, vi } from "vitest";
import {
  acceptsResult,
  buildQueryVariants,
  normalizePlaceKey,
  resolvePlace,
  resolvePlaceCoordinates,
  variantIsFullyQualified,
  type GeocodeHit,
} from "./iranLocations";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function qOf(url: string): string | null {
  return new URL(url, "http://test.local").searchParams.get("q");
}

function paramsOf(url: string): URLSearchParams {
  return new URL(String(url), "http://test.local").searchParams;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const PARITY_CASES: Array<[string, string]> = [
  ["خرم‌آباد", "خرماباد"],
  ["خرم اباد", "خرماباد"],
  ["بندر  عباس", "بندرعباس"],
  ["آبادان", "ابادان"],
  ["قائم‌شهر", "قائمشهر"],
  ["قائم شهر", "قائمشهر"],
  ["مشهد", "مشهد"],
  ["", ""],
  ["   ", ""],
];

describe("normalizePlaceKey", () => {
  it("matches the Python implementation's expectations", () => {
    for (const [raw, expected] of PARITY_CASES) {
      expect(normalizePlaceKey(raw)).toBe(expected);
    }
  });

  it("never merges two genuinely different names", () => {
    expect(normalizePlaceKey("تهران")).not.toBe(normalizePlaceKey("تهرانر"));
    expect(normalizePlaceKey("کرج")).not.toBe(normalizePlaceKey("گرگ"));
  });
});

describe("buildQueryVariants", () => {
  it("district with city + province → most specific first", () => {
    expect(
      buildQueryVariants("گلستان", "district", {
        provinceName: "مازندران",
        cityName: "ساری",
      })
    ).toEqual(["گلستان, ساری, مازندران", "گلستان, مازندران", "گلستان"]);
  });

  it("district with province only → skip the city slot", () => {
    expect(
      buildQueryVariants("گلستان", "district", { provinceName: "مازندران" })
    ).toEqual(["گلستان, مازندران", "گلستان"]);
  });

  it("district with no parents → bare name only", () => {
    expect(buildQueryVariants("گلستان", "district")).toEqual(["گلستان"]);
  });

  it("city with province → qualified then bare", () => {
    expect(
      buildQueryVariants("ساری", "city", { provinceName: "مازندران" })
    ).toEqual(["ساری, مازندران", "ساری"]);
  });

  it("city with no province → bare name only", () => {
    expect(buildQueryVariants("ساری", "city")).toEqual(["ساری"]);
  });

  it("empty name → no variants", () => {
    expect(buildQueryVariants("  ", "city")).toEqual([]);
  });
});

describe("variantIsFullyQualified", () => {
  it("district with all parents present", () => {
    expect(
      variantIsFullyQualified("گلستان, ساری, مازندران", "district", {
        provinceName: "مازندران",
        cityName: "ساری",
      })
    ).toBe(true);
  });

  it("district missing the city is not fully qualified", () => {
    expect(
      variantIsFullyQualified("گلستان, مازندران", "district", {
        provinceName: "مازندران",
        cityName: "ساری",
      })
    ).toBe(false);
  });

  it("bare district name is not fully qualified", () => {
    expect(
      variantIsFullyQualified("گلستان", "district", {
        provinceName: "مازندران",
        cityName: "ساری",
      })
    ).toBe(false);
  });

  it("city with province is fully qualified", () => {
    expect(
      variantIsFullyQualified("ساری, مازندران", "city", { provinceName: "مازندران" })
    ).toBe(true);
  });

  it("bare city with a selected province is not fully qualified", () => {
    expect(
      variantIsFullyQualified("ساری", "city", { provinceName: "مازندران" })
    ).toBe(false);
  });
});


describe("acceptsResult", () => {
  const hit = (address?: Record<string, string>): GeocodeHit => ({
    lat: 36.5,
    lon: 53.0,
    address,
  });

  it("fully qualified → accept top hit regardless of address", () => {
    expect(acceptsResult(hit({ province: "تهران" }), "مازندران", true)).toBe(true);
  });

  it("no province context → accept", () => {
    expect(acceptsResult(hit({ province: "تهران" }), undefined, false)).toBe(true);
  });

  it("missing address info → accept", () => {
    expect(acceptsResult(hit(undefined), "مازندران", false)).toBe(true);
  });

  it("English-only address (untranslatable) → accept (no clear mismatch)", () => {
    expect(
      acceptsResult(hit({ province: "Mazandaran Province", city: "Sari" }), "مازندران", false)
    ).toBe(true);
  });

  it("matching Persian province → accept", () => {
    expect(acceptsResult(hit({ province: "مازندران" }), "مازندران", false)).toBe(true);
  });

  it("a different Persian province → hard reject", () => {
    expect(acceptsResult(hit({ province: "تهران" }), "مازندران", false)).toBe(false);
  });
});


describe("resolvePlace / resolvePlaceCoordinates", () => {
  it("province → static table, no network", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const result = await resolvePlaceCoordinates("مازندران", "province");
    expect(result).toEqual([36.5633, 53.0601]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("structured city → qualified variant first, accepts top hit", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse([
        { lat: "36.6511", lon: "51.4965", address: { city: "Nowshahr", province: "Mazandaran Province" } },
      ])
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await resolvePlaceCoordinates(
      "نوشهر",
      "city",
      { provinceName: "مازندران" },
      { variants: true }
    );

    expect(result).toEqual([36.6511, 51.4965]);
    const queries = fetchMock.mock.calls.map(([u]) => qOf(String(u)));
    expect(queries).toEqual(["نوشهر, مازندران"]);
  });

  it("city in the static table → resolved offline, zero network calls", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const result = await resolvePlaceCoordinates(
      "ساری",
      "city",
      { provinceName: "مازندران" },
      { variants: true }
    );

    expect(result).toEqual([36.5633, 53.0601]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("table lookup matches a differently spelled name (ZWNJ / Arabic letters)", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    expect(normalizePlaceKey("خرم اباد")).toBe(normalizePlaceKey("خرم‌آباد"));
    const result = await resolvePlaceCoordinates("خرم اباد", "city", undefined, {
      variants: true,
    });
    expect(result).toEqual([33.4878, 48.3558]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("requests go to the same-origin proxy with q / viewbox / bounded", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse([{ lat: "36.6511", lon: "51.4965", address: { city: "Nowshahr" } }])
    );
    vi.stubGlobal("fetch", fetchMock);

    await resolvePlaceCoordinates("نوشهر", "city", { provinceName: "مازندران" }, { variants: true });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0];
    expect(String(url).startsWith("/common/api/geocode/?")).toBe(true);
    const params = paramsOf(url);
    expect(params.get("q")).toBe("نوشهر, مازندران");
    expect(params.get("viewbox")).toMatch(/^[-\d.]+,[-\d.]+,[-\d.]+,[-\d.]+$/);
    expect(params.has("bounded")).toBe(false);
  });

  it("only a not-yet-fully-qualified variant is sent bounded", async () => {
    const fetchMock = vi.fn(async () => jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await resolvePlaceCoordinates(
      "مرکزی",
      "district",
      { provinceName: "مازندران", cityName: "ساری" },
      { variants: true }
    );

    expect(fetchMock).toHaveBeenCalledTimes(3);
    const [first, second, third] = fetchMock.mock.calls.map(([u]) => paramsOf(String(u)));
    expect(first.get("q")).toBe("مرکزی, ساری, مازندران");
    expect(first.has("bounded")).toBe(false);
    expect(second.get("q")).toBe("مرکزی, مازندران");
    expect(second.get("bounded")).toBe("1");
    expect(third.get("q")).toBe("مرکزی");
    expect(third.get("bounded")).toBe("1");
  });

  it("structured district → ladder falls through to the next variant", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      const q = qOf(String(url));
      if (q === "مرکزی, ساری, مازندران") return jsonResponse([]);
      if (q === "مرکزی, مازندران")
        return jsonResponse([
          { lat: "36.56", lon: "53.06", address: { city: "Sari", province: "Mazandaran Province" } },
        ]);
      throw new Error(`unexpected query: ${q}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await resolvePlaceCoordinates(
      "مرکزی",
      "district",
      { provinceName: "مازندران", cityName: "ساری" },
      { variants: true }
    );

    expect(result).toEqual([36.56, 53.06]);
    const queries = fetchMock.mock.calls.map(([u]) => qOf(String(u)));
    expect(queries).toEqual(["مرکزی, ساری, مازندران", "مرکزی, مازندران"]);
  });

  it("partially-qualified hit in the wrong province is rejected → null", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      const q = qOf(String(url));
      if (q === "نوشهر, مازندران") return jsonResponse([]);
      if (q === "نوشهر")
        return jsonResponse([{ lat: "35.6892", lon: "51.389", address: { province: "تهران" } }]);
      throw new Error(`unexpected query: ${q}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await resolvePlaceCoordinates(
      "نوشهر",
      "city",
      { provinceName: "مازندران" },
      { variants: true }
    );

    expect(result).toBeNull();
    const queries = fetchMock.mock.calls.map(([u]) => qOf(String(u)));
    expect(queries).toEqual(["نوشهر, مازندران", "نوشهر"]);
  });

  it("offline (fetch rejects) → unavailable, and the wrapper still yields null", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("network down");
      })
    );
    const outcome = await resolvePlace(
      "نوشهر",
      "city",
      { provinceName: "مازندران" },
      { variants: true }
    );
    expect(outcome.status).toBe("unavailable");
    const result = await resolvePlaceCoordinates(
      "نوشهر",
      "city",
      { provinceName: "مازندران" },
      { variants: true }
    );
    expect(result).toBeNull();
  });

  it("proxy 503 (upstream unreachable) → unavailable, ladder stops at once", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ detail: "سرویس در دسترس نیست" }, 503));
    vi.stubGlobal("fetch", fetchMock);

    const outcome = await resolvePlace(
      "نوشهر",
      "city",
      { provinceName: "مازندران" },
      { variants: true }
    );

    expect(outcome).toEqual({ status: "unavailable" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("empty result from the proxy → not_found, distinct from unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse([])));
    const outcome = await resolvePlace("نوشهر", "city", { provinceName: "مازندران" }, {
      variants: true,
    });
    expect(outcome).toEqual({ status: "not_found" });
  });

  it("free-text search resolves the first hit on the most-specific query", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse([{ lat: "36.56", lon: "53.06", address: { city: "Sari" } }])
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await resolvePlaceCoordinates("گلستان", "district", {
      provinceName: "مازندران",
      cityName: "ساری",
    });

    expect(result).toEqual([36.56, 53.06]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(qOf(String(fetchMock.mock.calls[0][0]))).toBe("گلستان, ساری, مازندران");
  });

  it("free-text search sends every query unbounded (province only biases ranking)", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse([{ lat: "36.56", lon: "53.06", address: { city: "Sari" } }])
    );
    vi.stubGlobal("fetch", fetchMock);

    await resolvePlaceCoordinates("گلستان", "district", {
      provinceName: "مازندران",
      cityName: "ساری",
    });

    const params = paramsOf(fetchMock.mock.calls[0][0]);
    expect(params.has("bounded")).toBe(false);
    expect(params.has("viewbox")).toBe(true);
  });

  it("free-text search accepts a hit in another province (intentional cross-province search)", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse([{ lat: "35.6892", lon: "51.389", address: { province: "تهران" } }])
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await resolvePlaceCoordinates("گلستان", "district", {
      provinceName: "مازندران",
    });

    expect(result).toEqual([35.6892, 51.389]);
  });

  it("free-text search walks the ladder to the bare query when specific variants miss", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      const q = qOf(String(url));
      if (q === "گلستان") {
        return jsonResponse([{ lat: "35.6892", lon: "51.389", address: { province: "تهران" } }]);
      }
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await resolvePlaceCoordinates("گلستان", "district", {
      provinceName: "مازندران",
      cityName: "ساری",
    });

    expect(result).toEqual([35.6892, 51.389]);
    const queries = fetchMock.mock.calls.map(([u]) => qOf(String(u)));
    expect(queries).toEqual(["گلستان, ساری, مازندران", "گلستان, مازندران", "گلستان"]);
  });

  it("free-text search with no location selected sends the bare query", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse([{ lat: "35.6892", lon: "51.389" }])
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await resolvePlaceCoordinates("میدان آزادی تهران", "district");

    expect(result).toEqual([35.6892, 51.389]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const params = paramsOf(fetchMock.mock.calls[0][0]);
    expect(params.get("q")).toBe("میدان آزادی تهران");
    expect(params.has("viewbox")).toBe(false);
    expect(params.has("bounded")).toBe(false);
  });

  it("free-text search → unavailable is distinct from not_found", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ detail: "down" }, 503));
    vi.stubGlobal("fetch", fetchMock);

    const outcome = await resolvePlace("گلستان", "district", {
      provinceName: "مازندران",
    });

    expect(outcome).toEqual({ status: "unavailable" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("free-text search → not_found when every variant misses", async () => {
    const fetchMock = vi.fn(async () => jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    const outcome = await resolvePlace("جای‌ناموجود", "district", {
      provinceName: "مازندران",
      cityName: "ساری",
    });

    expect(outcome).toEqual({ status: "not_found" });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("empty name → not_found, no request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const outcome = await resolvePlace("   ", "district");
    expect(outcome).toEqual({ status: "not_found" });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
