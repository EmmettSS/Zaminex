import React from "react";
import { createRoot } from "react-dom/client";
import "../styles/index.css";
import { ListingsPage } from "../features/listings/pages/ListingsPage";

type ListingItem = {
  id: string;
  propertyId?: string | null;
  property: string;
  channels: string[];
  status: string;
  publishedAt?: string | null;
  expires?: string | null;
  views: number;
  score?: number | null;
  consultant?: string | null;
  consultantId?: string | null;
  title?: string | null;
  priority?: string | number | null;
  featured?: boolean;
  createdBy?: string | null;
  assignedTo?: string | null;
};

type BackendListing = {
  id?: number | string;
  title?: string | null;
  status?: string | null;
  priority?: number | string | null;
  property_title?: string | null;
  propertyId?: string | null;
  channels?: unknown;
  created_by?: string | null;
  assigned_to?: string | null;
  views?: number | null;
  consultant?: string | null;
  consultantId?: string | null;
  score?: number | null;
  publishedAt?: string | null;
  expires?: string | null;
  featured?: boolean | null;
};

function safeParseJson(id: string): unknown | null {
  const el = document.getElementById(id);
  if (!el) return null;
  try {
    return JSON.parse(el.textContent ?? "null");
  } catch {
    return null;
  }
}

function normalizeBackendListing(b: BackendListing): ListingItem {
  const id = b.id !== undefined && b.id !== null ? String(b.id) : "";
  const property = b.property_title ?? b.title ?? `Listing ${id}`;
  const channels = Array.isArray(b.channels) ? b.channels.filter((c): c is string => typeof c === "string") : [];
  const status = b.status ?? "Draft";
  const views = typeof b.views === "number" ? b.views : 0;
  const item: ListingItem = {
    id,
    propertyId: b.propertyId ?? undefined,
    property,
    channels,
    status,
    publishedAt: b.publishedAt ?? null,
    expires: b.expires ?? null,
    views,
    score: b.score ?? null,
    consultant: b.consultant ?? null,
    consultantId: b.consultantId ?? null,
    title: b.title ?? null,
    priority: b.priority ?? null,
    featured: b.featured ?? false,
    createdBy: b.created_by ?? null,
    assignedTo: b.assigned_to ?? null,
  };
  return item;
}

document.addEventListener("DOMContentLoaded", () => {
  const mount = document.getElementById("listing-list-root");
  if (!mount) return;

  const raw = safeParseJson("listing-props") as { current_user?: { id?: number | string; username?: string; role?: string } | undefined; initial_listings?: BackendListing[] } | null;
  const backendListings = Array.isArray(raw?.initial_listings) ? raw!.initial_listings : [];
  const initialListings: ListingItem[] = backendListings.map(normalizeBackendListing);

  const role = raw?.current_user && raw.current_user.role ? (String(raw.current_user.role).toUpperCase() === "ADMIN" ? "admin" : "consultant") : undefined;

  const navigate = (target: string) => {
    if (!target) return;
    const detailMatch = target.match(/[?&]id=([^&]+)/);
    if (target.startsWith("listing-detail") && detailMatch && detailMatch[1]) {
      window.location.href = `/listings/${encodeURIComponent(detailMatch[1])}/`;
      return;
    }
    if (target.startsWith("edit-listing") && detailMatch && detailMatch[1]) {
      window.location.href = `/listings/${encodeURIComponent(detailMatch[1])}/edit/`;
      return;
    }
    if (target === "create-listing") {
      window.location.href = `/listings/create/`;
      return;
    }
    window.location.href = `/listings/`;
  };

  createRoot(mount).render(
    <ListingsPage
      navigate={navigate as any}
      role={role as any}
      currentConsultantId={undefined}
      consultants={[]}
      properties={[]}
      listings={initialListings as any}
      onAction={() => {}}
      loading={false}
    />
  );
});
