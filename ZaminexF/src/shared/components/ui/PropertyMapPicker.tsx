import React, { useEffect, useRef, useState } from "react";
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Search, Crosshair, MapPin, Loader2 } from "lucide-react";
import {
  IRAN_DEFAULT_CENTER,
  IRAN_DEFAULT_ZOOM,
  IRAN_PROVINCE_CENTERS,
  resolvePlaceCoordinates,
  type LatLng,
} from "../../lib/iranLocations";

// Leaflet's default marker icons don't resolve from bundlers; build one inline.
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

function roundCoord(n: number): number {
  // Backend DecimalField(max_digits=9, decimal_places=6) rejects raw Leaflet
  // floats (13+ digits) with a confusing "no more than 9 digits" error.
  return Number(n.toFixed(6));
}

/** Leaflet tiles and click coords drift inside RTL documents until the size is known. */
function FitMapSize() {
  const map = useMap();
  useEffect(() => {
    const id = window.setTimeout(() => map.invalidateSize(), 40);
    return () => window.clearTimeout(id);
  }, [map]);
  return null;
}

/** Click the map or drag the pin to choose / change the property location. */
function ClickPicker({
  value,
  onChange,
}: {
  value: LatLng | null;
  onChange: (p: LatLng) => void;
}) {
  useMapEvents({
    click(e) {
      onChange([roundCoord(e.latlng.lat), roundCoord(e.latlng.lng)]);
    },
  });
  if (!value) return null;
  return (
    <Marker
      position={value}
      icon={pinIcon}
      draggable
      eventHandlers={{
        dragend(e) {
          const p = e.target.getLatLng();
          onChange([roundCoord(p.lat), roundCoord(p.lng)]);
        },
      }}
    />
  );
}

/** Flying the camera to the resolved coordinates (province → city → district). */
function FlyToLocation({
  location,
  zoom,
}: {
  location: LatLng | null;
  zoom: number;
}) {
  const map = useMap();
  useEffect(() => {
    if (location) map.flyTo(location, zoom, { duration: 0.8 });
  }, [map, location, zoom]);
  return null;
}

function PropertyMapPicker({
  value,
  onChange,
  provinceName,
  cityName,
  districtName,
}: {
  value: LatLng | null;
  onChange: (p: LatLng) => void;
  provinceName?: string;
  cityName?: string;
  districtName?: string;
}) {
  const [q, setQ] = useState("");
  const [searching, setSearching] = useState(false);
  const [focusTarget, setFocusTarget] = useState<{ location: LatLng; zoom: number } | null>(null);
  const [searchNoResult, setSearchNoResult] = useState(false);
  const noResultTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // On edit the pin is already saved. Do not fly to the district centre on
  // first hydrate — that used to yank the camera off the real marker.
  const skipInitialFly = useRef(Boolean(value));
  const didHydrateLocation = useRef(false);

  // Clear the pending "no result" timer on unmount so we never update state
  // on an unmounted component.
  useEffect(() => {
    return () => {
      if (noResultTimer.current) clearTimeout(noResultTimer.current);
    };
  }, []);

  // When a province / city / district changes, resolve and fly there.
  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      const name = districtName || cityName || provinceName || "";

      if (!didHydrateLocation.current) {
        // Edit form: district labels arrive after the location tree loads.
        if (!name && skipInitialFly.current) return;
        didHydrateLocation.current = true;
        if (skipInitialFly.current) return;
      }

      if (!name) {
        if (!value) setFocusTarget({ location: IRAN_DEFAULT_CENTER, zoom: IRAN_DEFAULT_ZOOM });
        return;
      }
      const kind = districtName ? "district" : cityName ? "city" : "province";
      const resolved = await resolvePlaceCoordinates(name, kind, { provinceName, cityName });
      if (cancelled) return;
      if (resolved) {
        const zoom = districtName ? 15 : cityName ? 12 : 8;
        setFocusTarget({ location: resolved, zoom });
      } else if (!value && provinceName) {
        // fallback to the province centre when a district/city lookup fails
        const p = IRAN_PROVINCE_CENTERS[provinceName];
        if (p) setFocusTarget({ location: p, zoom: 9 });
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [provinceName, cityName, districtName]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = async () => {
    if (!q.trim()) return;
    if (noResultTimer.current) clearTimeout(noResultTimer.current);
    setSearchNoResult(false);
    setSearching(true);
    try {
      const resolved = await resolvePlaceCoordinates(q.trim(), "district");
      if (resolved) {
        setFocusTarget({ location: resolved, zoom: 15 });
        setQ("");
      } else {
        // No match found: show a short notice over the map, then auto-dismiss.
        setSearchNoResult(true);
        noResultTimer.current = setTimeout(() => setSearchNoResult(false), 7000);
      }
    } finally {
      setSearching(false);
    }
  };

  const center = value ?? focusTarget?.location ?? IRAN_DEFAULT_CENTER;
  const zoom = focusTarget?.zoom ?? (value ? 15 : IRAN_DEFAULT_ZOOM);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search size={13} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="جستجوی مکان (محله، شهر، آدرس)…"
            className="w-full pr-8 pl-3 py-2 text-sm rounded-xl border border-border bg-input-background outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <button
          type="button"
          onClick={handleSearch}
          disabled={searching}
          className="px-3 py-2 rounded-xl bg-primary text-white text-sm flex items-center gap-1.5 hover:opacity-90 transition-opacity"
        >
          {searching ? <Loader2 size={13} className="animate-spin" /> : <Crosshair size={13} />}یافتن
        </button>
      </div>
      <p className="text-[11px] text-muted-foreground/80">برای جستجوی مکان به اتصال اینترنت نیاز است.</p>

      <div className="isolate relative h-64 rounded-2xl overflow-hidden border border-border">
        <MapContainer
          center={center}
          zoom={zoom}
          scrollWheelZoom
          dragging
          doubleClickZoom
          touchZoom
          className="zaminex-map-picker"
          style={{ height: "100%", width: "100%", cursor: "crosshair" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitMapSize />
          <ClickPicker value={value} onChange={onChange} />
          <FlyToLocation location={focusTarget?.location ?? null} zoom={focusTarget?.zoom ?? zoom} />
        </MapContainer>
        <div className="pointer-events-none absolute bottom-2 left-2 bg-white/95 backdrop-blur rounded-lg px-2.5 py-1.5 text-[11px] text-muted-foreground shadow-sm font-mono">
          {value ? `${value[0].toFixed(6)}, ${value[1].toFixed(6)}` : "برای ثبت موقعیت روی نقشه کلیک کنید"}
        </div>
        {value && (
          <div className="pointer-events-none absolute top-2 right-2 bg-white/95 rounded-lg px-2 py-1 text-[11px] text-emerald-700 font-semibold flex items-center gap-1 shadow-sm">
            <MapPin size={11} />موقعیت ثبت شد
          </div>
        )}
        {searchNoResult && (
          <div className="absolute inset-0 z-[1001] flex items-center justify-center pointer-events-none">
            <div className="bg-white/95 backdrop-blur rounded-lg px-3 py-1.5 text-xs text-destructive shadow-sm border border-border">
              نتیجه‌ای یافت نشد
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-3 text-[11px] text-muted-foreground">
        <span>کلیک روی نقشه برای انتخاب نقطه</span>
        <span>·</span>
        <span>کشیدن پین برای جابه‌جایی دقیق</span>
        <span>·</span>
        <span>دکمه‌های + و − برای زوم</span>
        <span>·</span>
        <span>کشیدن نقشه برای جابه‌جایی</span>
      </div>
    </div>
  );
}

export { PropertyMapPicker };
