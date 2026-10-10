import React, { useMemo } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { MapPin } from "lucide-react";
import { DEFAULT_VIEW_CENTER, DEFAULT_VIEW_ZOOM } from "../../../shared/lib/iranLocations";
import {
  STATUS_FA,
  makePinIcon,
  statusInfo,
  PropertyMarkerPopupBody,
} from "../../../shared/components/ui/PropertyMarkerPopup";

type MapPoint = {
  id: number;
  title: string;
  lat: number;
  lng: number;
  status: string;
  area: number;
};

function FitMapSize() {
  const map = useMap();
  React.useEffect(() => {
    const id = window.setTimeout(() => map.invalidateSize(), 60);
    return () => window.clearTimeout(id);
  }, [map]);
  return null;
}

function PropertyLocationsMap({ points }: { points: MapPoint[] }) {
  const center: [number, number] = useMemo(() => {
    if (points.length === 1) return [points[0].lat, points[0].lng];
    if (points.length > 1) {
      const lat = points.reduce((s, p) => s + p.lat, 0) / points.length;
      const lng = points.reduce((s, p) => s + p.lng, 0) / points.length;
      return [lat, lng];
    }
    return DEFAULT_VIEW_CENTER;
  }, [points]);

  const zoom = points.length === 1 ? 13 : points.length > 1 ? 8 : DEFAULT_VIEW_ZOOM;

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
          {points.map((p) => (
            <Marker key={p.id} position={[p.lat, p.lng]} icon={makePinIcon(statusInfo(p.status).pin)}>
              <Popup closeButton={false} maxWidth={260} minWidth={220} className="zaminex-popup">
                <PropertyMarkerPopupBody
                  title={p.title}
                  lat={p.lat}
                  lng={p.lng}
                  status={p.status}
                  area={p.area}
                />
              </Popup>
            </Marker>
          ))}
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
