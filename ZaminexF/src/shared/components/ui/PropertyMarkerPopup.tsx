import React from "react";
import L from "leaflet";
import { MapPin, Maximize2, User } from "lucide-react";

export const STATUS_FA: Record<string, string> = {
  AVAILABLE: "در دسترس",
  RESERVED: "رزرو شده",
  SOLD: "فروخته شد",
  INACTIVE: "بایگانی",
};

export const STATUS_STYLE: Record<string, { color: string; bg: string; dot: string; pin: string }> = {
  AVAILABLE: { color: "text-emerald-700", bg: "bg-emerald-50 border-emerald-200", dot: "bg-emerald-500", pin: "#0BB68A" },
  RESERVED: { color: "text-amber-700", bg: "bg-amber-50 border-amber-200", dot: "bg-amber-500", pin: "#F59E0B" },
  SOLD: { color: "text-rose-700", bg: "bg-rose-50 border-rose-200", dot: "bg-rose-500", pin: "#EF4444" },
  INACTIVE: { color: "text-slate-600", bg: "bg-slate-100 border-slate-200", dot: "bg-slate-400", pin: "#94A3B8" },
};

export function statusInfo(status: string) {
  const key = String(status || "").toUpperCase();
  return (
    STATUS_STYLE[key] || {
      color: "text-slate-600",
      bg: "bg-slate-100 border-slate-200",
      dot: "bg-slate-400",
      pin: "#64748B",
    }
  );
}

export function makePinIcon(color: string) {
  return L.divIcon({
    className: "zaminex-map-pin",
    html: `<div style="position:relative;width:34px;height:40px;filter:drop-shadow(0 4px 6px rgba(0,0,0,0.18));">
             <svg width="34" height="40" viewBox="0 0 32 40" fill="none" xmlns="http://www.w3.org/2000/svg">
               <path d="M16 1C8.3 1 2 7.1 2 14.7c0 8.7 12.2 22.7 13.1 23.7a1.4 1.4 0 0 0 1.8 0C17.8 37.4 30 23.4 30 14.7 30 7.1 23.7 1 16 1Z" fill="${color}"/>
               <circle cx="16" cy="15" r="6" fill="#fff"/>
             </svg>
           </div>`,
    iconSize: [34, 40],
    iconAnchor: [17, 38],
    popupAnchor: [0, -34],
  });
}

export function PropertyMarkerPopupBody({
  title,
  consultantName,
  lat,
  lng,
  status,
  area,
}: {
  title: string;
  consultantName?: string | null;
  lat: number;
  lng: number;
  status: string;
  area: number;
}) {
  const info = statusInfo(status);
  const label = STATUS_FA[String(status || "").toUpperCase()] || "—";
  return (
    <div className="w-56 overflow-hidden rounded-xl bg-white font-sans">
      <div className="flex items-start gap-2.5 p-3">
        <div className="mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <MapPin size={17} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-bold text-foreground">{title}</p>
          {consultantName ? (
            <p className="mt-0.5 flex items-center gap-1 text-[11px] text-muted-foreground">
              <User size={10} className="flex-shrink-0" />
              <span className="truncate">{consultantName}</span>
            </p>
          ) : null}
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            {lat.toFixed(5)}, {lng.toFixed(5)}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 border-t border-border bg-secondary/40 px-3 py-2.5">
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${info.bg} ${info.color}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${info.dot}`} />
          {label}
        </span>
        <span className="ms-auto inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 text-[11px] font-semibold text-foreground shadow-sm ring-1 ring-border">
          <Maximize2 size={11} className="text-muted-foreground" />
          {Number(area || 0).toLocaleString("fa-IR")} متر
        </span>
      </div>
    </div>
  );
}
