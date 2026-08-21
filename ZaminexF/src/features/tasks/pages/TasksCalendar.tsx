import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { Page, Role, Property, Listing, FollowUp, ConsultantItem, BadgeV } from "../../../shared/lib/types";
import { fmtShort, toPersianType, toPersianDeal, toPersianPropertyStatus, toPersianTaskStatus, toPersianTaskType, toPersianPriority, toPersianChannel, propertyStatusToUI, toPersianFollowupType, toPersianListingStatus, isTaskOverdue } from "../../../shared/lib/utils";
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
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, ReferenceLine, ScatterChart, Scatter, ZAxis, RadialBarChart, RadialBar } from "recharts";
import { WEEKDAYS } from "../../../shared/lib/constants";
import { statusBadge } from "../../../shared/components/ui/StatusBadge";
import {
  gregorianToJalali,
  todayJalali,
  daysInJalaliMonth,
  firstWeekdayOfJalaliMonth,
  JALALI_MONTHS,
} from "../../../shared/lib/jdate";

const CALENDAR_DAY_PREVIEW = 2;
const faNum = (n: number) => n.toLocaleString("fa-IR", { useGrouping: false });

const CALENDAR_TONES = {
  completed: "bg-emerald-100 text-emerald-700",
  inProgress: "bg-blue-100 text-blue-700",
  pending: "bg-slate-100 text-slate-700",
  overdue: "bg-red-100 text-red-700",
  cancelled: "bg-slate-200 text-slate-500",
} as const;

const CALENDAR_LEGEND: { key: keyof typeof CALENDAR_TONES; label: string; dot: string }[] = [
  { key: "pending", label: "در انتظار انجام", dot: "bg-slate-400" },
  { key: "inProgress", label: "در حال انجام", dot: "bg-blue-500" },
  { key: "completed", label: "تکمیل‌شده", dot: "bg-emerald-500" },
  { key: "overdue", label: "از تاریخ گذشته", dot: "bg-red-500" },
  { key: "cancelled", label: "لغوشده", dot: "bg-slate-500" },
];

function calendarTaskTone(task: { status?: string; isOverdue?: boolean; due?: string; due_date?: string }): string {
  const status = String(task.status || "").toUpperCase();
  if (status === "COMPLETED") return CALENDAR_TONES.completed;
  if (status === "CANCELLED") return CALENDAR_TONES.cancelled;
  if (isTaskOverdue(task)) return CALENDAR_TONES.overdue;
  if (status === "IN_PROGRESS") return CALENDAR_TONES.inProgress;
  return CALENDAR_TONES.pending;
}

