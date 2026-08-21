import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { fuzzyFilter } from "../../../shared/lib/fuzzySearch";
import { Page, Role, Property, Listing, FollowUp, ConsultantItem, BadgeV, FollowUpCreatePayload } from "../../../shared/lib/types";
import { fmtShort, toPersianType, toPersianDeal, toPersianPropertyStatus, toPersianTaskStatus, toPersianTaskType, toPersianPriority, toPersianChannel, propertyStatusToUI, toPersianFollowupType, toPersianListingStatus } from "../../../shared/lib/utils";
import { Badge } from "../../../shared/components/ui/Badge";
import { Btn } from "../../../shared/components/ui/Btn";
import { Input } from "../../../shared/components/ui/Input";
import { Card } from "../../../shared/components/ui/Card";
import { SelectField } from "../../../shared/components/ui/SelectField";
import { ProfileAvatar } from "../../../shared/components/ui/ProfileAvatar";
import { KpiCard } from "../../../shared/components/ui/KpiCard";
import { EmptyState } from "../../../shared/components/ui/EmptyState";
import { PageHeader } from "../../../shared/components/ui/PageHeader";
import { ConfirmModal } from "../../../shared/components/ConfirmModal";
import { Pagination } from "../../../shared/components/Pagination";
import { DistrictCombobox } from "../../../shared/components/ui/DistrictCombobox";
import { apiFetch, readJson, apiErrorMessage, getCsrfToken } from "../../../shared/lib/apiClient";
import { toast } from "../../../shared/lib/utils";
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, MessageSquare, Sparkles, GripVertical, MoreVertical, Building, History, Flame, Image, Filter } from "lucide-react";
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, ReferenceLine, ScatterChart, Scatter, ZAxis, RadialBarChart, RadialBar } from "recharts";

// =============================================================================
//  Regions: Province → City → District
//
//  A single screen for the whole geography. The three levels share one layout
//  (add box + list card) and are switched by a tab strip, so the page keeps the
//  structure it had when it managed a flat district list.
//
//  Nothing is seeded: the agency defines its own coverage area.
// =============================================================================

type LevelKey = "province" | "city" | "district";

type Row = {
  id: number;
  name: string;
  displayName: string;
  isActive: boolean;
  province?: number;
  provinceName?: string;
  city?: number;
  cityName?: string;
  fullPath?: string;
  cityCount?: number;
  districtCount?: number;
  propertyCount?: number;
};

const ENDPOINT: Record<LevelKey, string> = {
  province: "/basics/api/provinces/",
  city: "/basics/api/cities/",
  district: "/basics/api/districts/",
};

const LABELS: Record<LevelKey, { tab: string; one: string; add: string; list: string; empty: string }> = {
  province: { tab: "استان‌ها", one: "استان", add: "افزودن استان جدید", list: "لیست استان‌ها", empty: "هنوز استانی ثبت نشده است." },
  city: { tab: "شهرها", one: "شهر", add: "افزودن شهر جدید", list: "لیست شهرها", empty: "هنوز شهری ثبت نشده است." },
  district: { tab: "محله‌ها", one: "محله", add: "افزودن محله جدید", list: "لیست محله‌ها", empty: "هنوز محله‌ای ثبت نشده است." },
};

