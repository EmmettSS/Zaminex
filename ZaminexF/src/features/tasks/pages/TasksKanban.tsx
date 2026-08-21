import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { fuzzyFilter, fuzzyMatch } from "../../../shared/lib/fuzzySearch";
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
import { statusBadge } from "../../../shared/components/ui/StatusBadge";
import { TaskDetailModal } from "../../../shared/components/TaskDetailModal";
import { JalaliDateInput } from "../../../shared/components/ui/JalaliDateInput";
import { formatJalali } from "../../../shared/lib/jdate";
function TasksKanban({
  tasks,
  loading,
  consultants,
  properties,
  onCreate,
  onStatusChange,
  onSave,
  onDelete,
  currentUserId,
  role,
  taskTypesList = [],
  initialCreateOpen = false,
  onCreateDismiss,
}: {
  tasks: any[];
  loading: boolean;
  consultants: any[];
  properties: Property[];
  onCreate: (payload: any) => Promise<void>;
  onStatusChange: (id: string, status: string) => Promise<void>;
  onSave: (id: string, patch: Record<string, any>) => Promise<void>;
  currentUserId?: string | null;
  role?: Role;
  onDelete: (id: string) => Promise<void>;
  taskTypesList?: Array<{ value: string; label: string }>;
  initialCreateOpen?: boolean;
  onCreateDismiss?: () => void;
}) {
  const [createOpen, setCreateOpen] = useState(initialCreateOpen);
  const closeCreate = () => {
    setCreateOpen(false);
    onCreateDismiss?.();
  };
  const [confirmDeleteTask, setConfirmDeleteTask] = useState<string | null>(null);
  const [selectedTask, setSelectedTask] = useState<any | null>(null);
  const [search, setSearch] = useState("");
  const [newTask, setNewTask] = useState({ 
    title: "", 
    description: "", 
    priority: "MEDIUM", 
    taskType: "VIEWING", 
    assignee: currentUserId || "", 
    propertyId: "", 
    due: "", 
    status: "PENDING" 
  });

  const [showFilter, setShowFilter] = useState(false);
  const [taskFilters, setTaskFilters] = useState({
    statuses: [] as string[], 
    priorities: [] as string[], 
    assignees: [] as string[],
    properties: [] as string[], 
    taskTypes: [] as string[],
    dueDateFrom: "", 
    dueDateTo: "", 
    completionStatus: "",
  });

  const toggleMulti = (key: "statuses" | "priorities" | "assignees" | "properties" | "taskTypes", val: string) => {
    setTaskFilters((f) => ({ ...f, [key]: f[key].includes(val) ? f[key].filter((x) => x !== val) : [...f[key], val] }));
  };
  const clearFilters = () => {
    setTaskFilters({
      statuses: [],
      priorities: [],
      assignees: [],
      properties: [],
      taskTypes: [],
      dueDateFrom: "",
      dueDateTo: "",
      completionStatus: "",
    });
    setSearch("");
  };

  const hasActiveFilter = search.length > 0 || taskFilters.statuses.length > 0 || taskFilters.priorities.length > 0 || taskFilters.assignees.length > 0 || taskFilters.properties.length > 0 || taskFilters.taskTypes.length > 0 || taskFilters.dueDateFrom || taskFilters.dueDateTo || taskFilters.completionStatus;

  const filtered = useMemo(() => {
    let result = tasks || [];
    const q = search.trim();
    if (q) {
      result = fuzzyFilter(result, q, (t) => `${t.title || ""} ${t.description || ""} ${t.assignee || ""} ${t.assigned_to_detail?.name || ""} ${t.propertyTitle || ""} ${(t as any).property_detail?.title || ""}`);
    }
    return result.filter((t) => {
      if (taskFilters.statuses.length > 0 && !taskFilters.statuses.includes(t.status)) return false;
      if (taskFilters.priorities.length > 0 && !taskFilters.priorities.includes(t.priority)) return false;
      if (taskFilters.assignees.length > 0 && !taskFilters.assignees.includes(String(t.assigneeId || ""))) return false;
      if (taskFilters.properties.length > 0 && !taskFilters.properties.includes(String(t.propertyId || ""))) return false;
      if (taskFilters.taskTypes.length > 0 && !taskFilters.taskTypes.includes(t.task_type)) return false;
      if (taskFilters.completionStatus === "completed" && t.status !== "COMPLETED") return false;
      if (taskFilters.completionStatus === "open" && t.status === "COMPLETED") return false;
      if (taskFilters.dueDateFrom && t.due && t.due < taskFilters.dueDateFrom) return false;
      if (taskFilters.dueDateTo && t.due && t.due > taskFilters.dueDateTo) return false;
      return true;
    });
  }, [tasks, search, taskFilters]);

  const cols = [
    { id: "PENDING", label: "برای انجام", color: "bg-slate-400" },
    { id: "IN_PROGRESS", label: "در حال انجام", color: "bg-blue-500" },
    { id: "COMPLETED", label: "انجام‌شده", color: "bg-emerald-500" },
    { id: "CANCELLED", label: "لغوشده", color: "bg-red-400" },
  ];
  const move = async (tid: string, status: string) => { 
    try {
      await onStatusChange(tid, status);
      toast({ type: "success", message: `وظیفه به ${status} منتقل شد.` });
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطا در تغییر وضعیت" });
    }
  };
  const taskActions = (t: any) => [
    { label: "مشاهده و ویرایش", icon: <Edit2 size={12} />, onClick: () => setSelectedTask(t) },
    { label: "تکمیل سریع", icon: <Check size={12} />, onClick: () => move(String(t.id), "COMPLETED") },
    { label: "حذف", icon: <Trash2 size={12} />, onClick: () => setConfirmDeleteTask(String(t.id)), danger: true },
  ];

  const handleDeleteConfirm = async () => {
    const id = confirmDeleteTask;
    setConfirmDeleteTask(null);
    if (!id) return;
    try {
      await onDelete(id);
      toast({ type: "success", message: "وظیفه با موفقیت حذف شد." });
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطا در حذف وظیفه" });
    }
  };

  const assigneeProperties = useMemo(() => {
    if (!newTask.assignee) return properties;
    return properties.filter(
      (p) => String(p.consultantId ?? p.consultant ?? "") === String(newTask.assignee) || (p as any).isShared === true
    );
  }, [properties, newTask.assignee]);

  const handleCreate = async () => {
    if (!newTask.title.trim()) {
      toast({ type: "error", message: "عنوان وظیفه الزامی است." });
      return;
    }
    if (!newTask.due) {
      toast({ type: "error", message: "تاریخ سررسید الزامی است." });
      return;
    }
    if (!newTask.assignee) {
      toast({ type: "error", message: "انتخاب مشاور الزامی است." });
      return;
    }
    try {
      await onCreate({
        title: newTask.title,
        description: newTask.description,
        priority: newTask.priority,
        taskType: newTask.taskType,
        assignee: newTask.assignee,
        propertyId: newTask.propertyId || null,
        due: newTask.due,
        status: newTask.status,
      });
      setCreateOpen(false);
      setNewTask({ title: "", description: "", priority: "MEDIUM", taskType: "VIEWING", assignee: currentUserId || "", propertyId: "", due: "", status: "PENDING" });
      toast({ type: "success", message: "وظیفه با موفقیت ایجاد شد." });
      onCreateDismiss?.();
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطا در ایجاد وظیفه" });
    }
  };

  return (
    <div className="p-6 h-full flex flex-col">
      <div className="flex items-center gap-2 mb-5">
        <div className="flex-1">
          <h1 className="text-xl font-bold">مدیریت وظایف</h1>
          <p className="text-sm text-muted-foreground">
            {filtered.length.toLocaleString("fa-IR")} وظیفه در همه مشاوران
          </p>
        </div>

        <div className="relative flex-1 max-w-sm">
          <Search
            size={14}
            className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="جستجوی وظایف…"
            className="w-full pl-10 pr-3 py-2 text-sm rounded-xl border border-border bg-white outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <Btn
          variant="secondary"
          size="sm"
          onClick={() => setShowFilter(!showFilter)}
          className={hasActiveFilter || search ? "!border-primary !text-primary !bg-primary/5" : ""}
        >
          <SlidersHorizontal size={13} />
          فیلتر
          {hasActiveFilter && (
            <span className="w-4 h-4 rounded-full bg-primary text-white text-xs flex items-center justify-center">
              {[
                taskFilters.statuses.length,
                taskFilters.priorities.length,
                taskFilters.assignees.length,
                taskFilters.properties.length,
                taskFilters.taskTypes.length,
              ].reduce((s, n) => s + (n > 0 ? 1 : 0), 0)}
            </span>
          )}
        </Btn>

        {hasActiveFilter && (
          <button
            type="button"
            onClick={clearFilters}
            className="px-2.5 py-1 text-[10px] rounded-lg border text-red-500 border-red-200 bg-red-200 hover:bg-secondary hover:text-foreground transition-colors"
          >
            پاک کردن فیلترها
          </button>
        )}

        <Btn variant="primary" size="sm" onClick={() => setCreateOpen(true)}>
          <Plus size={13} />
          وظیفه جدید
        </Btn>
      </div>

      {/* Task Filter Panel */}
      {showFilter && (
        <Card className="p-4 mb-4 border border-border/80 shadow-sm bg-card rounded-2xl">
          <div className="flex items-center justify-between pb-3 mb-3 border-b border-border/60">
            <h3 className="text-xs font-semibold text-foreground/80">فیلترهای پیشرفته</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <label className="block text-[10px] font-medium text-muted-foreground mb-1">وضعیت</label>
              <select 
                value={taskFilters.statuses[0] || ""} 
                onChange={(e) => setTaskFilters(p => ({ ...p, statuses: e.target.value ? [e.target.value] : [] }))}
                className="w-full px-3 py-1.5 rounded-xl border border-border bg-white text-xs outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">همه وضعیت‌ها</option>
                <option value="PENDING">در انتظار انجام</option>
                <option value="IN_PROGRESS">در حال انجام</option>
                <option value="COMPLETED">تکمیل‌شده</option>
                <option value="CANCELLED">لغوشده</option>
              </select>
            </div>

            <div>
              <label className="block text-[10px] font-medium text-muted-foreground mb-1">اولویت</label>
              <select 
                value={taskFilters.priorities[0] || ""} 
                onChange={(e) => setTaskFilters(p => ({ ...p, priorities: e.target.value ? [e.target.value] : [] }))}
                className="w-full px-3 py-1.5 rounded-xl border border-border bg-white text-xs outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">همه اولویت‌ها</option>
                <option value="LOW">اولویت کم</option>
                <option value="MEDIUM">اولویت عادی</option>
                <option value="HIGH">اولویت بالا</option>
                <option value="URGENT">اولویت فوری</option>
              </select>
            </div>

            <div>
              <label className="block text-[10px] font-medium text-muted-foreground mb-1">مسئول</label>
              <MultiConsultantCombobox
                values={taskFilters.assignees || []}
                onChange={(selectedIds) => setTaskFilters((p) => ({ ...p, assignees: selectedIds }))}
                consultants={consultants}
              />
            </div>

            <div>
              <label className="block text-[10px] font-medium text-muted-foreground mb-1">ملک مرتبط</label>
              <MultiPropertyCombobox
                values={taskFilters.properties}
                onChange={(selectedIds) => setTaskFilters((p) => ({ ...p, properties: selectedIds }))}
                properties={properties}
              />
            </div>

            <div>
              <label className="block text-[10px] font-medium text-muted-foreground mb-1">نوع وظیفه</label>
              <select 
                value={taskFilters.taskTypes[0] || ""} 
                onChange={(e) => setTaskFilters(p => ({ ...p, taskTypes: e.target.value ? [e.target.value] : [] }))}
                className="w-full px-3 py-1.5 rounded-xl border border-border bg-white text-xs outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">همه انواع</option>
                {taskTypesList.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>

            <div>
              <label className="block text-[10px] font-medium text-muted-foreground mb-1">وضعیت تکمیل</label>
              <select 
                value={taskFilters.completionStatus} 
                onChange={(e) => setTaskFilters(p => ({ ...p, completionStatus: e.target.value }))}
                className="w-full px-3 py-1.5 rounded-xl border border-border bg-white text-xs outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">همه وظایف</option>
                <option value="open">وظایف باز</option>
                <option value="completed">وظایف تکمیل‌شده</option>
              </select>
            </div>

            <div>
              <label className="block text-[10px] font-medium text-muted-foreground mb-1">از تاریخ</label>
              <JalaliDateInput value={taskFilters.dueDateFrom} onChange={(v) => setTaskFilters(p => ({ ...p, dueDateFrom: v }))} />
            </div>

            <div>
              <label className="block text-[10px] font-medium text-muted-foreground mb-1">تا تاریخ</label>
              <JalaliDateInput value={taskFilters.dueDateTo} onChange={(v) => setTaskFilters(p => ({ ...p, dueDateTo: v }))} />
            </div>
          </div>
        </Card>
      )}

      <div className="flex gap-1 mb-5 flex-wrap">
        {cols.map((c) => { const count = filtered.filter((t) => t.status === c.id).length; return (<span key={c.id} className="flex items-center gap-1 px-2.5 py-1 bg-white border border-border rounded-full text-xs"><span className={cx("w-1.5 h-1.5 rounded-full", c.color)} />{c.label}: <strong>{count.toLocaleString("fa-IR")}</strong></span>); })}
        {hasActiveFilter && <span className="flex items-center gap-1 px-2.5 py-1 bg-primary/10 border border-primary/20 rounded-full text-xs text-primary font-medium"><SlidersHorizontal size={10} />فیلتر فعال — {filtered.length.toLocaleString("fa-IR")} نتیجه</span>}
      </div>
      <div className="flex gap-4 flex-1 overflow-x-auto pb-2">
        {loading ? (
          <div className="flex-1 text-center text-sm text-muted-foreground py-12">در حال بارگذاری وظایف…</div>
        ) : (
          cols.map((col) => {
            const colTasks = filtered.filter((t) => t.status === col.id);
            return (
              <div key={col.id} className="flex-shrink-0 w-72 flex flex-col">
                <div className="flex items-center gap-2 mb-3 px-1"><div className={cx("w-2.5 h-2.5 rounded-full", col.color)} /><span className="text-sm font-semibold">{col.label}</span><span className="ml-auto text-xs text-muted-foreground bg-white border border-border px-2 py-0.5 rounded-full font-semibold">{colTasks.length.toLocaleString("fa-IR")}</span></div>
                <div className="flex flex-col gap-2.5 flex-1">
                  {colTasks.map((task) => (
                    <Card key={task.id} className="p-3.5 cursor-pointer" onClick={() => setSelectedTask(task)}>
                      <div className="flex items-start justify-between gap-2 mb-2"><p className="text-xs font-semibold leading-snug flex-1">{task.title}</p><div onClick={(e) => e.stopPropagation()}><ActionMenu actions={taskActions(task)} /></div></div>
                      <div className="flex items-center gap-1.5 mb-2 flex-wrap">{statusBadge(task.priority)}{task.taskType && <Badge label={task.taskType} variant="muted" />}{isTaskOverdue(task) && <Badge label="از تاریخ گذشته" variant="danger" />}</div>
                      {task.description && <p className="text-xs text-muted-foreground mb-2.5 line-clamp-2">{task.description}</p>}
                      <div className="flex items-center justify-between text-xs text-muted-foreground"><div className="flex items-center gap-1"><Clock size={10} />{formatJalali(task.due)}</div><ProfileAvatar imageUrl={task.assigned_to_detail?.profile_image} initials={(task.assignee || "?").split(" ").map((w: string) => w[0]).join("").slice(0, 2)} size="xs" /></div>
                      {col.id !== "COMPLETED" && col.id !== "CANCELLED" && (
                        <div className="mt-2.5 pt-2.5 border-t border-border flex gap-2 flex-wrap">
                          {cols.filter((c) => c.id !== col.id && c.id !== "CANCELLED").map((c) => (<button key={c.id} onClick={(e) => { e.stopPropagation(); move(String(task.id), c.id); }} className="text-xs text-primary hover:underline">→ {c.label}</button>))}
                        </div>
                      )}
                    </Card>
                  ))}
                  <button onClick={() => setCreateOpen(true)} className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground px-2 py-2 rounded-xl hover:bg-secondary transition-colors border border-dashed border-border"><Plus size={12} />افزودن وظیفه</button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm p-4">
          <Card className="w-full max-w-xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between p-5 border-b border-border flex-shrink-0">
              <h3 className="text-base font-semibold">ایجاد وظیفه</h3>
              <button onClick={closeCreate} className="p-1.5 hover:bg-secondary rounded-lg transition-colors"><X size={15} /></button>
            </div>
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              <div className="space-y-3">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">جزئیات وظیفه</p>
                <Input label="عنوان" placeholder="مثال: هماهنگی بازدید ملک برای مشتری" value={newTask.title} onChange={(v) => setNewTask((p) => ({ ...p, title: v }))} required />
                <Input label="توضیحات" placeholder="شرح کامل این وظیفه…" value={newTask.description} onChange={(v) => setNewTask((p) => ({ ...p, description: v }))} textarea rows={3} />
              </div>
              <div className="space-y-3">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">دسته‌بندی</p>
                <div className="grid grid-cols-2 gap-3">
                  <SelectField label="نوع وظیفه" value={newTask.taskType} onChange={(v) => setNewTask((p) => ({ ...p, taskType: v }))} options={taskTypesList.map((t) => ({ label: t.label, value: t.value }))} />
                  <SelectField label="اولویت" value={newTask.priority} onChange={(v) => setNewTask((p) => ({ ...p, priority: v }))} options={["URGENT", "HIGH", "MEDIUM", "LOW"].map((p) => ({ label: toPersianPriority(p), value: p }))} />
                </div>
                <SelectField label="وضعیت اولیه" value={newTask.status} onChange={(v) => setNewTask((p) => ({ ...p, status: v }))} options={["PENDING", "IN_PROGRESS", "COMPLETED", "CANCELLED"].map((s) => ({ label: toPersianTaskStatus(s), value: s }))} />
              </div>
              <div className="space-y-3">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">واگذاری</p>
                <ConsultantCombobox label="واگذار به مشاور" value={newTask.assignee} onChange={(v) => setNewTask((p) => {
                  if (v === p.assignee) return p;
                  const keepProperty = !p.propertyId || !v || properties.some((x) => String(x.id) === String(p.propertyId) && String(x.consultantId ?? "") === String(v));
                  return { ...p, assignee: v, propertyId: keepProperty ? p.propertyId : "" };
                })} consultants={consultants}/>
                <PropertyCombobox label="ملک مرتبط" value={newTask.propertyId} onChange={(v) => setNewTask((p) => ({ ...p, propertyId: v }))} properties={assigneeProperties} />
              </div>
              <div className="space-y-3">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">زمان‌بندی</p>
                <JalaliDateInput label="تاریخ سررسید" value={newTask.due} onChange={(v) => setNewTask((p) => ({ ...p, due: v }))} required />
              </div>
            </div>
            <div className="flex gap-2 justify-end p-5 border-t border-border flex-shrink-0">
              <Btn variant="secondary" size="sm" onClick={closeCreate}>انصراف</Btn>
              <Btn variant="primary" size="sm" onClick={handleCreate} disabled={!newTask.title.trim() || !newTask.due || !newTask.assignee}>
                <Check size={13} />ایجاد وظیفه
              </Btn>
            </div>
          </Card>
        </div>
      )}
      {selectedTask && <TaskDetailModal task={selectedTask} onClose={() => setSelectedTask(null)} onSave={async (patch) => { await onSave(String(selectedTask.id), patch); }} onDelete={async () => { await onDelete(String(selectedTask.id)); }} />}
      <ConfirmModal open={!!confirmDeleteTask} title="حذف وظیفه؟" danger message="این وظیفه برای همیشه حذف خواهد شد. این عملیات قابل بازگشت نیست." onConfirm={handleDeleteConfirm} onCancel={() => setConfirmDeleteTask(null)} />
    </div>
  );
}

export { TasksKanban };
