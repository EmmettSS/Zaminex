import React, { useEffect } from "react";
import { MapContainer, TileLayer, Marker, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapPin } from "lucide-react";

const pinIcon = L.divIcon({
  className: "zaminex-map-pin",
  html: `<div style="display:flex;align-items:center;justify-content:center;width:32px;height:32px;">
           <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#0BB68A" stroke-width="2.2">
             <path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/>
             <circle cx="12" cy="10" r="3" fill="#fff" stroke="#0BB68A"/>
           </svg>
         </div>`,
  iconSize: [32, 32],
  iconAnchor: [16, 30],
});

function FitMapSize() {
  const map = useMap();
  useEffect(() => {
    const id = window.setTimeout(() => map.invalidateSize(), 40);
    return () => window.clearTimeout(id);
  }, [map]);
  return null;
}

function isValidCoord(n: number) {
  return Number.isFinite(n);
}

/** Read-only map of a saved property pin. Zoom only — no click-to-place. */
function PropertyLocationMap({ latitude, longitude }: { latitude: number; longitude: number }) {
  const lat = Number(latitude);
  const lng = Number(longitude);
  if (!isValidCoord(lat) || !isValidCoord(lng)) return null;
  const position: [number, number] = [lat, lng];

  return (
    <div className="space-y-2">
      <div className="isolate relative h-64 rounded-2xl overflow-hidden border border-border">
        <MapContainer
          key={`${lat.toFixed(6)},${lng.toFixed(6)}`}
          center={position}
          zoom={15}
          scrollWheelZoom
          dragging={false}
          doubleClickZoom
          touchZoom
          boxZoom={false}
          keyboard={false}
          className="zaminex-map-picker zaminex-map-readonly"
          style={{ height: "100%", width: "100%", cursor: "default" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitMapSize />
          <Marker position={position} icon={pinIcon} interactive={false} keyboard={false} />
        </MapContainer>
        <div className="pointer-events-none absolute bottom-2 left-2 bg-white/95 backdrop-blur rounded-lg px-2.5 py-1.5 text-[11px] text-muted-foreground shadow-sm font-mono">
          {lat.toFixed(6)}, {lng.toFixed(6)}
        </div>
        <div className="pointer-events-none absolute top-2 right-2 bg-white/95 rounded-lg px-2 py-1 text-[11px] text-emerald-700 font-semibold flex items-center gap-1 shadow-sm">
          <MapPin size={11} />موقعیت ثبت شد
        </div>
      </div>
      <div className="flex flex-wrap gap-3 text-[11px] text-muted-foreground">
        <span>فقط نمایش موقعیت ثبت‌شده</span>
        <span>·</span>
        <span>دکمه‌های + و − برای زوم</span>
        <span>·</span>
        <span>اسکرول ماوس / پینچ لمسی برای زوم</span>
      </div>
    </div>
  );
}

export { PropertyLocationMap };
