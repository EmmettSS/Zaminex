import React, { useEffect, useMemo, useState, useRef } from "react";
import { apiFetch } from "../../lib/apiClient";
import { ChevronDown, Search, Check, MapPin } from "lucide-react";
import { cx } from "../../lib/utils";
import { fuzzyFilter } from "../../lib/fuzzySearch";

/**
 * Cascading استان → شهر → محله picker.
 *
 * The three levels are administrator-managed, so the whole tree is fetched once
 * from `/basics/api/locations/` and filtered client-side — one request instead
 * of a round trip per dropdown.
 *
 * Now uses searchable comboboxes styled exactly like ConsultantCombobox /
 * DistrictCombobox (MapPin, searchable inside list) as requested.
 */

export type LocationDistrict = { id: number; name: string; displayName: string };
export type LocationCity = { id: number; name: string; displayName: string; districts: LocationDistrict[] };
export type LocationProvince = { id: number; name: string; displayName: string; cities: LocationCity[] };

/** Fetches the province → city → district tree once per mount. */
export function useLocationTree(csrfToken?: string) {
  const [tree, setTree] = useState<LocationProvince[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch("/basics/api/locations/", { method: "GET" }, csrfToken);
        if (!res.ok) throw new Error();
        const data = await res.json();
        if (!cancelled) setTree(Array.isArray(data) ? data : []);
      } catch {
        if (!cancelled) setTree([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [csrfToken]);

  return { tree, loading };
}

/**
 * Given a district id, find the city and province above it.
 * Used when editing a property, which only stores the leaf.
 */
export function findLocationPath(tree: LocationProvince[], districtId: string | number | null | undefined) {
  if (!districtId) return { provinceId: "", cityId: "" };
  for (const province of tree) {
    for (const city of province.cities) {
      if (city.districts.some((d) => String(d.id) === String(districtId))) {
        return { provinceId: String(province.id), cityId: String(city.id) };
      }
    }
  }
  return { provinceId: "", cityId: "" };
}

/* ──────────────────────────────────────────────────────────────
   Searchable combobox styled like ConsultantCombobox / DistrictCombobox
   ────────────────────────────────────────────────────────────── */

type LocationOption = { id: string | number; displayName: string };

function SearchableLocationCombobox({
  label,
  value,
  onChange,
  options,
  placeholder,
  searchPlaceholder,
  error,
  required,
  disabled,
}: {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  options: LocationOption[];
  placeholder?: string;
  searchPlaceholder?: string;
  error?: string;
  required?: boolean;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(0);

  const filtered = useMemo(
    () => fuzzyFilter(options, q, (o) => o.displayName),
    [options, q]
  );

  const selectedLabel = useMemo(
    () => options.find((o) => String(o.id) === String(value))?.displayName || "",
    [options, value]
  );

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setFocused(0);
    } else {
      setQ("");
    }
  }, [open]);

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocused((p) => Math.min(p + 1, filtered.length - 1));
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocused((p) => Math.max(p - 1, 0));
    }
    if (e.key === "Enter" && filtered[focused]) {
      onChange(String(filtered[focused].id));
      setOpen(false);
    }
    if (e.key === "Escape") setOpen(false);
  };

  const hl = (text: string) => {
    if (!q) return <>{text}</>;
    const i = text.toLowerCase().indexOf(q.toLowerCase());
    if (i === -1) return <>{text}</>;
    return (
      <>
        {text.slice(0, i)}
        <mark className="bg-primary/20 text-primary rounded-sm not-italic">
          {text.slice(i, i + q.length)}
        </mark>
        {text.slice(i + q.length)}
      </>
    );
  };

  return (
    <div className="flex flex-col gap-1.5" ref={ref}>
      {label && (
        <label className="text-xs font-medium text-foreground">
          {label}
          {required && <span className="text-primary mr-1">*</span>}
        </label>
      )}
      <div className="relative">
        <button
          type="button"
          onClick={() => !disabled && setOpen(!open)}
          disabled={disabled}
          aria-expanded={open}
          className={cx(
            "w-full flex items-center gap-2 rounded-xl border border-border bg-input-background px-3 py-2.5 text-sm text-right transition-all outline-none focus:ring-2 focus:ring-ring",
            open && "border-primary ring-2 ring-ring",
            disabled ? "opacity-60 cursor-not-allowed" : "hover:border-primary/30",
            error && "border-destructive focus:ring-destructive/20"
          )}
        >
          <MapPin size={13} className="text-muted-foreground flex-shrink-0" />
          <span className={cx("flex-1 truncate", value && selectedLabel ? "text-foreground font-medium" : "text-muted-foreground")}>
            {selectedLabel || placeholder || "انتخاب..."}
          </span>
          <ChevronDown size={13} className={cx("text-muted-foreground transition-transform flex-shrink-0", open && "rotate-180")} />
        </button>

        {open && !disabled && (
          <div className="absolute z-50 w-full mt-1 bg-card rounded-xl border border-border shadow-lg overflow-hidden">
            <div className="p-2 border-b border-border">
              <div className="relative">
                <Search size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  ref={inputRef}
                  value={q}
                  onChange={(e) => {
                    setQ(e.target.value);
                    setFocused(0);
                  }}
                  onKeyDown={handleKey}
                  placeholder={searchPlaceholder || "جستجو..."}
                  className="w-full pr-7 pl-2 py-1.5 text-xs bg-secondary rounded-lg outline-none placeholder:text-muted-foreground"
                />
              </div>
            </div>

            <div className="max-h-52 overflow-y-auto py-1">
              {filtered.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">موردی یافت نشد</p>
              ) : (
                filtered.map((opt, i) => (
                  <button
                    key={String(opt.id)}
                    type="button"
                    onMouseEnter={() => setFocused(i)}
                    onClick={() => {
                      onChange(String(opt.id));
                      setOpen(false);
                    }}
                    className={cx(
                      "w-full flex items-center gap-3 px-3 py-2.5 text-right transition-colors text-xs",
                      i === focused ? "bg-secondary" : "hover:bg-secondary/50",
                      String(value) === String(opt.id) && "bg-primary/5 text-primary font-medium"
                    )}
                  >
                    <MapPin size={12} className="text-muted-foreground flex-shrink-0" />
                    <span className="flex-1 text-right">{hl(opt.displayName)}</span>
                    {String(value) === String(opt.id) && <Check size={12} className="text-primary flex-shrink-0" />}
                  </button>
                ))
              )}
            </div>
          </div>
        )}
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

