import React from "react";
import { SelectField } from "./SelectField";
import { JalaliDateInput } from "./JalaliDateInput";
import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/apiClient";

/**
 * The extra filters a property type contributes to the search bar, built from
 * `/basics/api/schema/search/`.
 *
 * Rendered with the same `SelectField` and bare `input` styling the surrounding
 * filter row already uses, so the generated controls sit in the existing
 * `grid-cols-6` layout without looking bolted on.
 */

export type SearchFilterDef = {
  id: number;
  name: string;
  displayName: string;
  dataType: string;
  filterType: string;
  unit?: string;
  isCore: boolean;
  coreField?: string;
  sortOrder: string | number;
  options: { value: string; displayName: string }[];
};

/** Loads the filter definitions for one property type. */
export function useSearchSchema(
  propertyTypeId: string | number | null | undefined,
  csrfToken?: string
) {
  const [filters, setFilters] = useState<SearchFilterDef[]>([]);

  useEffect(() => {
    if (!propertyTypeId) {
      setFilters([]);
      return;
    }
    let cancelled = false;
    const controller = new AbortController();
    (async () => {
      try {
        const res = await apiFetch(
          `/basics/api/schema/search/?propertyType=${propertyTypeId}`,
          { method: "GET", signal: controller.signal },
          csrfToken
        );
        if (!res.ok) throw new Error();
        const data = await res.json();
        if (!cancelled) setFilters(data.propertyFilters ?? []);
      } catch {
        // Non-fatal: the bar keeps its built-in filters and simply shows no
        // type-specific ones.
        if (!cancelled) setFilters([]);
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [propertyTypeId, csrfToken]);

  return filters;
}

/**
 * Turns the current values into the query parameters the API expects:
 * `attr_<name>`, `attr_<name>_min`, `attr_<name>_max`.
 */
export function buildAttributeParams(values: Record<string, string>): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== "" && value != null) params.append(`attr_${key}`, value);
  });
  return params.toString();
}

const RANGE_FILTERS = new Set(["range", "range_fast"]);

/** Matches the plain inputs already used for the price range in the filter row. */
const INPUT_CLASS =
  "w-full rounded-xl border border-border bg-input-background px-2.5 py-2 text-xs outline-none focus:ring-2 focus:ring-ring";

function DynamicSearchFilters({
  filters,
  values,
  onChange,
}: {
  filters: SearchFilterDef[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
}) {
  if (!filters.length) return null;

  return (
    <>
      {filters.map((f) => {
        const label = f.unit ? `${f.displayName} (${f.unit})` : f.displayName;

        // Booleans read as a yes/no choice rather than a checkbox: a filter
        // needs three states — yes, no, and "don't care".
        if (f.dataType === "boolean") {
          return (
            <SelectField
              key={f.name}
              placeholder={f.displayName}
              value={values[f.name] ?? ""}
              onChange={(v) => onChange(f.name, v)}
              options={[
                { label: `${f.displayName}: دارد`, value: "true" },
                { label: `${f.displayName}: ندارد`, value: "false" },
              ]}
            />
          );
        }

        if (f.dataType === "select" || f.dataType === "multiselect") {
          return (
            <SelectField
              key={f.name}
              placeholder={f.displayName}
              value={values[f.name] ?? ""}
              onChange={(v) => onChange(f.name, v)}
              options={f.options.map((o) => ({ label: o.displayName, value: o.value }))}
            />
          );
        }

        const numeric = f.dataType === "integer" || f.dataType === "decimal";
        if (numeric && RANGE_FILTERS.has(f.filterType)) {
          return (
            <div key={f.name} className="flex gap-1.5">
              <input
                type="number"
                placeholder={`حداقل ${f.displayName}`}
                value={values[`${f.name}_min`] ?? ""}
                onChange={(e) => onChange(`${f.name}_min`, e.target.value)}
                className={INPUT_CLASS}
              />
              <input
                type="number"
                placeholder={`حداکثر ${f.displayName}`}
                value={values[`${f.name}_max`] ?? ""}
                onChange={(e) => onChange(`${f.name}_max`, e.target.value)}
                className={INPUT_CLASS}
              />
            </div>
          );
        }

        if (f.dataType === "date" && RANGE_FILTERS.has(f.filterType)) {
          return (
            <div key={f.name} className="flex gap-1.5">
              <JalaliDateInput
                value={values[`${f.name}_min`] ?? ""}
                onChange={(v) => onChange(`${f.name}_min`, v)}
              />
              <JalaliDateInput
                value={values[`${f.name}_max`] ?? ""}
                onChange={(v) => onChange(`${f.name}_max`, v)}
              />
            </div>
          );
        }

        return (
          <input
            key={f.name}
            type={numeric ? "number" : "text"}
            placeholder={label}
            value={values[f.name] ?? ""}
            onChange={(e) => onChange(f.name, e.target.value)}
            className={INPUT_CLASS}
          />
        );
      })}
    </>
  );
}

export { DynamicSearchFilters };