function DistrictsPage({ csrfToken, onDistrictsChanged }: { csrfToken: string; onDistrictsChanged: () => void }) {
  const [level, setLevel] = useState<LevelKey>("province");
  const [rows, setRows] = useState<Row[]>([]);
  const [provinces, setProvinces] = useState<Row[]>([]);
  const [cities, setCities] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [newName, setNewName] = useState("");
  const [newParent, setNewParent] = useState("");
  const [adding, setAdding] = useState(false);

  // A city needs a province, a district needs a city. Both parent lists are
  // kept loaded so the "add" box can offer them whatever tab is open.
  const fetchParents = useCallback(async () => {
    try {
      // `cache: "no-store"` keeps these authenticated GETs fresh: a province or
      // city added a moment ago must appear immediately, never a cached copy.
      const [pRes, cRes] = await Promise.all([
        apiFetch("/basics/api/provinces/?all=1", { method: "GET", cache: "no-store" }, csrfToken),
        apiFetch("/basics/api/cities/?all=1", { method: "GET", cache: "no-store" }, csrfToken),
      ]);
      if (pRes.ok) setProvinces(await pRes.json());
      if (cRes.ok) setCities(await cRes.json());
    } catch {
      // Non-fatal: the parent dropdown renders empty and the add button stays
      // disabled, which is the correct outcome when the list cannot be loaded.
    }
  }, [csrfToken]);

  const fetchRows = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch(`${ENDPOINT[level]}?all=1`, { method: "GET", cache: "no-store" }, csrfToken);
      if (res.ok) setRows(await res.json());
    } catch (err) {
      console.error("Error fetching regions:", err);
    } finally {
      setLoading(false);
    }
  }, [csrfToken, level]);

  useEffect(() => { fetchRows(); }, [fetchRows]);
  useEffect(() => { fetchParents(); }, [fetchParents]);

  // Switching tabs resets the add box so a half-typed entry cannot be
  // submitted against the wrong level.
  useEffect(() => { setNewName(""); setNewParent(""); setSearch(""); }, [level]);

  const parentOptions = useMemo(() => {
    if (level === "city") {
      return provinces.map((p) => ({ label: p.displayName, value: String(p.id) }));
    }
    if (level === "district") {
      return cities.map((c) => ({
        label: c.provinceName ? `${c.provinceName} / ${c.displayName}` : c.displayName,
        value: String(c.id),
      }));
    }
    return [];
  }, [level, provinces, cities]);

  const needsParent = level !== "province";
  const canAdd = !!newName.trim() && (!needsParent || !!newParent);

  const refreshAll = async () => {
    await Promise.all([fetchRows(), fetchParents()]);
    onDistrictsChanged();
  };

  const handleAdd = async () => {
    if (!canAdd) return;
    // A city/district cannot exist without its parent. `canAdd` already guards
    // this, but resolve the id here so a request can never go out without the
    // parent field (which the API rejects with a generic "این مقدار لازم است").
    const parentId = Number(newParent);
    if (needsParent && (!Number.isFinite(parentId) || parentId <= 0)) {
      toast({
        type: "error",
        message: level === "city" ? "انتخاب استان الزامی است." : "انتخاب شهر الزامی است.",
      });
      return;
    }

    setAdding(true);
    try {
      const body: Record<string, any> = { displayName: newName.trim() };
      if (level === "city") body.province = parentId;
      if (level === "district") body.city = parentId;

      const res = await apiFetch(ENDPOINT[level], { method: "POST", body: JSON.stringify(body) }, csrfToken);
      // `readJson` tolerates an empty body and a non-JSON error page (a CSRF
      // rejection is served as HTML), so a failed parse can no longer be
      // mistaken for a failed request.
      const data = await readJson(res).catch(() => null);

      if (res.ok) {
        toast({ type: "success", message: `${LABELS[level].one} با موفقیت اضافه شد.` });
        setNewName("");
        // Reflect the new row immediately (and keep the parent dropdowns in
        // sync) instead of waiting for the follow-up refetch to round-trip.
        // The refetch below then replaces this with the authoritative list.
        if (data && data.id) {
          setRows((prev) => [data, ...prev]);
          if (level === "province") setProvinces((prev) => [data, ...prev]);
          if (level === "city") setCities((prev) => [data, ...prev]);
        }
        await refreshAll();
      } else {
        // A city/district failure is usually reported against its parent key
        // (`province` / `city`), which the previous displayName-only lookup
        // dropped — leaving the operator with a generic "خطا در اضافه کردن
        // شهر" and no way to tell a missing parent from a duplicate name.
        // `apiErrorMessage` walks the whole payload, so every field error
        // reaches the toast whatever key the server used.
        toast({
          type: "error",
          message: apiErrorMessage(data, `خطا در اضافه کردن ${LABELS[level].one}`),
        });
      }
    } catch {
      toast({ type: "error", message: "خطا در ارتباط با سرور" });
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (row: Row) => {
    if (!confirm(`آیا از حذف ${LABELS[level].one} «${row.displayName}» مطمئن هستید؟`)) return;
    try {
      const res = await apiFetch(`${ENDPOINT[level]}${row.id}/`, { method: "DELETE" }, csrfToken);
      if (res.ok || res.status === 204) {
        toast({ type: "success", message: `${LABELS[level].one} با موفقیت حذف شد.` });
        await refreshAll();
      } else {
        // The server explains *why* a delete is refused ("این استان دارای شهر
        // فعال است…", "۳ ملک در این محله ثبت شده است…"); surface that instead
        // of a generic message the operator cannot act on.
        const data = await readJson(res).catch(() => null);
        toast({
          type: "error",
          message: apiErrorMessage(data, `خطا در حذف ${LABELS[level].one}`),
        });
      }
    } catch {
      toast({ type: "error", message: "خطا در ارتباط با سرور" });
    }
  };

  const handleToggleActive = async (row: Row) => {
    try {
      const res = await apiFetch(
        `${ENDPOINT[level]}${row.id}/`,
        { method: "PATCH", body: JSON.stringify({ isActive: !row.isActive }) },
        csrfToken
      );
      if (res.ok) {
        toast({ type: "success", message: row.isActive ? `${LABELS[level].one} غیرفعال شد.` : `${LABELS[level].one} فعال شد.` });
        await refreshAll();
      } else {
        // Without this branch a rejected toggle looked like a no-op: the row
        // silently snapped back on the next refresh with nothing explaining why.
        const data = await readJson(res).catch(() => null);
        toast({
          type: "error",
          message: apiErrorMessage(
            data,
            `خطا در تغییر وضعیت ${LABELS[level].one}`
          ),
        });
      }
    } catch {
      toast({ type: "error", message: "خطا در ارتباط با سرور" });
    }
  };

  const filtered = useMemo(() => {
    return fuzzyFilter(rows, search, (r) => `${r.displayName} ${r.provinceName ?? ""} ${r.cityName ?? ""}`);
  }, [rows, search]);

  /** Secondary line under each row: its parent, and what depends on it. */
  const subtitleFor = (row: Row) => {
    if (level === "province") {
      return `${(row.cityCount ?? 0).toLocaleString("fa-IR")} شهر`;
    }
    if (level === "city") {
      return `${row.provinceName ?? "—"} · ${(row.districtCount ?? 0).toLocaleString("fa-IR")} محله`;
    }
    const where = row.provinceName && row.cityName ? `${row.provinceName} / ${row.cityName}` : row.cityName ?? "—";
    return `${where} · ${(row.propertyCount ?? 0).toLocaleString("fa-IR")} ملک`;
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">
      <PageHeader title="مدیریت مناطق" subtitle="تعریف استان، شهر و محله‌های قابل استفاده در املاک" />

      {/* Level tabs */}
      <div className="flex items-center gap-1 p-1 bg-secondary rounded-xl w-fit">
        {(Object.keys(LABELS) as LevelKey[]).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setLevel(key)}
            className={cx(
              "px-4 py-2 text-xs font-medium rounded-lg transition-colors",
              level === key ? "bg-white text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            )}
          >
            {LABELS[key].tab}
          </button>
        ))}
      </div>

      {/* Add new */}
      <Card className="p-5">
        <h3 className="text-sm font-semibold mb-3">{LABELS[level].add}</h3>
        <div className="flex gap-3 items-end">
          {needsParent && (
            <div className="w-56">
              <SelectField
                label={level === "city" ? "استان" : "شهر"}
                value={newParent}
                onChange={setNewParent}
                options={parentOptions}
                placeholder={level === "city" ? "انتخاب استان" : "انتخاب شهر"}
              />
            </div>
          )}
          <div className="flex-1">
            <Input
              label={`نام ${LABELS[level].one}`}
              placeholder={`نام ${LABELS[level].one} را وارد کنید...`}
              value={newName}
              onChange={setNewName}
            />
          </div>
          <Btn variant="primary" onClick={handleAdd} disabled={adding || !canAdd}>
            {adding ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
            افزودن
          </Btn>
        </div>
        {needsParent && parentOptions.length === 0 && (
          <p className="text-xs text-muted-foreground mt-2.5">
            {level === "city" ? "ابتدا یک استان تعریف کنید." : "ابتدا یک شهر تعریف کنید."}
          </p>
        )}
      </Card>

      {/* List */}
      <Card className="overflow-hidden">
        <div className="px-5 py-3.5 border-b border-border bg-secondary/30">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold">{LABELS[level].list} ({filtered.length.toLocaleString("fa-IR")})</h3>
            <div className="relative max-w-xs">
              <Search size={12} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={`جستجوی ${LABELS[level].one}...`}
                className="w-full pl-3 pr-8 py-2 text-xs rounded-xl border border-border bg-white outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
        </div>

        {loading ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            <Loader2 size={24} className="animate-spin mx-auto mb-3 text-primary" />
            در حال بارگذاری...
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<MapPin size={28} />}
            title={`${LABELS[level].one}ای یافت نشد`}
            description={search ? "با عبارت جستجوی شما موردی پیدا نشد." : LABELS[level].empty}
          />
        ) : (
          <div className="divide-y divide-border">
            {filtered.map((row) => (
              <div key={row.id} className="flex items-center justify-between gap-3 px-5 py-3.5 hover:bg-secondary/20 transition-colors">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div className={cx("w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0", row.isActive ? "bg-emerald-100 text-emerald-600" : "bg-gray-100 text-gray-400")}>
                    {level === "province" ? <Layers size={14} /> : level === "city" ? <Building size={14} /> : <MapPin size={14} />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className={cx("text-sm font-semibold truncate", !row.isActive && "text-gray-400")}>{row.displayName}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{subtitleFor(row)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <Badge label={row.isActive ? "فعال" : "غیرفعال"} variant={row.isActive ? "success" : "muted"} dot />
                  <Btn
                    variant="ghost"
                    size="xs"
                    onClick={() => handleToggleActive(row)}
                    title={row.isActive ? "غیرفعال کردن" : "فعال کردن"}
                  >
                    {row.isActive ? <Archive size={12} /> : <CheckCircle2 size={12} />}
                  </Btn>
                  <Btn
                    variant="ghost"
                    size="xs"
                    onClick={() => handleDelete(row)}
                    className="!text-red-500 hover:!bg-red-50"
                    title="حذف"
                  >
                    <Trash2 size={12} />
                  </Btn>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

// =============================================================================
//  Activity Log
// =============================================================================

export { DistrictsPage };