function LocationSelect({
  tree,
  provinceId,
  cityId,
  districtId,
  onProvinceChange,
  onCityChange,
  onDistrictChange,
  errors = {},
  required,
}: {
  tree: LocationProvince[];
  provinceId: string;
  cityId: string;
  districtId: string;
  onProvinceChange: (v: string) => void;
  onCityChange: (v: string) => void;
  onDistrictChange: (v: string) => void;
  errors?: Record<string, string>;
  required?: boolean;
}) {
  const cities = useMemo(
    () => tree.find((p) => String(p.id) === String(provinceId))?.cities ?? [],
    [tree, provinceId]
  );
  const districts = useMemo(
    () => cities.find((c) => String(c.id) === String(cityId))?.districts ?? [],
    [cities, cityId]
  );

  const provinceOptions: LocationOption[] = useMemo(
    () => tree.map((p) => ({ id: p.id, displayName: p.displayName })),
    [tree]
  );

  const cityOptions: LocationOption[] = useMemo(
    () => cities.map((c) => ({ id: c.id, displayName: c.displayName })),
    [cities]
  );

  const districtOptions: LocationOption[] = useMemo(
    () => districts.map((d) => ({ id: d.id, displayName: d.displayName })),
    [districts]
  );

  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <SearchableLocationCombobox
          label="استان"
          value={provinceId}
          onChange={onProvinceChange}
          options={provinceOptions}
          placeholder="انتخاب استان"
          searchPlaceholder="جستجوی استان…"
          error={errors.provinceId}
          required={required}
        />
        <SearchableLocationCombobox
          label="شهر"
          value={cityId}
          onChange={onCityChange}
          options={cityOptions}
          placeholder={provinceId ? "انتخاب شهر" : "ابتدا استان را انتخاب کنید"}
          searchPlaceholder="جستجوی شهر…"
          error={errors.cityId}
          required={required}
          disabled={!provinceId}
        />
      </div>
      <SearchableLocationCombobox
        label="محله"
        value={districtId}
        onChange={onDistrictChange}
        options={districtOptions}
        placeholder={cityId ? "انتخاب محله" : "ابتدا شهر را انتخاب کنید"}
        searchPlaceholder="جستجوی محله…"
        error={errors.districtId}
        required={required}
        disabled={!cityId}
      />
    </>
  );
}

export { LocationSelect };