function TasksCalendar({ tasks }: { tasks: any[] }) {
  const t = todayJalali();
  const [viewYear, setViewYear] = useState(t.jy);
  const [viewMonth, setViewMonth] = useState(t.jm);
  const [dayModal, setDayModal] = useState<{ day: number; tasks: any[] } | null>(null);
  const [emptyNotice, setEmptyNotice] = useState<string | null>(null);
  const emptyNoticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const daysInMonth = daysInJalaliMonth(viewYear, viewMonth);
  const startOffset = firstWeekdayOfJalaliMonth(viewYear, viewMonth);

  const monthLabel = `${JALALI_MONTHS[viewMonth - 1]} ${faNum(viewYear)}`;

  const prevMonth = () => {
    if (viewMonth === 1) {
      setViewMonth(12);
      setViewYear(viewYear - 1);
    } else setViewMonth(viewMonth - 1);
  };
  const nextMonth = () => {
    if (viewMonth === 12) {
      setViewMonth(1);
      setViewYear(viewYear + 1);
    } else setViewMonth(viewMonth + 1);
  };

  // Place each task on the real Jalali day of its due date (stored Gregorian).
  const tasksByDay: Record<number, any[]> = {};
  const seen = new Set<string>();
  (tasks || []).forEach((task: any) => {
    const key = String(task.id || "");
    if (!task.due || seen.has(key)) return;
    seen.add(key);
    const j = gregorianToJalali(task.due);
    if (!j) return;
    if (j.jy !== viewYear || j.jm !== viewMonth) return;
    tasksByDay[j.jd] = [...(tasksByDay[j.jd] || []), task];
  });

  const todayKey = `${t.jy}-${t.jm}-${t.jd}`;

  const weekdayOf = (day: number) => WEEKDAYS[(startOffset + day - 1) % 7];

  const openDay = (day: number, dayTasks: any[]) => {
    if (!dayTasks.length) {
      if (emptyNoticeTimer.current) clearTimeout(emptyNoticeTimer.current);
      setEmptyNotice("وظیفه‌ای برای این روز ثبت نشده است.");
      emptyNoticeTimer.current = setTimeout(() => setEmptyNotice(null), 5000);
      return;
    }
    setEmptyNotice(null);
    setDayModal({ day, tasks: dayTasks });
  };

  useEffect(() => () => {
    if (emptyNoticeTimer.current) clearTimeout(emptyNoticeTimer.current);
  }, []);

  // Build grid cells for the Jalali month.
  const totalCells = Math.ceil((startOffset + daysInMonth) / 7) * 7;
  const cells = Array.from({ length: totalCells }, (_, idx) => {
    const day = idx - startOffset + 1;
    const inMonth = day >= 1 && day <= daysInMonth;
    const dayTasks = inMonth ? (tasksByDay[day] || []) : [];
    const isToday =
      inMonth && `${viewYear}-${viewMonth}-${day}` === todayKey;
    return { key: idx, day, inMonth, dayTasks, isToday };
  });

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">تقویم وظایف</h1>
        <div className="flex items-center gap-1 bg-white border border-border rounded-xl px-2 py-1">
          <button onClick={prevMonth} className="p-1.5 hover:bg-secondary rounded-lg">
            <ChevronRight size={14} />
          </button>
          <span className="text-sm font-semibold px-2">{monthLabel}</span>
          <button onClick={nextMonth} className="p-1.5 hover:bg-secondary rounded-lg">
            <ChevronLeft size={14} />
          </button>
        </div>
      </div>

      <Card className="p-3.5 mb-4">
        <div className="flex flex-wrap items-center gap-2">
          {CALENDAR_LEGEND.map((item) => (
            <span key={item.key} className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <span className={cx("w-2.5 h-2.5 rounded-full flex-shrink-0", item.dot)} />
              {item.label}
            </span>
          ))}
        </div>
        <p className="text-[11px] text-muted-foreground mt-2 leading-relaxed">
          رنگ هر وظیفه وضعیت آن را نشان می‌دهد. اگر مهلت گذشته و هنوز انجام نشده باشد، کنار عنوان علامت «!» می‌آید. برای دیدن همه وظایف یک روز، روی همان روز کلیک کنید.
        </p>
      </Card>

      <Card className="overflow-hidden">
        <div className="grid grid-cols-7 border-b border-border">
          {WEEKDAYS.map((d: string) => (
            <div key={d} className="py-2.5 text-center text-xs font-semibold text-muted-foreground border-r last:border-r-0 border-border">
              {d}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7">
          {cells.map(({ key, day, inMonth, dayTasks, isToday }) => (
            <div
              key={key}
              role={inMonth ? "button" : undefined}
              tabIndex={inMonth ? 0 : undefined}
              onClick={() => inMonth && openDay(day, dayTasks)}
              onKeyDown={(e) => {
                if (!inMonth) return;
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  openDay(day, dayTasks);
                }
              }}
              className={cx(
                "min-h-24 border-b border-r last:border-r-0 border-border p-1.5",
                !inMonth && "bg-secondary/20",
                isToday && "bg-primary/[0.04]",
                inMonth && "cursor-pointer hover:bg-secondary/30 transition-colors"
              )}
            >
              {inMonth && (
                <>
                  <div
                    className={cx(
                      "w-6 h-6 rounded-full flex items-center justify-center text-xs mb-1 font-medium",
                      isToday ? "bg-primary text-white font-bold" : "text-foreground"
                    )}
                  >
                    {day.toLocaleString("fa-IR")}
                  </div>
                  {dayTasks.slice(0, CALENDAR_DAY_PREVIEW).map((task: any) => (
                    <div
                      key={task.id}
                      className={cx("flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-lg mb-0.5 font-medium", calendarTaskTone(task))}
                    >
                      <span className="truncate min-w-0 flex-1">{(task.title || "").slice(0, 16)}</span>
                      {isTaskOverdue(task) ? <span className="flex-shrink-0 font-bold leading-none">!</span> : null}
                    </div>
                  ))}
                  {dayTasks.length > CALENDAR_DAY_PREVIEW && (
                    <p className="text-[10px] text-muted-foreground px-1 mt-0.5">
                      +{(dayTasks.length - CALENDAR_DAY_PREVIEW).toLocaleString("fa-IR")} مورد دیگر
                    </p>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      </Card>

      {emptyNotice && (
        <div className="fixed bottom-6 left-6 z-[60] flex items-center gap-3 px-4 py-3 rounded-xl border border-blue-200 bg-white shadow-lg text-sm font-medium min-w-72">
          <Info size={15} className="text-blue-600 flex-shrink-0" />
          <span>{emptyNotice}</span>
        </div>
      )}

      {dayModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm p-4" onClick={() => setDayModal(null)}>
          <Card className="w-full max-w-md shadow-2xl overflow-hidden max-h-[85vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-3 p-5 border-b border-border flex-shrink-0">
              <div>
                <p className="text-xs text-muted-foreground mb-0.5">وظایف روز</p>
                <h3 className="text-base font-semibold">
                  {`${weekdayOf(dayModal.day)} ${faNum(dayModal.day)} ${JALALI_MONTHS[viewMonth - 1]} ${faNum(viewYear)}`}
                </h3>
                <p className="text-xs text-muted-foreground mt-1">
                  {dayModal.tasks.length.toLocaleString("fa-IR")} وظیفه
                </p>
              </div>
              <button type="button" onClick={() => setDayModal(null)} className="p-1.5 hover:bg-secondary rounded-lg transition-colors flex-shrink-0">
                <X size={15} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-2">
              {dayModal.tasks.map((task: any) => (
                <div key={task.id} className="flex items-start justify-between gap-3 px-3 py-3 rounded-xl hover:bg-secondary/50">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold leading-snug">{task.title || "—"}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      مشاور: {task.assignee || task.assigned_to_detail?.name || "واگذار نشده"}
                    </p>
                  </div>
                  <div className="flex-shrink-0">{statusBadge(task.status)}</div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

// =============================================================================
//  Consultants Page
// =============================================================================

// =============================================================================
//  Consultant Analytics (detail-page reports)
// =============================================================================

export { TasksCalendar };
