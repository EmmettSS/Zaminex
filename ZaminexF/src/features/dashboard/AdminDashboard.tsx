import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../shared/lib/utils";
import { Page, Role, Property, Listing, FollowUp, ConsultantItem, BadgeV } from "../../shared/lib/types";
import { fmtShort, toPersianType, toPersianDeal, toPersianPropertyStatus, toPersianTaskStatus, toPersianTaskType, toPersianPriority, toPersianChannel, propertyStatusToUI, toPersianFollowupType, isFollowUpOverdue, isTaskOverdue } from "../../shared/lib/utils";
import { Badge } from "../../shared/components/ui/Badge";
import { Btn } from "../../shared/components/ui/Btn";
import { Input } from "../../shared/components/ui/Input";
import { Card } from "../../shared/components/ui/Card";
import { SelectField } from "../../shared/components/ui/SelectField";
import { ProfileAvatar } from "../../shared/components/ui/ProfileAvatar";
import { KpiCard } from "../../shared/components/ui/KpiCard";
import { EmptyState } from "../../shared/components/ui/EmptyState";
import { PageHeader } from "../../shared/components/ui/PageHeader";
import { ConfirmModal } from "../../shared/components/ConfirmModal";
import { ActionMenu } from "../../shared/components/ActionMenu";
import { Pagination } from "../../shared/components/Pagination";
import { BulkActionBar } from "../../shared/components/BulkActionBar";
import { PropertyCombobox } from "../../shared/components/ui/PropertyCombobox";
import { ConsultantCombobox } from "../../shared/components/ui/ConsultantCombobox";
import { DistrictCombobox } from "../../shared/components/ui/DistrictCombobox";
import { apiFetch, readJson, apiErrorMessage, getCsrfToken } from "../../shared/lib/apiClient";
import { toast } from "../../shared/lib/utils";
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, ReferenceLine, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, PieChart as RechartsPieChart } from "recharts";
import { Building2, FileText, CheckSquare, BellRing, Users, Activity, Settings, Plus, RefreshCw, Eye, Edit2, Trash2, Archive, Clock, MapPin, Check, X, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, SlidersHorizontal, ArrowUpRight, LayoutGrid, List, Download, Search, MoreVertical, Phone, Mail, Calendar, TrendingUp, Star, Shield, Lock, Key, Send, Loader2, AlertTriangle, Info, XCircle, CheckCircle2, TriangleAlert, Columns, MessageSquare, Sparkles, GripVertical, Building, History, Flame, Image, Zap, LayoutDashboard, Command, Filter, Award, BarChart3, Layers } from "lucide-react";
import { PIE_COLORS, CHART_COLORS } from "../../shared/lib/constants";
import { formatJalali, formatJalaliDT, formatJalaliDateTime } from "../../shared/lib/jdate";
import { TaskDetailModal } from "../../shared/components/TaskDetailModal";
function AdminDashboard({
  kpis,
  navigate,
  onRefresh,
  topConsultants = [],
  recentActivities = [],
  upcomingFollowups = [],
  tasks = [],
  revenueMonthly = [],
  revenueDealTypes = [],
  propertyComposition = [],
  hotProperties = [],
  properties = [],
  onSaveTask,
  onDeleteTask,
}: {
  kpis: { totalProperties: number; activeListings: number; openTasks: number; followUpsDue: number; consultants: number; consultantsActive: number };
  navigate: (p: Page) => void;
  onRefresh: () => void;
  topConsultants?: Array<{ fullName?: string; branch?: string; closedDealsCount?: number; completedWorkCount?: number; overdueWorkCount?: number; headlineValue?: number; headlineLabel?: string; tasksOverdueCount?: number; tenureDays?: number; profile_image?: string | null }>;
  recentActivities?: Array<{ id: number; userName: string; action: string; actionLabel?: string; description: string; createdAt: string }>;
  upcomingFollowups?: Array<FollowUp>;
  tasks?: any[];
  revenueMonthly?: Array<{ month: string; revenue: number; count?: number; total?: number; dealVolumes?: Record<string, number> }>;
  revenueDealTypes?: Array<{ name: string; label: string }>;
  propertyComposition?: Array<{ name: string; value: number; count: number; percentage: number }>;
  hotProperties?: Array<{ id?: number; title?: string; neighborhood?: string; engagementHeatScore?: number; daysOnMarket?: number | null }>;
  properties?: Property[];
  onSaveTask?: (id: string, patch: Record<string, any>) => Promise<void>;
  onDeleteTask?: (id: string) => Promise<void>;
}) {
  const [selectedTask, setSelectedTask] = useState<any | null>(null);
  const computedComposition = useMemo(() => {
    if (propertyComposition && propertyComposition.length > 0) {
      const total = propertyComposition.reduce((sum, item) => sum + (item.count || item.value || 0), 0) || 1;
      return propertyComposition.map((item) => {
        const cnt = item.count ?? item.value ?? 0;
        const pct = item.percentage ?? Math.round((cnt / total) * 100 * 10) / 10;
        const persianName = toPersianType(item.name);
        return {
          name: persianName,
          value: cnt,
          count: cnt,
          percentage: pct,
        };
      });
    }

    const activeProperties = (properties || []).filter(
      (p) => String(p.propertyStatus || p.status || "").toUpperCase() !== "INACTIVE"
    );

    if (activeProperties.length === 0) {
      return [];
    }

    const typeCounts: Record<string, number> = {};
    activeProperties.forEach((p) => {
      const rawType = (p as any).propertyTypeDisplay || (p as any).propertyTypeName || toPersianType(p.type || (p as any).propertyType);
      const name = rawType && rawType !== "—" ? rawType : "سایر";
      typeCounts[name] = (typeCounts[name] || 0) + 1;
    });

    const total = activeProperties.length;
    return Object.entries(typeCounts)
      .map(([name, count]) => {
        const percentage = Math.round((count / total) * 100 * 10) / 10;
        return {
          name,
          value: count,
          count,
          percentage,
        };
      })
      .sort((a, b) => b.count - a.count);
  }, [propertyComposition, properties]);

  const revenueData = useMemo(() => revenueMonthly || [], [revenueMonthly]);
  const dealTypes = useMemo(() => revenueDealTypes || [], [revenueDealTypes]);
  const hasRevenue = revenueData.some((m) => (m.revenue || 0) > 0 || (m.count || 0) > 0);

  // `upcomingFollowups` already arrives sorted (overdue first, then newest
  // activity, with a stable id tie-breaker) and trimmed to five. Re-sorting it
  // here by the overdue flag alone would discard that recency order, so the
  // list is rendered exactly as received.
  const overdueTasks = useMemo(
    () => tasks.filter((t) => isTaskOverdue(t)),
    [tasks]
  );

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">سلام، خوش آمدید</h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-sm text-muted-foreground">نمایی کلی از عملکرد سازمان در روز جاری</p>
            <span className="flex items-center gap-1 text-xs text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />بروزرسانی زنده</span>
          </div>
        </div>
        <div className="flex gap-2"><Btn variant="primary" size="sm" onClick={() => navigate("add-property")}><Plus size={13} />افزودن ملک</Btn></div>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <KpiCard label="کل املاک" value={kpis.totalProperties.toLocaleString("fa-IR")} icon={<Building2 size={18} />} color="bg-blue-50 text-blue-600" />
        <KpiCard label="آگهی‌های فعال" value={kpis.activeListings.toLocaleString("fa-IR")} icon={<FileText size={18} />} color="bg-amber-50 text-amber-600" />
        <KpiCard label="وظایف باز" value={kpis.openTasks.toLocaleString("fa-IR")} icon={<CheckSquare size={18} />} color="bg-orange-50 text-orange-600" />
        <KpiCard label="پیگیری‌های پیش‌رو" value={kpis.followUpsDue.toLocaleString("fa-IR")} icon={<BellRing size={18} />} color="bg-purple-50 text-purple-600" />
        <KpiCard label="مشاوران" value={kpis.consultants.toLocaleString("fa-IR")} sub={`${kpis.consultantsActive} فعال`} icon={<Users size={18} />} color="bg-primary/10 text-primary" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 p-5">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-semibold">حجم معاملات بسته‌شده</h2><Badge label="به تفکیک نوع معامله — ۶ ماه شمسی" variant="muted" /></div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={revenueData} margin={{ top: 0, left: 0, right: -20, bottom: 0 }}>
              <defs>
                {dealTypes.length === 0 ? (
                  <linearGradient id="g-total" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#0BB68A" stopOpacity={0.15} /><stop offset="95%" stopColor="#0BB68A" stopOpacity={0} /></linearGradient>
                ) : (
                  dealTypes.map((dt, i) => {
                    const color = CHART_COLORS[i % CHART_COLORS.length];
                    return (
                      <linearGradient key={`g-${dt.name}`} id={`g-${dt.name}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={color} stopOpacity={0.18} />
                        <stop offset="95%" stopColor={color} stopOpacity={0} />
                      </linearGradient>
                    );
                  })
                )}
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.05)" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#9CA3AF" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#9CA3AF" }} axisLine={false} tickLine={false} tickFormatter={(v: any) => `${v} م`} />
              <Tooltip
                contentStyle={{ fontSize: 12, borderRadius: 12, border: "1px solid rgba(0,0,0,0.08)" }}
                formatter={(value: any, name: any) => [`${Number(value || 0).toLocaleString("fa-IR")} میلیارد تومان`, name]}
              />
              {dealTypes.length === 0 ? (
                <Area type="monotone" dataKey="revenue" stroke="#0BB68A" strokeWidth={2.5} fill="url(#g-total)" dot={false} name="ارزش کل معاملات" />
              ) : (
                dealTypes.map((dt, i) => (
                  <Area
                    key={dt.name}
                    type="monotone"
                    dataKey={(row: any) => row.dealVolumes?.[dt.name] ?? 0}
                    stroke={CHART_COLORS[i % CHART_COLORS.length]}
                    strokeWidth={2}
                    fill={`url(#g-${dt.name})`}
                    fillOpacity={1}
                    dot={false}
                    name={dt.label}
                  />
                ))
              )}
            </AreaChart>
          </ResponsiveContainer>
          {dealTypes.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 justify-center">
              {dealTypes.map((dt, i) => (
                <span key={dt.name} className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }} />
                  {dt.label}
                </span>
              ))}
            </div>
          )}
          <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
            {revenueData.slice(-3).map((m: any) => (
              <div key={m.month} className="p-2 bg-secondary rounded-xl">
                <p className="text-muted-foreground">{m.month}</p>
                <p className="font-semibold">
                  {(m.revenue ?? 0).toLocaleString("fa-IR")} میلیارد
                  <span className="text-muted-foreground font-normal"> • {(m.count ?? 0).toLocaleString("fa-IR")} معامله</span>
                </p>
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="text-sm font-semibold mb-1">ترکیب املاک</h2>
          <p className="text-xs text-muted-foreground mb-4">توزیع بر اساس نوع ملک</p>
          {computedComposition.length === 0 ? (
            <div className="py-12 text-center text-xs text-muted-foreground">
              هنوز ملکی در سیستم ثبت نشده است.
            </div>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={140}>
                <RechartsPieChart>
                  <Pie 
                    data={computedComposition} 
                    cx="50%" 
                    cy="50%" 
                    innerRadius={38} 
                    outerRadius={60} 
                    dataKey="value" 
                    stroke="none"
                  >
                    {computedComposition.map((d: any, i: number) => (
                      <Cell key={`mix-${d.name}`} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} formatter={(value: any, name: any, props: any) => [`${value} ملک (${props.payload.percentage || ''}٪)`, props.payload.name || name]} />
                </RechartsPieChart>
              </ResponsiveContainer>
              <div className="space-y-2 mt-1">
                {computedComposition.slice(0, 6).map((item: any, idx: number) => {
                  const color = PIE_COLORS[idx % PIE_COLORS.length];
                  return (
                    <div key={item.name} className="flex items-center gap-2 text-xs">
                      <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
                      <span className="flex-1 text-muted-foreground truncate">{item.name}</span>
                      <span className="font-semibold">{item.percentage}٪ • {item.count} عدد</span>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </Card>
      </div>
      <Card className="p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-semibold">املاک پرتعامل</h2>
            <p className="text-xs text-muted-foreground mt-0.5">بیشترین پیگیری و وظیفه در ۳۰ روز اخیر</p>
          </div>
          <button onClick={() => navigate("properties")} className="text-xs text-primary hover:underline">مشاهده همه</button>
        </div>
        {hotProperties.length === 0 ? (
          <p className="text-xs text-muted-foreground">هنوز تعامل ثبت‌شده‌ای روی املاک نیست.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {hotProperties.map((p) => (
              <button
                key={String(p.id)}
                type="button"
                onClick={() => p.id != null && navigate("property-detail", p.id)}
                className="text-right p-3 rounded-xl bg-secondary/70 hover:bg-secondary transition-colors"
              >
                <p className="text-xs font-semibold truncate">{p.title}</p>
                <p className="text-[10px] text-muted-foreground truncate mt-0.5">{p.neighborhood}</p>
                <p className="text-[11px] font-bold text-emerald-600 mt-1.5">{(p.engagementHeatScore ?? 0).toLocaleString("fa-IR")} امتیاز تعامل</p>
              </button>
            ))}
          </div>
        )}
      </Card>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="p-5">
          <div className="flex items-center justify-between mb-3"><h2 className="text-sm font-semibold">مشاوران برتر</h2><button onClick={() => navigate("consultants")} className="text-xs text-primary hover:underline">مشاهده همه</button></div>
          <div className="space-y-3">
            {topConsultants.length === 0 ? (
              <p className="text-xs text-muted-foreground">برای مشاهده رتبه‌بندی به صفحه مشاوران بروید.</p>
            ) : (
              topConsultants.map((c, i) => (
                <div key={`${c.fullName}-${i}`} className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-xs font-mono text-muted-foreground w-4">{(i + 1).toLocaleString("fa-IR")}</span>
                    <ProfileAvatar imageUrl={c.profile_image} initials={(c.fullName || "?").split(" ").map((w) => w[0]).join("").slice(0, 2)} size="xs" />
                    <div className="min-w-0">
                      <p className="text-xs font-semibold truncate">{c.fullName}</p>
                      <p className="text-[10px] text-muted-foreground truncate">{c.branch}</p>
                    </div>
                  </div>
                  <div className="text-left flex-shrink-0">
                    <p className="text-xs font-bold text-emerald-600">{(c.headlineValue ?? 0).toLocaleString("fa-IR")}</p>
                    <p className="text-[10px] text-muted-foreground">{c.headlineLabel || "کارهای تکمیل‌شده"}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center justify-between mb-3"><h2 className="text-sm font-semibold">فعالیت‌های اخیر</h2><button onClick={() => navigate("activity")} className="text-xs text-primary hover:underline">مشاهده همه</button></div>
          <div className="space-y-3">
            {recentActivities.length === 0 ? (
              <p className="text-xs text-muted-foreground">هنوز فعالیتی ثبت نشده است.</p>
            ) : (
              recentActivities.slice(0, 5).map((act) => {
                const actionColors: Record<string, string> = {
                  create: "bg-emerald-100 text-emerald-600",
                  update: "bg-blue-100 text-blue-600",
                  status_change: "bg-purple-100 text-purple-600",
                  complete: "bg-emerald-100 text-emerald-600",
                  archive: "bg-amber-100 text-amber-600",
                  delete: "bg-red-100 text-red-600",
                  approve: "bg-teal-100 text-teal-600",
                };
                const actionIcons: Record<string, React.ReactNode> = {
                  create: <Plus size={11} />,
                  update: <Edit2 size={11} />,
                  status_change: <RefreshCw size={11} />,
                  complete: <Check size={11} />,
                  archive: <Archive size={11} />,
                  delete: <Trash2 size={11} />,
                  approve: <CheckCircle2 size={11} />,
                };
                const when = formatJalaliDateTime(act.createdAt);
                return (
                  <div key={act.id} className="flex items-start gap-2.5">
                    <div className={cx("w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5", actionColors[act.action] || "bg-secondary text-muted-foreground")}>
                      {actionIcons[act.action] || <Activity size={11} />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-foreground leading-relaxed line-clamp-2">{act.description}</p>
                      <p className="text-[10px] text-muted-foreground mt-0.5">{act.userName} · {when.date}{when.time ? ` · ${when.time}` : ""}</p>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center justify-between mb-3"><h2 className="text-sm font-semibold">پیگیری‌های پیش‌رو</h2><button onClick={() => navigate("follow-ups")} className="text-xs text-primary hover:underline">مشاهده همه</button></div>
          <div className="space-y-3">
            {upcomingFollowups.length === 0 && overdueTasks.length === 0 ? (
              <p className="text-xs text-muted-foreground">پیگیری زمان‌بندی‌شده‌ای وجود ندارد.</p>
            ) : (
              <>
                {upcomingFollowups.map((fu) => (
                  <div key={fu.id} className="flex items-center gap-2.5">
                    <div className={cx("w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 text-white", fu.type === "Call" ? "bg-blue-500" : fu.type === "Meeting" ? "bg-purple-500" : fu.type === "Email" ? "bg-slate-400" : "bg-emerald-500")}>
                      {fu.type === "Call" ? <Phone size={12} /> : fu.type === "Meeting" ? <Users size={12} /> : fu.type === "Email" ? <Mail size={12} /> : <MapPin size={12} />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold truncate">{fu.title}</p>
                      <p className="text-[10px] text-muted-foreground truncate">{fu.contact} · {formatJalaliDT(fu.date)}</p>
                    </div>
                    {isFollowUpOverdue(fu) && <Badge label="از تاریخ گذشته" variant="danger" />}
                  </div>
                ))}
                {overdueTasks.slice(0, 3).map((t) => (
                  <div key={`task-${t.id}`} className="flex items-center gap-2.5 cursor-pointer rounded-xl hover:bg-secondary/60 -mx-1 px-1 py-0.5 transition-colors" onClick={() => setSelectedTask(t)}>
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 bg-red-500 text-white">
                      <CheckSquare size={12} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold truncate">{t.title}</p>
                      <p className="text-[10px] text-muted-foreground truncate">{t.taskType || "وظیفه"} · سررسید {formatJalali(t.due || t.due_date)}</p>
                    </div>
                    <Badge label="از تاریخ گذشته" variant="danger" />
                  </div>
                ))}
              </>
            )}
          </div>
        </Card>
      </div>
      {selectedTask && (
        <TaskDetailModal
          task={selectedTask}
          onClose={() => setSelectedTask(null)}
          onSave={onSaveTask ? async (patch) => { await onSaveTask(String(selectedTask.id), patch); } : undefined}
          onDelete={onDeleteTask ? async () => { await onDeleteTask(String(selectedTask.id)); } : undefined}
        />
      )}
    </div>
  );
}

// =============================================================================
//  Properties Page
// =============================================================================

const formatPriceDeviation = (idx?: number | null) => {
  if (idx == null || Number.isNaN(idx)) return "—";
  const pct = idx * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}٪ نسبت به میانگین محله`;
};

const delegationLabel = (code?: string | null) => {
  const map: Record<string, string> = {
    DELEGATED: "تفویض‌شده (تیمی)",
    SELF_MANAGED: "مدیریت شخصی",
    UNASSIGNED: "هنوز واگذار نشده",
  };
  return map[code || ""] || "—";
};

export { AdminDashboard };
