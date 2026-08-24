import { useEffect, useState } from "react";
import { apiFetch } from "./apiClient";
import type { AttributeSchema } from "../components/ui/DynamicAttributeFields";

/**
 * Loads the reference-data catalogue (usages, property types, deal types).
 *
 * These used to be hard-coded arrays in the frontend; they are now maintained
 * by an administrator, so the forms read them at runtime.
 */
export type CatalogItem = {
  id: number;
  name: string;
  displayName: string;
  propertyUsage?: number;
  propertyUsageName?: string;
};

export type Catalog = {
  usages: CatalogItem[];
  propertyTypes: CatalogItem[];
  dealTypes: CatalogItem[];
};

export function useBasicsCatalog(csrfToken?: string) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch("/basics/api/catalog/", { method: "GET" }, csrfToken);
        if (!res.ok) throw new Error();
        const data = await res.json();
        if (!cancelled) setCatalog(data);
      } catch {
        // Non-fatal: the wizard falls back to an empty option list and the
        // required-field validation still prevents an incomplete submission.
        if (!cancelled) setCatalog(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [csrfToken]);

  return { catalog, loading };
}

/**
 * Loads the custom fields configured for one property type or deal type.
 *
 * Passing a falsy id clears the schema, so switching back to "no type
 * selected" removes the dynamic section instead of leaving stale fields on
 * screen.
 */
export function useAttributeSchema(
  kind: "property" | "listing",
  typeId: string | number | null | undefined,
  csrfToken?: string
) {
  const [schema, setSchema] = useState<AttributeSchema | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!typeId) {
      setSchema(null);
      return;
    }

    let cancelled = false;
    const controller = new AbortController();
    setLoading(true);

    const param = kind === "property" ? "propertyType" : "dealType";
    const path =
      kind === "property"
        ? `/basics/api/schema/property-form/?${param}=${typeId}`
        : `/basics/api/schema/listing-form/?${param}=${typeId}`;

    (async () => {
      try {
        const res = await apiFetch(path, { method: "GET", signal: controller.signal }, csrfToken);
        if (!res.ok) throw new Error();
        const data = await res.json();
        if (!cancelled) setSchema(data);
      } catch {
        if (!cancelled) setSchema(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [kind, typeId, csrfToken]);

  return { schema, loading };
}
