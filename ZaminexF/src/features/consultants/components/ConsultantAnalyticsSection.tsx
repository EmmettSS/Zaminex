import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { Page, Role, Property, Listing, FollowUp, ConsultantItem, BadgeV, ConsultantAnalyticsPayload } from "../../../shared/lib/types";
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
import { ActionMenu } from "../../../shared/components/ActionMenu";
import { Pagination } from "../../../shared/components/Pagination";
import { BulkActionBar } from "../../../shared/components/BulkActionBar";
import { PropertyCombobox } from "../../../shared/components/ui/PropertyCombobox";
import { ConsultantCombobox } from "../../../shared/components/ui/ConsultantCombobox";
import { DistrictCombobox } from "../../../shared/components/ui/DistrictCombobox";
import { MultiPropertyCombobox } from "../../../shared/components/ui/MultiPropertyCombobox";
import { MultiConsultantCombobox } from "../../../shared/components/ui/MultiConsultantCombobox";
import { apiFetch, readJson, apiErrorMessage, getCsrfToken } from "../../../shared/lib/apiClient";
import { toast } from "../../../shared/lib/utils";
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, MessageSquare, Sparkles, GripVertical, MoreVertical, Building, History, Flame, Image, Filter } from "lucide-react";
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, ReferenceLine, ScatterChart, Scatter, ZAxis, RadialBarChart, RadialBar, PieChart as RechartsPieChart } from "recharts";
import { FOLLOWUP_TYPE_LABELS, CHART_COLORS } from "../../../shared/lib/constants";
import { ChartCard } from "../../../shared/components/ui/ChartCard";
import { EmptyChart } from "../../../shared/components/ui/EmptyChart";
import { PropertyLocationsMap } from "./PropertyLocationsMap";

const FOLLOWUP_STATUS_LABELS: Record<string, string> = {
  scheduled: "برنامه‌ریزی‌شده",
  completed: "تکمیل‌شده",
  cancelled: "لغوشده",
  overdue: "از تاریخ گذشته",
};

const LISTING_STATUS_COLORS: Record<string, string> = {
  DRAFT: "#94A3B8",
  ACTIVE: "#0BB68A",
  PAUSED: "#F59E0B",
  SOLD: "#EF4444",
  EXPIRED: "#8B5CF6",
  ARCHIVED: "#64748B",
};

/** Radar axis labels sit outside the polygon, next to their own spoke. */
function splitRadarLabel(value: string): string[] {
  const parts = value.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return [parts[0], parts.slice(1).join(" ")];
  return [value];
}

