import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { Page, Role, Property, Listing, FollowUp, ConsultantItem, BadgeV, FollowUpCreatePayload } from "../../../shared/lib/types";
import { fmtShort, toPersianType, toPersianDeal, toPersianPropertyStatus, toPersianTaskStatus, toPersianTaskType, toPersianPriority, toPersianChannel, propertyStatusToUI, toPersianFollowupType, toPersianListingStatus, isFollowUpOverdue, isTaskOverdue } from "../../../shared/lib/utils";
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
import { statusBadge } from "../../../shared/components/ui/StatusBadge";
import { formatJalali, formatJalaliDT, formatJalaliDateTime } from "../../../shared/lib/jdate";
import { TaskDetailModal } from "../../../shared/components/TaskDetailModal";
import { PIE_COLORS, CHART_COLORS } from "../../../shared/lib/constants";
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

function ConsultantDashboard({ navigate, tasks, followups, userName, consultantId, kpis, recentActivities = [], onSaveTask, onDeleteTask, myReport = null, propertyComposition = [] }: { 
  navigate: (p: Page) => void; 
  tasks: any[]; 
  followups: FollowUp[]; 
  userName: string;
  consultantId: string | null;
  kpis: { properties: number; listings: number; openTasks: number };
  recentActivities?: Array<{ id: number; userName: string; action: string; actionLabel?: string; description: string; createdAt: string }>;
  onSaveTask?: (id: string, patch: Record<string, any>) => Promise<void>;
  onDeleteTask?: (id: string) => Promise<void>;
  myReport?: { kpis?: Record<string, any>; charts?: Record<string, any> } | null;
  propertyComposition?: Array<{ name: string; value: number; count: number; percentage: number }>;
}) {
  const [selectedTask, setSelectedTask] = useState<any | null>(null);
  const myTasks = tasks
    .filter((t) => String(t.assigneeId) === String(consultantId))
    .slice()
    .sort((a, b) => Number(isTaskOverdue(b)) - Number(isTaskOverdue(a)));
  const myFUs = followups
    .filter((f) => String(f.consultantId) === String(consultantId))
    .slice()
    .sort((a, b) => Number(isFollowUpOverdue(b)) - Number(isFollowUpOverdue(a)));
  const overdueTasksCount = myTasks.filter((t) => isTaskOverdue(t)).length;
  const overdueFollowupsCount = myFUs.filter((f) => isFollowUpOverdue(f)).length;
  const upcomingFollowupsCount = myFUs.filter((f) => f.status === "scheduled" && !isFollowUpOverdue(f)).length;
  const mix = (propertyComposition || []).map((item) => ({
    name: item.name,
    value: item.count ?? item.value ?? 0,
    percentage: item.percentage,
  }));
  const performance = myReport?.charts?.performanceProfile || [];
  const monthly = (myReport?.charts?.monthlyActivity || []).map((m: any) => ({
    ...m,
    label: m.label || m.month,
  }));
  const hasMonthly = monthly.some((m: any) => (m.tasksCompleted || 0) + (m.followups || 0) + (m.listings || 0) > 0);
  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold tracking-tight">سلام، {userName} 👋</h1><p className="text-sm text-muted-foreground mt-0.5">نمای کلی فضای کاری شما در امروز</p></div>
        <div className="flex gap-2"><Btn variant="secondary" size="sm" onClick={() => navigate("add-property")}><Plus size={13} />افزودن ملک</Btn><Btn variant="primary" size="sm" onClick={() => navigate("create-followup")}><Plus size={13} />ثبت پیگیری</Btn></div>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard label="املاک من" value={kpis.properties.toLocaleString("fa-IR")} icon={<Building2 size={16} />} color="bg-primary/10 text-primary" />
        <KpiCard label="آگهی‌های فعال" value={kpis.listings.toLocaleString("fa-IR")} icon={<FileText size={16} />} color="bg-blue-50 text-blue-600" />
        <KpiCard label="وظایف باز" value={kpis.openTasks.toLocaleString("fa-IR")} icon={<CheckSquare size={16} />} color="bg-amber-50 text-amber-600" />
        <KpiCard label="پیگیری‌های پیش‌رو" value={upcomingFollowupsCount.toLocaleString("fa-IR")} icon={<BellRing size={16} />} color="bg-emerald-50 text-emerald-600" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card className="p-5">
          <h2 className="text-sm font-semibold mb-1">ترکیب املاک من</h2>
          <p className="text-xs text-muted-foreground mb-4">توزیع املاک در دسترس شما بر اساس نوع</p>
          {mix.length === 0 ? (
            <p className="py-10 text-center text-xs text-muted-foreground">هنوز ملکی برای شما ثبت نشده است.</p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={140}>
                <PieChart>
                  <Pie data={mix} cx="50%" cy="50%" innerRadius={38} outerRadius={60} dataKey="value" stroke="none">
                    {mix.map((d, i) => (
                      <Cell key={d.name} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} formatter={(value: any, _n: any, props: any) => [`${value} ملک`, props.payload.name]} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5 mt-1">
                {mix.slice(0, 5).map((item, idx) => (
                  <div key={item.name} className="flex items-center gap-2 text-xs">
                    <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: PIE_COLORS[idx % PIE_COLORS.length] }} />
                    <span className="flex-1 text-muted-foreground truncate">{item.name}</span>
                    <span className="font-semibold">{item.percentage}٪ • {item.value}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
        <Card className="p-5">
          <h2 className="text-sm font-semibold mb-1">پروفایل عملکرد</h2>
          <p className="text-xs text-muted-foreground mb-4">امتیاز واقعی شما در تکمیل، به‌موقع بودن، پیگیری و پوشش آگهی</p>
          {performance.length === 0 ? (
            <p className="py-10 text-center text-xs text-muted-foreground">هنوز داده عملکردی ثبت نشده است.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <RadarChart data={performance} cx="50%" cy="50%" outerRadius="58%">
                <PolarGrid stroke="#E5E7EB" />
                <PolarAngleAxis dataKey="metric" tick={<PerformanceRadarTick />} tickLine={false} />
                <Radar dataKey="score" name="امتیاز" stroke="#0BB68A" fill="#0BB68A" fillOpacity={0.35} strokeWidth={2} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
              </RadarChart>
            </ResponsiveContainer>
          )}
          {hasMonthly && (
            <p className="text-[11px] text-muted-foreground mt-2">
              ۶ ماه اخیر: {monthly.reduce((s: number, m: any) => s + (m.tasksCompleted || 0), 0).toLocaleString("fa-IR")} وظیفه تکمیل‌شده
              {" · "}
              {monthly.reduce((s: number, m: any) => s + (m.followups || 0), 0).toLocaleString("fa-IR")} پیگیری
            </p>
          )}
        </Card>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-4">
          <Card className="p-5">
            <div className="flex items-center justify-between mb-3"><h2 className="text-sm font-semibold">وظایف من</h2><button onClick={() => navigate("my-tasks")} className="text-xs text-primary hover:underline">مشاهده همه</button></div>
            <div className="space-y-2.5">
              {myTasks.length === 0 ? <p className="text-xs text-muted-foreground">وظیفه‌ای ندارید.</p> : myTasks.slice(0, 4).map((t) => (
                <div key={t.id} className="flex items-center gap-3 py-2 border-b border-border last:border-0 cursor-pointer rounded-xl hover:bg-secondary/50 -mx-1 px-1 transition-colors" onClick={() => setSelectedTask(t)}>
                  <div className="flex-shrink-0">{t.status === "COMPLETED" ? <CheckCircle2 size={15} className="text-emerald-500" /> : <Circle size={15} className="text-muted-foreground" />}</div>
                  <div className="flex-1 min-w-0"><p className="text-xs font-semibold truncate">{t.title}</p><p className="text-xs text-muted-foreground">{t.taskType} · سررسید {formatJalali(t.due)}</p></div>
                  {isTaskOverdue(t) ? <Badge label="از تاریخ گذشته" variant="danger" /> : statusBadge(t.priority)}
                </div>
              ))}
            </div>
          </Card>
          <Card className="p-5">
            <div className="flex items-center justify-between mb-3"><h2 className="text-sm font-semibold">پیگیری‌های پیش‌رو</h2><button onClick={() => navigate("my-followups")} className="text-xs text-primary hover:underline">مشاهده همه</button></div>
            <div className="space-y-2.5">
              {myFUs.length === 0 ? <p className="text-xs text-muted-foreground">پیگیری‌ای ندارید.</p> : myFUs.map((fu) => (
                <div key={fu.id} className="flex items-center gap-3 py-2 border-b border-border last:border-0">
                  <div className={cx("w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 text-white", fu.type === "Call" ? "bg-blue-500" : fu.type === "Meeting" ? "bg-purple-500" : "bg-emerald-500")}>{fu.type === "Call" ? <Phone size={12} /> : fu.type === "Meeting" ? <Users size={12} /> : <Mail size={12} />}</div>
                  <div className="flex-1 min-w-0"><p className="text-xs font-semibold truncate">{fu.title}</p><p className="text-xs text-muted-foreground">{fu.contact} · {formatJalaliDT(fu.date)}</p></div>
                  {isFollowUpOverdue(fu) && <Badge label="از تاریخ گذشته" variant="danger" />}
                </div>
              ))}
            </div>
          </Card>
        </div>
        <div className="space-y-4">
          <Card className="p-4"><h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">عملیات سریع</h3>
            <div className="space-y-1">{[["افزودن ملک", "add-property" as Page, <Building2 size={13} />], ["ثبت پیگیری", "create-followup" as Page, <BellRing size={13} />], ["املاک من", "my-properties" as Page, <Building2 size={13} />], ["پروفایل من", "my-profile" as Page, <User size={13} />]].map(([l, p, icon]) => (<button key={l as string} onClick={() => navigate(p as Page)} className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl hover:bg-secondary transition-colors text-xs font-medium text-right"><span className="text-primary">{icon as React.ReactNode}</span>{l}</button>))}</div>
          </Card>
          <Card className="p-4"><h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">عملکرد من</h3>
            <div className="space-y-3">{([["کل وظایف", myTasks.length, false], ["تکمیل‌شده", myTasks.filter(t => t.status === "COMPLETED").length, false], ["وظیفه از تاریخ گذشته", overdueTasksCount, true], ["پیگیری پیش‌رو", upcomingFollowupsCount, false], ["پیگیری تکمیل‌شده", myFUs.filter(f => f.status === "completed").length, false], ["پیگیری از تاریخ گذشته", overdueFollowupsCount, true]] as [string, number, boolean][]).map(([k, v, danger]) => (<div key={k} className="flex justify-between items-center"><span className="text-xs text-muted-foreground">{k}</span><span className={cx("text-xs font-bold", danger && v > 0 && "text-red-600")}>{v.toLocaleString("fa-IR")}</span></div>))}</div>
          </Card>
          <Card className="p-4">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">فعالیت‌های اخیر</h3>
            <div className="space-y-2.5">
              {recentActivities.length === 0 ? (
                <p className="text-xs text-muted-foreground">هنوز فعالیتی ثبت نشده است.</p>
              ) : recentActivities.slice(0, 5).map((act) => {
                const when = formatJalaliDateTime(act.createdAt);
                return (
                  <div key={act.id} className="py-1.5 border-b border-border last:border-0">
                    <p className="text-xs font-semibold leading-relaxed line-clamp-2">{act.description}</p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">{act.userName} · {when.date}{when.time ? ` · ${when.time}` : ""}</p>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
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

export { ConsultantDashboard };
