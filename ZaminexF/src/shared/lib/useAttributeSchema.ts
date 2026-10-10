import { useEffect, useState } from "react";
import { apiFetch } from "./apiClient";
import type { AttributeSchema } from "../components/ui/DynamicAttributeFields";

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
