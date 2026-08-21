import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { Page, Role, Property, Listing, FollowUp, ConsultantItem, BadgeV, PropertyReportPayload } from "../../../shared/lib/types";
import { fmtShort, toPersianType, toPersianDeal, toPersianPropertyStatus, toPersianTaskStatus, toPersianTaskType, toPersianPriority, toPersianChannel, propertyStatusToUI, toPersianFollowupType, formatPriceDeviation, delegationLabel } from "../../../shared/lib/utils";
import { Badge } from "../../../shared/components/ui/Badge";
import { Btn } from "../../../shared/components/ui/Btn";
import { Input } from "../../../shared/components/ui/Input";
import { JalaliDateInput } from "../../../shared/components/ui/JalaliDateInput";
import { Card } from "../../../shared/components/ui/Card";
import { SelectField } from "../../../shared/components/ui/SelectField";
import { ProfileAvatar } from "../../../shared/components/ui/ProfileAvatar";
import { KpiCard } from "../../../shared/components/ui/KpiCard";
import { EmptyState } from "../../../shared/components/ui/EmptyState";
import { ChartCard } from "../../../shared/components/ui/ChartCard";
import { EmptyChart } from "../../../shared/components/ui/EmptyChart";
import { PageHeader } from "../../../shared/components/ui/PageHeader";
import { ConfirmModal } from "../../../shared/components/ConfirmModal";
import { ActionMenu } from "../../../shared/components/ActionMenu";
import { Pagination } from "../../../shared/components/Pagination";
import { BulkActionBar } from "../../../shared/components/BulkActionBar";
import { PropertyCombobox } from "../../../shared/components/ui/PropertyCombobox";
import { ConsultantCombobox } from "../../../shared/components/ui/ConsultantCombobox";
import { DistrictCombobox } from "../../../shared/components/ui/DistrictCombobox";
import { apiFetch, readJson, apiErrorMessage, getCsrfToken } from "../../../shared/lib/apiClient";
import { toast } from "../../../shared/lib/utils";
import { CHART_COLORS, DELEGATION_COLORS } from "../../../shared/lib/constants";
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, ReferenceLine, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, ScatterChart, ZAxis, Scatter, PieChart as RechartsPieChart, RadialBarChart, RadialBar } from "recharts";
import { Building2, FileText, CheckSquare, BellRing, Users, Activity, Settings, Plus, RefreshCw, Eye, Edit2, Trash2, Archive, Clock, MapPin, Check, X, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, SlidersHorizontal, ArrowUpRight, LayoutGrid, List, Download, Search, MoreVertical, Phone, Mail, Calendar, TrendingUp, Star, Shield, Lock, Key, Send, Loader2, AlertTriangle, Info, XCircle, CheckCircle2, TriangleAlert, Columns, MessageSquare, Sparkles, GripVertical, Building, History, Flame, Image, Zap, LayoutDashboard, Command, Filter, Award, BarChart3, Layers, AlertCircle, Target } from "lucide-react";
function PropertyReportsPage({ csrfToken, propertyId, propertyPreview, onBack }: { csrfToken: string; propertyId: string | null; propertyPreview?: Property | null; onBack: () => void; }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<PropertyReportPayload | null>(null);
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      if (dateFrom) qs.set("date_from", dateFrom);
      if (dateTo) qs.set("date_to", dateTo);
      const url = `/api/reports/properties/${propertyId}/${qs.toString() ? "?" + qs.toString() : ""}`;
      const res = await apiFetch(url, { method: "GET" }, csrfToken);
      if (!res.ok) {
        const err = await readJson(res);
        setError(apiErrorMessage(err, "خطا در بارگذاری گزارش"));
        return;
      }
      const payload = await res.json();
      setData(payload);
    } catch (e: any) {
      setError(e?.message || "خطا در ارتباط با سرور");
    } finally {
      setLoading(false);
    }
  }, [propertyId, dateFrom, dateTo, csrfToken]);

  useEffect(() => { load(); }, [load]);

  const handleExport = async () => {
    if (!propertyId) return;
    setExporting(true);
    try {
      const qs = new URLSearchParams();
      if (dateFrom) qs.set("date_from", dateFrom);
      if (dateTo) qs.set("date_to", dateTo);
      const url = `/api/reports/properties/${propertyId}/export/${qs.toString() ? "?" + qs.toString() : ""}`;
      const res = await fetch(url, { method: "GET", credentials: "same-origin" });
      if (!res.ok) {
        toast({ type: "error", message: "خطا در تهیه خروجی CSV" });
        return;
      }
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `property-report-${propertyId}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
      toast({ type: "success", message: "خروجی CSV دریافت شد." });
    } catch {
      toast({ type: "error", message: "خطا در تهیه خروجی CSV" });
    } finally {
      setExporting(false);
    }
  };

  if (!propertyId) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <EmptyState icon={<AlertCircle size={28} />} title="ملک انتخاب نشده" description="ابتدا یک ملک را انتخاب کنید." action={<Btn onClick={onBack} variant="secondary"><ChevronRight size={13} />بازگشت</Btn>} />
      </div>
    );
  }

  const k = data?.kpis || {};
  const ch = data?.charts || {};

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <PageHeader
        title={data ? `گزارش تحلیلی: ${data.property.title}` : propertyPreview ? `گزارش تحلیلی: ${propertyPreview.title}` : "گزارش تحلیلی ملک"}
        subtitle={data ? `کد ${data.property.internalCode} • محله ${data.property.neighborhood || "—"}` : (propertyPreview?.internalCode ? `کد ${propertyPreview.internalCode}` : "در حال بارگذاری…")}
        actions={
          <div className="flex gap-2">
            <Btn variant="ghost" size="sm" onClick={onBack}><ChevronRight size={13} />بازگشت به ملک</Btn>
            <Btn variant="secondary" size="sm" onClick={handleExport} disabled={exporting || !data}><Download size={13} />{exporting ? "در حال تهیه…" : "خروجی CSV"}</Btn>
          </div>
        }
      />

      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1 w-56">
            <JalaliDateInput label="از تاریخ" value={dateFrom} onChange={setDateFrom} />
          </div>
          <div className="flex flex-col gap-1 w-56">
            <JalaliDateInput label="تا تاریخ" value={dateTo} onChange={setDateTo} />
          </div>
          <div className="flex gap-2 mr-auto">
            <Btn size="sm" onClick={load} disabled={loading}>{loading ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}اعمال فیلتر</Btn>
            <Btn size="sm" variant="ghost" onClick={() => { setDateFrom(""); setDateTo(""); }}>پاک کردن</Btn>
          </div>
        </div>
        {data?.warnings && data.warnings.length > 0 && (
          <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 text-amber-800 px-3 py-2 text-xs space-y-1">
            <div className="font-semibold flex items-center gap-1"><AlertTriangle size={13} /> نکات و فال‌بک‌های محاسبه:</div>
            <ul className="list-disc pr-4 space-y-0.5">
              {data.warnings.map((w: string, i: number) => <li key={i}>{w}</li>)}
            </ul>
          </div>
        )}
        {data?.meta?.comparablesSource && (
          <p className="text-[11px] text-muted-foreground mt-2">
            منبع مقایسه قیمت: {data.meta.comparablesSource}
          </p>
        )}
      </Card>

      {loading && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Card key={i} className="p-5"><div className="h-10 w-10 rounded-xl bg-secondary/60 mb-3 animate-pulse" /><div className="h-6 w-24 bg-secondary/60 rounded animate-pulse mb-1" /><div className="h-4 w-32 bg-secondary/40 rounded animate-pulse" /></Card>
          ))}
        </div>
      )}

      {error && <Card className="p-6 border-red-200 bg-red-50 text-red-700 text-sm">{error}</Card>}

      {!loading && !error && data && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard label="روزهای تصدی" value={(k.tenureDays ?? "—").toLocaleString?.("fa-IR") ?? "—"} icon={<Calendar size={16} />} color="bg-blue-50 text-blue-600" />
            <KpiCard label="وظایف تأخیردار" value={(k.tasksOverdueCount ?? 0).toLocaleString("fa-IR")} icon={<AlertCircle size={16} />} color={(k.tasksOverdueCount ?? 0) > 0 ? "bg-red-50 text-red-600" : "bg-amber-50 text-amber-600"} />
            <KpiCard label="پیگیری‌های تأخیردار" value={(k.followupsOverdueCount ?? 0).toLocaleString("fa-IR")} icon={<BellRing size={16} />} color={(k.followupsOverdueCount ?? 0) > 0 ? "bg-red-50 text-red-600" : "bg-purple-50 text-purple-600"} />
            <KpiCard label="نرخ تکمیل کار" value={k.workCompletionRate != null ? `${Number(k.workCompletionRate).toLocaleString("fa-IR")}٪` : "—"} icon={<Target size={16} />} color="bg-emerald-50 text-emerald-600" />
            <KpiCard label="قیمت هر متر" value={k.pricePerSqm != null ? fmtShort(Number(k.pricePerSqm)) : "—"} icon={<TrendingUp size={16} />} color="bg-primary/10 text-primary" />
            <KpiCard label="تعداد تصاویر" value={(k.imagesCount ?? 0).toLocaleString("fa-IR")} icon={<Image size={16} />} color="bg-purple-50 text-purple-600" />
            <KpiCard label="روز در بازار" value={k.daysOnMarket != null ? `${Number(k.daysOnMarket).toLocaleString("fa-IR")} روز` : "—"} icon={<Clock size={16} />} color="bg-orange-50 text-orange-600" />
            <KpiCard label="دقت جغرافیایی" value={k.geoPrecisionFlag ? "دقیق" : "نادقیق"} icon={<MapPin size={16} />} color={k.geoPrecisionFlag ? "bg-emerald-50 text-emerald-600" : "bg-red-50 text-red-600"} />
            <KpiCard label="نرخ اتلاف آگهی" value={k.listingBurnRate != null ? `${Number((Number(k.listingBurnRate) * 100).toFixed(0)).toLocaleString("fa-IR")}٪` : "—"} sub={ch.burnRateGauge?.status} icon={<Flame size={16} />} color="bg-red-50 text-red-600" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ChartCard title="روزهای تصدی ملک" subtitle="این نمودار نشان می‌دهد ملک چه مدت در سیستم ثبت شده است. هرچه ملک قدیمی‌تر باشد، نیاز به بازنگری قیمت و استراتژی فروش بیشتری دارد.">
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={ch.tenureHistogram || []} margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                    <XAxis dataKey="label" fontSize={11} />
                    <YAxis fontSize={11} />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                    <Bar dataKey="count" fill={CHART_COLORS[0]} radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>

            <ChartCard title="وظایف سررسید‌گذشته" subtitle="این نمودار وظایفی را نشان می‌دهد که از موعد مقرر گذشته‌اند. تعداد بالا نشان‌دهنده نیاز به پیگیری فوری و مدیریت بهتر زمان است.">
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={ch.tasksOverdueByType || []} margin={{ top: 10, right: 10, left: 0, bottom: 10 }} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                    <XAxis type="number" fontSize={11} />
                    <YAxis dataKey="label" type="category" fontSize={11} width={100} />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                    <Bar dataKey="count" fill={CHART_COLORS[2]} radius={[0, 8, 8, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>

            <ChartCard title="پیگیری‌های سررسید‌گذشته" subtitle="این نمودار پیگیری‌هایی را نشان می‌دهد که زمان‌شان گذشته و هنوز تکمیل نشده‌اند. تأخیر در پیگیری می‌تواند احتمال بستن معامله را کاهش دهد.">
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={ch.followupsOverdueByType || []} margin={{ top: 10, right: 10, left: 0, bottom: 10 }} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                    <XAxis type="number" fontSize={11} />
                    <YAxis dataKey="label" type="category" fontSize={11} width={100} />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                    <Bar dataKey="count" fill="#EF4444" radius={[0, 8, 8, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>

            <ChartCard title="نرخ تکمیل پیگیری‌ها" subtitle="این نمودار درصد پیگیری‌های تکمیل‌شده این ملک را بر اساس نوع ارتباط نشان می‌دهد. محاسبه از وضعیت واقعی پیگیری است، نه حدس احتمال.">
              {ch.workCompletionByType?.length ? (
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={ch.workCompletionByType} margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                      <XAxis dataKey="label" fontSize={11} />
                      <YAxis fontSize={11} domain={[0, 100]} />
                      <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} formatter={(v: any) => [`${Number(v ?? 0).toLocaleString("fa-IR")}٪`, "نرخ تکمیل"]} />
                      <Bar dataKey="rate" fill={CHART_COLORS[1]} radius={[8, 8, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : <EmptyChart message="داده‌ای برای نمایش وجود ندارد." />}
            </ChartCard>

            <ChartCard title="قیمت هر متر مربع" subtitle="این نقشه موقعیت ملک و قیمت هر متر مربع آن را نشان می‌دهد. برای تحلیل دقیق‌تر، باید با املاک مشابه در منطقه مقایسه شود.">
              {ch.priceMap?.length ? (
                <div className="h-56 rounded-xl border border-border bg-gradient-to-br from-emerald-50 to-blue-50 relative overflow-hidden">
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="relative">
                      <div className="absolute inset-0 rounded-full bg-emerald-500/20 animate-ping" style={{ width: 80, height: 80, left: -40, top: -40 }} />
                      <div className="w-10 h-10 rounded-full bg-emerald-500 border-4 border-white shadow-lg flex items-center justify-center text-white text-xs font-bold">
                        {Math.round(ch.priceMap[0].value / 1_000_000)}M
                      </div>
                    </div>
                  </div>
                  <div className="absolute top-3 right-3 bg-white/90 rounded-lg px-3 py-1.5 text-xs font-medium shadow-sm">
                    <MapPin size={12} className="inline ml-1" />{ch.priceMap[0].label}
                  </div>
                  <p className="absolute bottom-2 right-3 text-[10px] text-muted-foreground">Lat: {ch.priceMap[0].lat?.toFixed?.(4)} • Lon: {ch.priceMap[0].lng?.toFixed?.(4)}</p>
                </div>
              ) : <EmptyChart message="موقعیت جغرافیایی برای نمایش روی نقشه موجود نیست." />}
            </ChartCard>

            <ChartCard title="تعداد تصاویر ملک" subtitle="این نمودار توزیع تعداد تصاویر ثبت‌شده را نشان می‌دهد. تعداد بیشتر تصاویر معمولاً به معنای جذب بیشتر بازدیدکننده و افزایش احتمال فروش است.">
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={ch.imagesHistogram || []} margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                    <XAxis dataKey="label" fontSize={11} />
                    <YAxis fontSize={11} />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                    <Bar dataKey="count" fill={CHART_COLORS[3]} radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>

            <ChartCard title="مدت حضور در بازار" subtitle="این نمودار نشان می‌دهد آگهی‌های ملک چه مدت در بازار فعال بوده‌اند. مدت زمان طولانی ممکن است نیاز به بازنگری قیمت یا استراتژی بازاریابی را نشان دهد.">
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={ch.daysOnMarketHistogram || []} margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                    <XAxis dataKey="label" fontSize={11} />
                    <YAxis fontSize={11} />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                    <Bar dataKey="count" fill={CHART_COLORS[4]} radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>

            <ChartCard title="تحلیل فضای آگهی" subtitle="این نمودار پراکندگی آگهی‌ها را بر اساس مدت نمایش و اولویت نشان می‌دهد. این تحلیل به شناسایی آگهی‌های موثر و کم‌بازده کمک می‌کند.">
              {ch.spatialScatter?.length ? (
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                      <XAxis type="number" dataKey="x" name="روز نمایش" fontSize={11} />
                      <YAxis type="number" dataKey="y" name="اولویت" fontSize={11} />
                      <ZAxis range={[60, 400]} />
                      <Tooltip cursor={{ strokeDasharray: "3 3" }} contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                      <Scatter data={ch.spatialScatter} fill={CHART_COLORS[1]} />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              ) : <EmptyChart message="داده پراکندگی موجود نیست." />}
            </ChartCard>

            <ChartCard title="انحراف قیمت از عرف محله" subtitle="این نمودار میزان انحراف قیمت ملک را نسبت به میانگین منطقه نشان می‌دهد. انحراف مثبت به معنای قیمت بالاتر از عرف و انحراف منفی به معنای قیمت پایین‌تر است.">
              {k.priceDeviationIndex != null ? (
                <div className="space-y-4">
                  <div className="h-40">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={ch.priceDeviation?.bars || []} margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                        <XAxis dataKey="label" fontSize={11} />
                        <YAxis fontSize={11} />
                        <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                        <ReferenceLine y={0} stroke="#94A3B8" />
                        <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                          {(ch.priceDeviation?.bars || []).map((_: any, i: number) => (
                            <Cell key={i} fill={i === 0 ? CHART_COLORS[0] : CHART_COLORS[2]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="text-sm text-center font-semibold">
                    انحراف: <span className={Number(k.priceDeviationIndex) >= 0 ? "text-emerald-600" : "text-red-600"}>
                      {Number(k.priceDeviationIndex) >= 0 ? "+" : ""}{(Number(k.priceDeviationIndex) * 100).toFixed(1)}٪
                    </span>
                  </div>
                </div>
              ) : <EmptyChart message="انحراف قیمت قابل محاسبه نیست (داده‌های مقایسه‌ای کافی نیست)." />}
            </ChartCard>

            <ChartCard title="دقت مختصات جغرافیایی" subtitle="این نمودار وضعیت دقت مختصات جغرافیایی ملک را نشان می‌دهد. مختصات دقیق برای نمایش صحیح در نقشه و تحلیل‌های مکانی ضروری است.">
              <div className="h-56 flex items-center justify-center">
                <ResponsiveContainer width="100%" height="100%">
                  <RechartsPieChart>
                    <Pie data={ch.geoDonut || []} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" stroke="none" paddingAngle={2}>
                      {(ch.geoDonut || []).map((_: any, i: number) => (
                        <Cell key={i} fill={i === 0 ? CHART_COLORS[0] : "#CBD5E1"} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                  </RechartsPieChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>

            <ChartCard title="امتیاز حرارت تعامل" subtitle="این نمودار حرارتی نشان می‌دهد در کدام هفته‌ها بیشترین تعامل (پیگیری، بازدید، مذاکره) رخ داده است. نقاط داغ نشان‌دهنده دوره‌های فعالیت بالا هستند.">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr>
                      <th className="text-right p-2 font-semibold text-muted-foreground w-28">نوع فعالیت</th>
                      {(ch.engagementHeatmap?.weeks || []).map((w: string) => (
                        <th key={w} className="p-2 font-semibold text-muted-foreground">{w}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(ch.engagementHeatmap?.rows || []).map((row: any) => {
                      const max = Math.max(1, ...(row.values || []));
                      return (
                        <tr key={row.key}>
                          <td className="p-2 font-medium">{row.label}</td>
                          {(row.values || []).map((v: number, i: number) => {
                            const intensity = v / max;
                            const bg = v === 0 ? "bg-secondary" : intensity > 0.66 ? "bg-emerald-500" : intensity > 0.33 ? "bg-emerald-300" : "bg-emerald-100";
                            const fg = v === 0 || intensity < 0.33 ? "text-muted-foreground" : "text-white";
                            return (
                              <td key={i} className="p-1">
                                <div className={cx("rounded-lg h-9 flex items-center justify-center font-semibold", bg, fg)}>{v.toLocaleString("fa-IR")}</div>
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </ChartCard>

            <ChartCard title="کانال‌های انتشار آگهی" subtitle="این نمودار توزیع آگهی‌ها را در کانال‌های مختلف (وب‌سایت، اینستاگرام، تلگرام و ...) نشان می‌دهد. تنوع کانال‌ها به جذب مخاطبان بیشتر کمک می‌کند.">
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={ch.publishChannel || []} margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                    <XAxis dataKey="label" fontSize={11} />
                    <YAxis fontSize={11} />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                    <Bar dataKey="count" fill={CHART_COLORS[1]} radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>

            <ChartCard title="میانگین عمر آگهی در هر کانال" subtitle="این نمودار نشان می‌دهد آگهی‌ها در هر کانال به طور متوسط چه مدت فعال بوده‌اند. عمر طولانی‌تر معمولاً نشان‌دهنده اثربخشی بالاتر آن کانال است.">
              {ch.avgLifespanByChannel?.length ? (
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={ch.avgLifespanByChannel} margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                      <XAxis dataKey="label" fontSize={11} />
                      <YAxis fontSize={11} />
                      <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                      <Bar dataKey="avgLifespan" fill={CHART_COLORS[5]} radius={[8, 8, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : <EmptyChart message="آگهی‌ای برای این ملک یافت نشد." />}
            </ChartCard>

            <ChartCard title="بازه زمانی نمایش آگهی‌ها" subtitle="این نمودار گانت نشان می‌دهد هر آگهی در چه بازه زمانی فعال بوده است. این تحلیل به شناسایی دوره‌های طلایی بازاریابی و تداخلات کمک می‌کند." className="lg:col-span-2">
              {ch.exposureTimeline?.length ? (
                <div className="space-y-3">
                  {(ch.exposureTimeline || []).map((t: any) => {
                    const start = new Date(t.start).getTime();
                    const end = new Date(t.end).getTime();
                    const all = ch.exposureTimeline;
                    const minT = Math.min(...all.map((x: any) => new Date(x.start).getTime()));
                    const maxT = Math.max(...all.map((x: any) => new Date(x.end).getTime()));
                    const total = Math.max(1, maxT - minT);
                    const leftPct = ((start - minT) / total) * 100;
                    const widthPct = Math.max(5, ((end - start) / total) * 100);
                    const statusColor: Record<string, string> = { ACTIVE: "bg-emerald-500", PAUSED: "bg-amber-500", EXPIRED: "bg-slate-400", ARCHIVED: "bg-red-400", DRAFT: "bg-blue-400" };
                    return (
                      <div key={t.id} className="flex items-center gap-3 text-xs">
                        <div className="w-44 flex-shrink-0 truncate font-medium">{t.label}</div>
                        <div className="flex-1 h-7 relative bg-secondary/60 rounded-lg overflow-hidden">
                          <div className={cx("absolute top-1 bottom-1 rounded-md flex items-center px-2 text-white text-[10px] font-semibold shadow-sm", statusColor[t.status] || "bg-primary")} style={{ right: `${leftPct}%`, width: `${widthPct}%` }}>
                            {t.channel} • {t.days} روز
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : <EmptyChart message="بازه نمایشی برای آگهی‌ها یافت نشد." />}
            </ChartCard>

            <ChartCard title="شاخص تفویض وظایف" subtitle="این نمودار نشان می‌دهد چه درصدی از آگهی‌ها به مشاوران دیگر تفویض شده است. تفویض مناسب به تعادل کار و استفاده از تخصص‌های مختلف کمک می‌کند.">
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={ch.delegationByChannel || []} margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                    <XAxis dataKey="label" fontSize={11} />
                    <YAxis fontSize={11} />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="selfManaged" name="مدیریت شخصی" stackId="a" fill={DELEGATION_COLORS.selfManaged} radius={[0, 0, 0, 0]} />
                    <Bar dataKey="delegated" name="تفویض‌شده" stackId="a" fill={DELEGATION_COLORS.delegated} radius={[0, 0, 0, 0]} />
                    <Bar dataKey="unassigned" name="واگذار نشده" stackId="a" fill={DELEGATION_COLORS.unassigned} radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>

            <ChartCard title="نرخ اتلاف آگهی‌ها" subtitle="این نمودار درصد آگهی‌هایی را نشان می‌دهد که بدون نتیجه منقضی یا بایگانی شده‌اند. نرخ بالا نشان‌دهنده نیاز به بازنگری استراتژی بازاریابی و قیمت‌گذاری است.">
              <div className="h-56 flex items-center justify-center relative">
                <ResponsiveContainer width="100%" height="100%">
                  <RadialBarChart innerRadius="70%" outerRadius="100%" data={[{ name: "Burn", value: k.listingBurnRate != null ? Math.round(k.listingBurnRate * 100) : 0, fill: Number(k.listingBurnRate ?? 0) >= 0.5 ? "#EF4444" : Number(k.listingBurnRate ?? 0) >= 0.2 ? "#F59E0B" : "#0BB68A" }]} startAngle={180} endAngle={0}>
                    <RadialBar background dataKey="value" cornerRadius={10} fill="#0BB68A" />
                  </RadialBarChart>
                </ResponsiveContainer>
                <div className="absolute text-center">
                  <div className="text-3xl font-bold">
                    {k.listingBurnRate != null ? `${(Number(k.listingBurnRate) * 100).toFixed(0)}٪` : "—"}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">{ch.burnRateGauge?.status || "ناموجود"}</div>
                </div>
              </div>
            </ChartCard>
          </div>
        </>
      )}
    </div>
  );
}


// =============================================================================
//  Districts Management
// =============================================================================

export { PropertyReportsPage };
