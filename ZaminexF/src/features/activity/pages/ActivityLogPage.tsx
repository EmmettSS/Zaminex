import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { Page, Role, Property, Listing, FollowUp, ConsultantItem, BadgeV, FollowUpCreatePayload, ActivityLogItem } from "../../../shared/lib/types";
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
function ActivityLogPage({ csrfToken }: { csrfToken: string }) {
  const [filter, setFilter] = useState("all");
  const [items, setItems] = useState<ActivityLogItem[]>([]);
  const [summary, setSummary] = useState<{ total: number; thisWeek: number; completed: number }>({ total: 0, thisWeek: 0, completed: 0 });
  const [nextUrl, setNextUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDeleteAll, setConfirmDeleteAll] = useState(false);

  const types = ["all", "create", "update", "status_change", "complete", "approve", "reject", "export", "archive", "delete"];
  const typeLabels: Record<string, string> = { all: "همه فعالیت‌ها", create: "ایجاد", update: "بروزرسانی", status_change: "تغییر وضعیت", complete: "تکمیل", approve: "تایید", reject: "رد", export: "خروجی", archive: "بایگانی", delete: "حذف" };
  const colors: Record<string, string> = { create: "bg-emerald-100 text-emerald-600", update: "bg-blue-100 text-blue-600", status_change: "bg-purple-100 text-purple-600", complete: "bg-emerald-100 text-emerald-600", approve: "bg-teal-100 text-teal-600", reject: "bg-rose-100 text-rose-600", export: "bg-amber-100 text-amber-600", archive: "bg-red-100 text-red-600", delete: "bg-red-100 text-red-600", system: "bg-secondary text-muted-foreground" };
  const icons: Record<string, React.ReactNode> = { create: <Plus size={13} />, update: <Edit2 size={13} />, status_change: <RefreshCw size={13} />, complete: <Check size={13} />, approve: <CheckCircle2 size={13} />, reject: <XCircle size={13} />, export: <Download size={13} />, archive: <Archive size={13} />, delete: <Trash2 size={13} />, system: <Settings size={13} /> };
  const badgeVariants: Record<string, BadgeV> = { create: "success", update: "info", status_change: "purple", complete: "success", approve: "teal", reject: "danger", export: "warning", archive: "muted", delete: "danger" };

  const apiPath = useCallback((url: string) => {
    try {
      const u = new URL(url, window.location.origin);
      return u.pathname + u.search;
    } catch {
      return url;
    }
  }, []);

  const buildUrl = useCallback(
    (pageUrl?: string | null) => {
      if (pageUrl) return apiPath(pageUrl);
      const qs = new URLSearchParams({ page_size: "30" });
      if (filter !== "all") qs.set("action", filter);
      return `/common/api/activity-log/?${qs.toString()}`;
    },
    [filter, apiPath]
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(buildUrl(), { method: "GET" }, csrfToken);
      const data = await readJson(res);
      if (!res.ok) throw new Error(apiErrorMessage(data, "خطا در بارگذاری گزارش فعالیت"));
      setItems(Array.isArray(data?.results) ? data.results : []);
      setSummary({
        total: data?.summary?.total ?? data?.count ?? 0,
        thisWeek: data?.summary?.thisWeek ?? 0,
        completed: data?.summary?.completed ?? 0,
      });
      setNextUrl(data?.next || null);
    } catch (err: any) {
      setError(err?.message || "خطا در بارگذاری گزارش فعالیت");
    } finally {
      setLoading(false);
    }
  }, [buildUrl, csrfToken]);

  useEffect(() => { load(); }, [load]);

  const handleDeleteAll = async () => {
    try {
      const res = await apiFetch("/common/api/activity-log/", { method: "DELETE" }, csrfToken);
      const data = await readJson(res);
      if (!res.ok) throw new Error(apiErrorMessage(data, "خطا در حذف گزارش‌های فعالیت"));

      toast({ type: "success", message: "تمامی گزارش‌های فعالیت با موفقیت حذف شدند." });
      setItems([]);
      setSummary({ total: 0, thisWeek: 0, completed: 0 });
      setNextUrl(null);
      setConfirmDeleteAll(false);
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطا در حذف گزارش‌های فعالیت" });
    }
  };

  const loadMore = async () => {
    if (!nextUrl || loadingMore) return;
    setLoadingMore(true);
    try {
      const res = await apiFetch(buildUrl(nextUrl), { method: "GET" }, csrfToken);
      const data = await readJson(res);
      if (!res.ok) throw new Error(apiErrorMessage(data, "خطا در بارگذاری فعالیت‌های بیشتر"));
      setItems((prev) => [...prev, ...(Array.isArray(data?.results) ? data.results : [])]);
      setNextUrl(data?.next || null);
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطا در بارگذاری فعالیت‌های بیشتر" });
    } finally {
      setLoadingMore(false);
    }
  };

  const dayLabel = (iso: string) => {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "—";
    const sameDay = (a: Date, b: Date) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    if (sameDay(d, today)) return "امروز";
    if (sameDay(d, yesterday)) return "دیروز";
    return d.toLocaleDateString("fa-IR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  };

  const timeLabel = (iso: string) => {
    const d = new Date(iso);
    const diff = Date.now() - d.getTime();
    if (isNaN(d.getTime()) || diff < 0) return d.toLocaleDateString("fa-IR");
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "همین الان";
    if (mins < 60) return `${mins.toLocaleString("fa-IR")} دقیقه پیش`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs.toLocaleString("fa-IR")} ساعت پیش`;
    const days = Math.floor(hrs / 24);
    if (days < 7) return `${days.toLocaleString("fa-IR")} روز پیش`;
    return d.toLocaleDateString("fa-IR");
  };

  const groups = useMemo(() => {
    const out: { label: string; rows: ActivityLogItem[] }[] = [];
    for (const it of items) {
      const lbl = dayLabel(it.createdAt);
      const last = out[out.length - 1];
      if (last && last.label === lbl) last.rows.push(it);
      else out.push({ label: lbl, rows: [it] });
    }
    return out;
  }, [items]);

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      <PageHeader
        title="گزارش فعالیت"
        subtitle="ردیابی تمام اقدامات انجام‌شده در سیستم"
        actions={
          <Btn
            variant="danger"
            size="sm"
            onClick={() => setConfirmDeleteAll(true)}
            disabled={items.length === 0 && summary.total === 0}
          >
            <Trash2 size={13} />
            حذف همه لاگ‌ها
          </Btn>
        }
      />
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <KpiCard label="کل اقدامات" value={summary.total.toLocaleString("fa-IR")} icon={<Activity size={16} />} color="bg-primary/10 text-primary" />
        <KpiCard label="این هفته" value={summary.thisWeek.toLocaleString("fa-IR")} icon={<Calendar size={16} />} color="bg-blue-50 text-blue-600" />
        <KpiCard label="وظایف تکمیل‌شده" value={summary.completed.toLocaleString("fa-IR")} icon={<CheckCircle2 size={16} />} color="bg-emerald-50 text-emerald-600" />
      </div>
      <div className="flex gap-4">
        <div className="w-44 flex-shrink-0">
          <Card className="p-3">
            <p className="text-xs font-semibold text-muted-foreground mb-2 px-1">فیلتر بر اساس نوع</p>
            {types.map((t) => (
              <button key={t} onClick={() => setFilter(t)} className={cx("w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-right text-xs font-medium transition-colors mb-0.5", filter === t ? "bg-primary text-white" : "hover:bg-secondary text-foreground")}>
                <span>{typeLabels[t] || t}</span>
              </button>
            ))}
          </Card>
        </div>
        <div className="flex-1">
          <Card className="overflow-hidden">
            {loading ? (
              <div className="px-5 py-12 text-center text-sm text-muted-foreground">
                <Loader2 size={22} className="animate-spin mx-auto mb-3 text-primary" />
                در حال بارگذاری فعالیت‌ها…
              </div>
            ) : error ? (
              <div className="px-5 py-12 text-center">
                <p className="text-sm text-red-600 mb-3">{error}</p>
                <Btn variant="secondary" size="sm" onClick={load}><RefreshCw size={13} />تلاش مجدد</Btn>
              </div>
            ) : items.length === 0 ? (
              <EmptyState icon={<Activity size={28} />} title="فعالیتی یافت نشد" description="هنوز فعالیتی با این فیلتر در سیستم ثبت نشده است." />
            ) : (
              <>
                {groups.map((g) => (
                  <div key={g.label}>
                    <div className="px-4 py-3 border-b border-border bg-secondary/30 text-xs font-semibold text-muted-foreground">{g.label}</div>
                    <div className="divide-y divide-border">
                      {g.rows.map((act) => (
                        <div key={act.id} className="flex items-start gap-3 px-5 py-3.5 hover:bg-secondary/20 transition-colors">
                          <div className={cx("w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5", colors[act.action] || "bg-secondary text-muted-foreground")}>
                            {icons[act.action] || <Activity size={13} />}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium text-foreground leading-relaxed">{act.description}</p>
                            <p className="text-[11px] text-muted-foreground mt-1">{act.userName} · {act.targetTypeLabel} · {timeLabel(act.createdAt)}</p>
                          </div>
                          <Badge label={act.actionLabel} variant={badgeVariants[act.action] || "default"} />
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
                {nextUrl && (
                  <div className="px-5 py-3.5 border-t border-border text-center">
                    <Btn variant="secondary" size="sm" onClick={loadMore} disabled={loadingMore}>
                      {loadingMore ? <Loader2 size={13} className="animate-spin" /> : <ChevronDown size={13} />}
                      {loadingMore ? "در حال بارگذاری…" : "نمایش موارد بیشتر"}
                    </Btn>
                  </div>
                )}
              </>
            )}
          </Card>
        </div>
      </div>
      <ConfirmModal
        open={confirmDeleteAll}
        danger
        title="حذف تمامی لاگ‌های فعالیت؟"
        message="آیا از حذف تمامی گزارش‌ها و لاگ‌های فعالیت اطمینان دارید؟ تمام سوابق پاک خواهند شد و قابل بازیابی نیستند."
        onConfirm={handleDeleteAll}
        onCancel={() => setConfirmDeleteAll(false)}
      />
    </div>
  );
}

// =============================================================================
//  Settings
// =============================================================================

export { ActivityLogPage };