function PerformanceRadarTick({
  x = 0,
  y = 0,
  cx,
  cy,
  payload,
}: {
  x?: number;
  y?: number;
  cx?: number;
  cy?: number;
  payload?: { value?: string };
}) {
  const ox = cx ?? x;
  const oy = cy ?? y;
  const dx = x - ox;
  const dy = y - oy;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  const tx = ox + ux * (len + 14);
  const ty = oy + uy * (len + 14);

  let textAnchor: "start" | "middle" | "end" = "middle";
  if (ux > 0.35) textAnchor = "start";
  else if (ux < -0.35) textAnchor = "end";

  const lines = splitRadarLabel(payload?.value ?? "");
  const lineH = 13;
  let startDy = 0;
  if (uy < -0.5) startDy = lines.length > 1 ? -(lineH - 2) : 0;
  else if (uy > 0.5) startDy = 11;
  else startDy = lines.length > 1 ? -4 : 3;

  return (
    <text
      x={tx}
      y={ty}
      textAnchor={textAnchor}
      fontSize={11}
      fontWeight={500}
      fill="#6B7280"
      style={{ direction: "ltr", unicodeBidi: "isolate" }}
    >
      {lines.map((line, i) => (
        <tspan key={line} x={tx} dy={i === 0 ? startDy : lineH}>{line}</tspan>
      ))}
    </text>
  );
}
function ConsultantAnalyticsSection({ consultantId, csrfToken }: { consultantId: string | number; csrfToken: string }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ConsultantAnalyticsPayload | null>(null);

  const load = useCallback(async () => {
    if (!consultantId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/common/api/analytics/consultants/${consultantId}/`, { method: "GET" }, csrfToken);
      const payload = await readJson(res);
      if (!res.ok) throw new Error(apiErrorMessage(payload, "خطا در بارگذاری تحلیل مشاور"));
      setData(payload);
    } catch (e: any) {
      setError(e?.message || "خطا در ارتباط با سرور");
    } finally {
      setLoading(false);
    }
  }, [consultantId, csrfToken]);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-5">
        {Array.from({ length: 2 }).map((_, i) => (
          <Card key={i} className="p-5">
            <div className="h-4 w-28 bg-secondary/60 rounded animate-pulse mb-4" />
            <div className="h-40 bg-secondary/30 rounded-xl animate-pulse" />
          </Card>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Card className="p-8 text-center">
        <p className="text-sm text-red-600 mb-3">{error}</p>
        <Btn variant="secondary" size="sm" onClick={load}><RefreshCw size={13} />تلاش مجدد</Btn>
      </Card>
    );
  }

  const charts = data?.charts || {};
  const monthly = (charts.monthlyActivity || []).map((m) => ({
    ...m,
    label: (m as any).label || new Date(`${m.month}T00:00:00`).toLocaleDateString("fa-IR", { month: "long" }),
  }));
  const tasksByStatus = (charts.tasksByStatus || []).map((s) => ({ ...s, name: toPersianTaskStatus(s.status) }));
  const followupsByType = (charts.followupsByType || []).map((f) => ({ ...f, label: FOLLOWUP_TYPE_LABELS[f.type] || f.type }));
  const listingsByChannel = (charts.listingsByChannel || []).map((c) => ({ ...c, label: toPersianChannel(c.channel) }));
  const performanceProfile = charts.performanceProfile || [];
  const hasMonthlyData = monthly.some((m) => m.tasksCompleted > 0 || m.followups > 0 || m.listings > 0);

  const listingsByDealType = (charts.listingsByDealType || []).map((d) => ({ ...d, label: toPersianDeal(d.label) }));
  const listingsByStatus = (charts.listingsByStatus || []).map((s) => ({ ...s, label: toPersianListingStatus(s.status) }));
  const tasksByPriority = (charts.tasksByPriority || []).map((p) => ({ ...p, label: toPersianPriority(p.priority) }));
  const followupsByStatus = (charts.followupsByStatus || []).map((s) => ({ ...s, label: FOLLOWUP_STATUS_LABELS[s.status] || s.status }));
  const propertiesByType = (charts.propertiesByType || []).map((t) => ({
    ...t,
    label: t.type ? toPersianType(t.type) : "سایر",
  }));
  const propertyLocations = charts.propertyLocations || [];

  return (
    <>
      <div className="grid grid-cols-2 gap-5">
        <ChartCard title="روند فعالیت ماهانه" subtitle="حجم پیگیری‌ها و وظایف تکمیل‌شده این مشاور در ۶ ماه اخیر؛ شاخصی از پویایی و بهره‌وری عملیاتی.">
          {hasMonthlyData ? (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={monthly} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="cg-fu" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#0BB68A" stopOpacity={0.3} /><stop offset="100%" stopColor="#0BB68A" stopOpacity={0} /></linearGradient>
                    <linearGradient id="cg-task" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#3B82F6" stopOpacity={0.3} /><stop offset="100%" stopColor="#3B82F6" stopOpacity={0} /></linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                  <XAxis dataKey="label" fontSize={11} />
                  <YAxis fontSize={11} allowDecimals={false} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                  <Area type="monotone" dataKey="followups" name="پیگیری‌ها" stroke="#0BB68A" strokeWidth={2.5} fill="url(#cg-fu)" dot={false} />
                  <Area type="monotone" dataKey="tasksCompleted" name="وظایف تکمیل‌شده" stroke="#3B82F6" strokeWidth={2.5} fill="url(#cg-task)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : <EmptyChart message="فعالیتی در ۶ ماه اخیر برای این مشاور ثبت نشده است." />}
        </ChartCard>

        <ChartCard title="پروفایل عملکرد" subtitle="امتیاز ترکیبی مشاور در پنج حوزه کلیدی (۰ تا ۱۰۰): تکمیل وظایف، انجام به‌موقع، تکمیل پیگیری، پوشش بازاریابی و تعامل اخیر.">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={performanceProfile} cx="50%" cy="50%" outerRadius="56%">
                <PolarGrid stroke="#E5E7EB" />
                <PolarAngleAxis dataKey="metric" tick={<PerformanceRadarTick />} tickLine={false} />
                <Radar dataKey="score" name="امتیاز" stroke="#0BB68A" fill="#0BB68A" fillOpacity={0.35} strokeWidth={2} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard title="ترکیب وضعیت وظایف" subtitle="توزیع وظایف محول‌شده به این مشاور بر اساس وضعیت فعلی؛ سهم بزرگ تکمیل‌شده نشان‌دهنده عملکرد مطلوب است.">
          {tasksByStatus.length ? (
            <>
              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <RechartsPieChart>
                    <Pie data={tasksByStatus} cx="50%" cy="50%" innerRadius={45} outerRadius={70} dataKey="count" nameKey="name" stroke="none" paddingAngle={2}>
                      {tasksByStatus.map((s, i) => (
                        <Cell key={i} fill={s.status === "COMPLETED" ? CHART_COLORS[0] : s.status === "IN_PROGRESS" ? CHART_COLORS[1] : CHART_COLORS[2]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                  </RechartsPieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-2">
                {tasksByStatus.map((s, i) => (
                  <span key={i} className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.status === "COMPLETED" ? CHART_COLORS[0] : s.status === "IN_PROGRESS" ? CHART_COLORS[1] : CHART_COLORS[2] }} />
                    {s.name}: <strong className="text-foreground">{s.count.toLocaleString("fa-IR")}</strong>
                  </span>
                ))}
              </div>
            </>
          ) : <EmptyChart message="وظیفه‌ای برای این مشاور ثبت نشده است." />}
        </ChartCard>

        <ChartCard title="نرخ تکمیل پیگیری‌ها" subtitle="درصد پیگیری‌های تکمیل‌شده این مشاور به تفکیک نوع ارتباط؛ بر اساس وضعیت واقعی، نه حدس احتمال.">
          {followupsByType.length ? (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={followupsByType} margin={{ top: 10, right: 10, left: 0, bottom: 10 }} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                  <XAxis type="number" fontSize={11} domain={[0, 100]} />
                  <YAxis dataKey="label" type="category" fontSize={11} width={95} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} formatter={(v: any) => [`${Number(v ?? 0).toLocaleString("fa-IR")}٪`, "نرخ تکمیل"]} />
                  <Bar dataKey="completionRate" name="نرخ تکمیل" fill={CHART_COLORS[3]} radius={[0, 8, 8, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <EmptyChart message="پیگیری‌ای برای این مشاور ثبت نشده است." />}
        </ChartCard>
      </div>

      <ChartCard title="کانال‌های انتشار آگهی" subtitle="توزیع آگهی‌های این مشاور (ایجادشده یا واگذارشده) در کانال‌های مختلف انتشار.">
        {listingsByChannel.length ? (
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={listingsByChannel} margin={{ top: 10, right: 10, left: 0, bottom: 10 }} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis type="number" fontSize={11} allowDecimals={false} />
                <YAxis dataKey="label" type="category" fontSize={11} width={95} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                <Bar dataKey="count" name="تعداد آگهی" radius={[0, 8, 8, 0]}>
                  {listingsByChannel.map((_, i) => (
                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : <EmptyChart message="آگهی‌ای برای این مشاور ثبت نشده است." />}
      </ChartCard>

      <ChartCard title="نقشه‌ی توزیع املاک" subtitle="موقعیت جغرافیایی املاک واگذارشده به این مشاور روی نقشه؛ رنگ نشانگر بر اساس وضعیت ملک است.">
        {propertyLocations.length ? (
          <PropertyLocationsMap points={propertyLocations} />
        ) : <EmptyChart message="برای املاک این مشاور مختصات جغرافیایی ثبت نشده است." />}
      </ChartCard>

      <div className="grid grid-cols-2 gap-5">
        <ChartCard title="ترکیب نوع معامله آگهی‌ها" subtitle="توزیع آگهی‌های این مشاور بر اساس نوع معامله (فروش، رهن و اجاره و …).">
          {listingsByDealType.length ? (
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={listingsByDealType} margin={{ top: 10, right: 10, left: 0, bottom: 10 }} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                  <XAxis type="number" fontSize={11} allowDecimals={false} />
                  <YAxis dataKey="label" type="category" fontSize={11} width={95} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                  <Bar dataKey="count" name="تعداد آگهی" fill={CHART_COLORS[4]} radius={[0, 8, 8, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <EmptyChart message="آگهی‌ای برای این مشاور ثبت نشده است." />}
        </ChartCard>

        <ChartCard title="وضعیت آگهی‌ها" subtitle="توزیع آگهی‌های این مشاور بر اساس وضعیت فعلی (فعال، فروخته، منقضی و …).">
          {listingsByStatus.length ? (
            <>
              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <RechartsPieChart>
                    <Pie data={listingsByStatus} cx="50%" cy="50%" innerRadius={45} outerRadius={70} dataKey="count" nameKey="label" stroke="none" paddingAngle={2}>
                      {listingsByStatus.map((s, i) => (
                        <Cell key={i} fill={LISTING_STATUS_COLORS[s.status] || CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                  </RechartsPieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-2">
                {listingsByStatus.map((s, i) => (
                  <span key={i} className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: LISTING_STATUS_COLORS[s.status] || CHART_COLORS[i % CHART_COLORS.length] }} />
                    {s.label}: <strong className="text-foreground">{s.count.toLocaleString("fa-IR")}</strong>
                  </span>
                ))}
              </div>
            </>
          ) : <EmptyChart message="آگهی‌ای برای این مشاور ثبت نشده است." />}
        </ChartCard>

        <ChartCard title="اولویت وظایف" subtitle="توزیع وظایف این مشاور بر اساس سطح اولویت (کم، متوسط، زیاد، فوری).">
          {tasksByPriority.length ? (
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={tasksByPriority} margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                  <XAxis dataKey="label" fontSize={11} />
                  <YAxis fontSize={11} allowDecimals={false} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                  <Bar dataKey="count" name="تعداد وظیفه" fill={CHART_COLORS[1]} radius={[8, 8, 0, 0]}>
                    {tasksByPriority.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <EmptyChart message="وظیفه‌ای برای این مشاور ثبت نشده است." />}
        </ChartCard>

        <ChartCard title="وضعیت پیگیری‌ها" subtitle="توزیع پیگیری‌های این مشاور بر اساس وضعیت (برنامه‌ریزی‌شده / تکمیل‌شده).">
          {followupsByStatus.length ? (
            <>
              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <RechartsPieChart>
                    <Pie data={followupsByStatus} cx="50%" cy="50%" innerRadius={45} outerRadius={70} dataKey="count" nameKey="label" stroke="none" paddingAngle={2}>
                      {followupsByStatus.map((s, i) => (
                        <Cell key={i} fill={s.status === "completed" ? CHART_COLORS[0] : s.status === "overdue" ? "#EF4444" : CHART_COLORS[2]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                  </RechartsPieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-2">
                {followupsByStatus.map((s, i) => (
                  <span key={i} className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.status === "completed" ? CHART_COLORS[0] : CHART_COLORS[2] }} />
                    {s.label}: <strong className="text-foreground">{s.count.toLocaleString("fa-IR")}</strong>
                  </span>
                ))}
              </div>
            </>
          ) : <EmptyChart message="پیگیری‌ای برای این مشاور ثبت نشده است." />}
        </ChartCard>
      </div>

      <ChartCard title="ترکیب نوع املاک" subtitle="توزیع املاک این مشاور بر اساس نوع ملک (آپارتمان، ویلا، زمین و …).">
        {propertiesByType.length ? (
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={propertiesByType} margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="label" fontSize={11} />
                <YAxis fontSize={11} allowDecimals={false} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                <Bar dataKey="count" name="تعداد ملک" fill={CHART_COLORS[5]} radius={[8, 8, 0, 0]}>
                  {propertiesByType.map((_, i) => (
                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : <EmptyChart message="برای این مشاور ملکی ثبت نشده است." />}
      </ChartCard>
    </>
  );
}

export { ConsultantAnalyticsSection };
