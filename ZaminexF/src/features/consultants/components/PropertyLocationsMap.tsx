import React, { useMemo } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapPin, Maximize2 } from "lucide-react";
import { IRAN_DEFAULT_CENTER } from "../../../shared/lib/iranLocations";

type MapPoint = {
  id: number;
  title: string;
  lat: number;
  lng: number;
  status: string;
  area: number;
};

const STATUS_FA: Record<string, string> = {
  AVAILABLE: "در دسترس",
  RESERVED: "رزرو شده",
  SOLD: "فروخته شد",
  INACTIVE: "بایگانی",
};

const STATUS_STYLE: Record<string, { color: string; bg: string; dot: string; pin: string }> = {
  AVAILABLE: { color: "text-emerald-700", bg: "bg-emerald-50 border-emerald-200", dot: "bg-emerald-500", pin: "#0BB68A" },
  RESERVED: { color: "text-amber-700", bg: "bg-amber-50 border-amber-200", dot: "bg-amber-500", pin: "#F59E0B" },
  SOLD: { color: "text-rose-700", bg: "bg-rose-50 border-rose-200", dot: "bg-rose-500", pin: "#EF4444" },
  INACTIVE: { color: "text-slate-600", bg: "bg-slate-100 border-slate-200", dot: "bg-slate-400", pin: "#94A3B8" },
};

function statusInfo(status: string) {
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

function makeIcon(status: string) {
  const color = statusInfo(status).pin;
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

function FitMapSize() {
  const map = useMap();
  // Leaflet can render with stale tile sizes inside flex/RTL containers until
  // the next animation frame; force a measurement once the map is mounted.
  React.useEffect(() => {
    const id = window.setTimeout(() => map.invalidateSize(), 60);
    return () => window.clearTimeout(id);
  }, [map]);
  return null;
}

/** Read-only map showing all of a consultant's located properties. */
function PropertyLocationsMap({ points }: { points: MapPoint[] }) {
  const center: [number, number] = useMemo(() => {
    if (points.length === 1) return [points[0].lat, points[0].lng];
    if (points.length > 1) {
      const lat = points.reduce((s, p) => s + p.lat, 0) / points.length;
      const lng = points.reduce((s, p) => s + p.lng, 0) / points.length;
      return [lat, lng];
    }
    return IRAN_DEFAULT_CENTER;
  }, [points]);

  const zoom = points.length === 1 ? 13 : points.length > 1 ? 8 : 5;

  return (
    <div className="space-y-2">
      <div className="isolate relative h-64 rounded-2xl overflow-hidden border border-border">
        <MapContainer
          center={center}
          zoom={zoom}
          scrollWheelZoom
          dragging
          doubleClickZoom
          touchZoom
          className="zaminex-map-picker zaminex-map-readonly"
          style={{ height: "100%", width: "100%", cursor: "grab" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitMapSize />
          {points.map((p) => {
            const info = statusInfo(p.status);
            const label = STATUS_FA[String(p.status || "").toUpperCase()] || "—";
            return (
              <Marker key={p.id} position={[p.lat, p.lng]} icon={makeIcon(p.status)}>
                <Popup closeButton={false} maxWidth={260} minWidth={220} className="zaminex-popup">
                  <div className="w-56 overflow-hidden rounded-xl bg-white font-sans">
                    <div className="flex items-start gap-2.5 p-3">
                      <div className="mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                        <MapPin size={17} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-bold text-foreground">{p.title}</p>
                        <p className="mt-0.5 text-[11px] text-muted-foreground">
                          {p.lat.toFixed(5)}, {p.lng.toFixed(5)}
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
                        {Number(p.area || 0).toLocaleString("fa-IR")} متر
                      </span>
                    </div>
                  </div>
                </Popup>
              </Marker>
            );
          })}
        </MapContainer>
        <div className="pointer-events-none absolute bottom-2 left-2 bg-white/95 backdrop-blur rounded-lg px-2.5 py-1.5 text-[11px] text-muted-foreground shadow-sm font-mono">
          {points.length.toLocaleString("fa-IR")} موقعیت ثبت‌شده
        </div>
        <div className="pointer-events-none absolute top-2 right-2 bg-white/95 rounded-lg px-2 py-1 text-[11px] text-emerald-700 font-semibold flex items-center gap-1 shadow-sm">
          <MapPin size={11} />نقشهٔ املاک مشاور
        </div>
      </div>
      <div className="flex flex-wrap gap-3 text-[11px] text-muted-foreground">
        <span>کلیک روی هر پین برای دیدن اطلاعات ملک</span>
        <span>·</span>
        <span>دکمه‌های + و − برای زوم</span>
        <span>·</span>
        <span>اسکرول ماوس / پینچ لمسی برای زوم</span>
      </div>
    </div>
  );
}

export { PropertyLocationsMap };
