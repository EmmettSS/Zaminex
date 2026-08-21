import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { Page, Role, Property, Listing, FollowUp, ConsultantItem, BadgeV, FollowUpCreatePayload } from "../../../shared/lib/types";
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
import { formatJalali } from "../../../shared/lib/jdate";
import { ConfirmModal } from "../../../shared/components/ConfirmModal";
import { Pagination } from "../../../shared/components/Pagination";
import { DistrictCombobox } from "../../../shared/components/ui/DistrictCombobox";
import { apiFetch, readJson, apiErrorMessage, getCsrfToken } from "../../../shared/lib/apiClient";
import { toast } from "../../../shared/lib/utils";
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, MessageSquare, Sparkles, GripVertical, MoreVertical, Building, History, Flame, Image, Filter } from "lucide-react";
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, ReferenceLine, ScatterChart, Scatter, ZAxis, RadialBarChart, RadialBar } from "recharts";
import { statusBadge } from "../../../shared/components/ui/StatusBadge";
import { ActionMenu } from "../../../shared/components/ActionMenu";
import { TaskDetailModal } from "../../../shared/components/TaskDetailModal";
function MyTasksPage({ tasks, consultantId, onSave, onStatusChange, onDelete }: { 
  tasks: any[]; 
  consultantId: string | null; 
  onSave: (id: string, patch: any) => Promise<void>;
  onStatusChange: (id: string, status: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedTask, setSelectedTask] = useState<any | null>(null);
  const [confirmDeleteTask, setConfirmDeleteTask] = useState<string | null>(null);
  const myTasks = tasks.filter((t) => String(t.assigneeId) === String(consultantId));
  const shown = myTasks.filter((t) => statusFilter === "all" || t.status === statusFilter);

  const taskActions = (t: any) => [
    { label: "مشاهده و ویرایش", icon: <Edit2 size={12} />, onClick: () => setSelectedTask(t) },
    { label: "تکمیل", icon: <Check size={12} />, onClick: () => onStatusChange(String(t.id), "COMPLETED") },
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

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <PageHeader title="وظایف من" />
      <div className="flex gap-1.5 mb-5 flex-wrap">
        {["all", "PENDING", "IN_PROGRESS", "COMPLETED", "CANCELLED"].map((s) => (
          <button key={s} onClick={() => setStatusFilter(s)} className={cx("px-3 py-1.5 rounded-lg text-xs font-medium transition-colors", statusFilter === s ? "bg-primary text-white shadow-sm" : "bg-white border border-border hover:bg-secondary")}>
            {s === "all" ? "همه وظایف" : toPersianTaskStatus(s)}
          </button>
        ))}
      </div>
      {shown.length === 0 ? <EmptyState icon={<CheckCircle2 size={28} />} title="وظیفه‌ای نیست" description="با فیلتر فعلی هیچ وظیفه‌ای پیدا نشد." /> : (
        <div className="space-y-3">
          {shown.map((t) => (
            <Card key={t.id} className="p-4 flex items-start gap-3 cursor-pointer hover:shadow-md transition-shadow" onClick={() => setSelectedTask(t)}>
              <div className="mt-0.5 flex-shrink-0">{t.status === "COMPLETED" ? <CheckCircle2 size={16} className="text-emerald-500" /> : <Circle size={16} className="text-muted-foreground" />}</div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold">{t.title}</p>
                {t.description && <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{t.description}</p>}
                <div className="flex items-center gap-3 mt-2 flex-wrap">
                  {statusBadge(t.priority)}{t.taskType && <Badge label={t.taskType} variant="muted" />}
                  {isTaskOverdue(t) && <Badge label="از تاریخ گذشته" variant="danger" />}
                  <span className="text-xs text-muted-foreground flex items-center gap-1"><Clock size={10} />سررسید {formatJalali(t.due)}</span>
                  {t.completionDate && <span className="text-xs text-emerald-600 flex items-center gap-1"><CheckCircle2 size={10} />تکمیل {formatJalali(t.completionDate)}</span>}
                </div>
              </div>
              <div onClick={(e) => e.stopPropagation()}><ActionMenu actions={taskActions(t)} /></div>
            </Card>
          ))}
        </div>
      )}
      {selectedTask && <TaskDetailModal task={selectedTask} onClose={() => setSelectedTask(null)} onSave={async (patch) => { await onSave(String(selectedTask.id), patch); }} onDelete={async () => { await onDelete(String(selectedTask.id)); }} />}
      <ConfirmModal open={!!confirmDeleteTask} title="حذف وظیفه؟" danger message="این وظیفه برای همیشه حذف خواهد شد. این عملیات قابل بازگشت نیست." onConfirm={handleDeleteConfirm} onCancel={() => setConfirmDeleteTask(null)} />
    </div>
  );
}

export { MyTasksPage };
