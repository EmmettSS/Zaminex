import React, { useState, useCallback, useEffect, useRef } from "react";
import { cx } from "../lib/utils";
import { BadgeV } from "../lib/types";
import { ChevronLeft, ChevronRight, ChevronDown, Check, X, Archive, Trash2, Download, RefreshCw, Clock, Building2, Eye, Edit2, CheckCircle2, MoreVertical, MapPin, User, Lock, Key, Send, Loader2, Shield, Filter, Plus, CheckSquare, BellRing, LayoutDashboard, FileText, Users, Activity, Settings, LogOut } from "lucide-react";
import { Badge } from "./ui/Badge";
import { Btn } from "./ui/Btn";
import { Card } from "./ui/Card";
import { ProfileAvatar } from "./ui/ProfileAvatar";
import { Input } from "./ui/Input";
import { JalaliDateInput } from "./ui/JalaliDateInput";
import { formatJalali, formatJalaliDateTime } from "../lib/jdate";
import { SelectField } from "./ui/SelectField";
import { KpiCard } from "./ui/KpiCard";
import { PageHeader } from "./ui/PageHeader";
import { EmptyState } from "./ui/EmptyState";
import { toast, toPersianTaskStatus, isTaskOverdue } from "../lib/utils";
import { apiFetch, readJson } from "../lib/apiClient";
import { createPortal } from "react-dom";
import { statusBadge } from "./ui/StatusBadge";
import { TASK_STATUSES } from "../lib/constants";
import { ConfirmModal } from "./ConfirmModal";

function formatHistoryValue(value?: string | null) {
  if (!value) return "—";
  if (/^\d{4}-\d{2}-\d{2}/.test(value)) return formatJalali(value);
  return value;
}

function TaskDetailModal({ task, onClose, onSave, onDelete }: { task: any; onClose: () => void; onSave?: (patch: Record<string, any>) => Promise<void> | void; onDelete?: () => Promise<void> | void; }) {
  const [status, setStatus] = useState(task.status);
  const [note, setNote] = useState(task.note || "");
  const [completionDate, setCompletionDate] = useState(task.completionDate || task.completed_at || "");
  const [history, setHistory] = useState<{ id: string | number; title: string; from?: string | null; to?: string | null; user: string; createdAt?: string | null; changes?: { fromLabel?: string; toLabel?: string }[] }[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fallback = [{
      id: `create-${task.id}`,
      title: "ایجاد وظیفه",
      user: task.creator || "سیستم",
      createdAt: task.created_at || null,
    }];
    const load = async () => {
      setHistoryLoading(true);
      try {
        const res = await apiFetch(`/tasks/api/tasks/${task.id}/history/`, { method: "GET" });
        const data = await readJson(res);
        if (!res.ok) throw new Error("history");
        const rows = Array.isArray(data?.results) ? data.results : [];
        const mapped = rows.map((row: any) => ({
          id: row.id,
          title: row.title || row.actionLabel || row.action || "تغییر",
          from: row.from,
          to: row.to,
          user: row.user || row.userName || "سیستم",
          createdAt: row.createdAt || null,
          changes: Array.isArray(row.changes) ? row.changes : [],
        }));
        if (!cancelled) setHistory(mapped.length ? mapped : fallback);
      } catch {
        if (!cancelled) setHistory(fallback);
      } finally {
        if (!cancelled) setHistoryLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [task.id, task.updated_at, task.creator, task.created_at]);

  const persist = async () => {
    if (!onSave) {
      toast({ type: "success", message: "وظیفه بروزرسانی شد." });
      onClose();
      return;
    }
    try {
      setSaving(true);
      await onSave({ status, completionDate, note: note.trim() });
      toast({ type: "success", message: "وظیفه با موفقیت بروزرسانی شد." });
      onClose();
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطا در ذخیره تغییرات" });
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!onDelete) return;
    try {
      setDeleting(true);
      await onDelete();
      toast({ type: "success", message: "وظیفه با موفقیت حذف شد." });
      setConfirmDelete(false);
      onClose();
    } catch (err: any) {
      setDeleting(false);
      setConfirmDelete(false);
      toast({ type: "error", message: err?.message || "خطا در حذف وظیفه" });
    }
  };

  return (
    <>
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm p-4">
      <Card className="w-full max-w-2xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
        <div className="flex items-start justify-between gap-4 p-5 border-b border-border flex-shrink-0">
          <div>
            <div className="flex items-center gap-2 mb-1 flex-wrap">{statusBadge(task.priority)}{task.taskType && <Badge label={task.taskType} variant="muted" />}{isTaskOverdue(task) && <Badge label="از تاریخ گذشته" variant="danger" />}</div>
            <h2 className="text-base font-bold">{task.title}</h2>
            <p className="text-xs text-muted-foreground mt-1">ایجاد توسط {task.creator || "—"}{task.due ? ` · سررسید ${formatJalali(task.due)}` : ""}</p>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-secondary rounded-lg transition-colors flex-shrink-0"><X size={16} /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {task.description && (
            <div><p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">توضیحات</p><p className="text-sm text-foreground leading-relaxed bg-secondary rounded-xl p-3">{task.description}</p></div>
          )}
          {task.note && (
            <div><p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">یادداشت</p><p className="text-sm text-foreground leading-relaxed bg-secondary rounded-xl p-3 whitespace-pre-wrap">{task.note}</p></div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <SelectField label="بروزرسانی وضعیت" value={status} onChange={setStatus} options={TASK_STATUSES.map((s) => ({ label: toPersianTaskStatus(s), value: s }))} />
            {status === "COMPLETED" && <JalaliDateInput label="تاریخ تکمیل" value={completionDate} onChange={setCompletionDate} />}
          </div>
          {(task.property || task.propertyId) && <div className="flex items-center gap-2 p-3 bg-secondary rounded-xl text-xs"><Building2 size={13} className="text-muted-foreground" /><span className="text-muted-foreground">ملک:</span><span className="font-medium">{task.property_detail?.title || task.property_detail?.internal_code || "—"}</span></div>}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">افزودن یادداشت</p>
            <Input placeholder="یادداشتی درباره این وظیفه بنویسید…" value={note} onChange={setNote} textarea rows={3} />
          </div>
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">سابقه تغییرات</p>
            <div className="relative">
              <div className="absolute right-3 top-0 bottom-0 w-px bg-border" />
              <div className="space-y-3 pr-8">
                {historyLoading && <p className="text-xs text-muted-foreground">در حال بارگذاری سابقه…</p>}
                {!historyLoading && history.map((h) => {
                  const when = formatJalaliDateTime(h.createdAt);
                  const extraChanges = (h.changes || []).filter((c) => c.fromLabel && c.toLabel);
                  const showPrimary = Boolean(h.from && h.to) && extraChanges.length <= 1;
                  return (
                    <div key={h.id} className="relative">
                      <div className="absolute -right-5 top-1.5 w-2 h-2 rounded-full bg-primary/50 border-2 border-white" />
                      <div className="bg-secondary rounded-xl p-3">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="text-xs font-semibold">{h.title}</span>
                          <span className="text-xs text-muted-foreground font-mono tabular-nums flex-shrink-0">{when.time}</span>
                        </div>
                        {showPrimary && <p className="text-xs text-muted-foreground"><span className="line-through">{formatHistoryValue(h.from)}</span> → <span className="font-medium text-foreground">{formatHistoryValue(h.to)}</span></p>}
                        {!showPrimary && extraChanges.length > 1 && extraChanges.map((c, i) => (
                          <p key={i} className="text-xs text-muted-foreground"><span className="line-through">{formatHistoryValue(c.fromLabel)}</span> → <span className="font-medium text-foreground">{formatHistoryValue(c.toLabel)}</span></p>
                        ))}
                        <p className="text-xs text-muted-foreground mt-1">توسط {h.user}{when.date && when.date !== "—" ? ` · ${when.date}` : ""}</p>
                      </div>
                    </div>
                  );
                })}
                {!historyLoading && history.length === 0 && <p className="text-xs text-muted-foreground">سابقه‌ای ثبت نشده است.</p>}
              </div>
            </div>
          </div>
        </div>
        <div className="flex gap-2 justify-end p-5 border-t border-border flex-shrink-0">
          <Btn variant="secondary" size="sm" onClick={onClose}>بستن</Btn>
          <Btn variant="primary" size="sm" onClick={persist} disabled={saving}><Check size={13} />{saving ? "در حال ذخیره…" : "ذخیره تغییرات"}</Btn>
          {onDelete && <Btn variant="danger" size="sm" onClick={() => setConfirmDelete(true)} disabled={deleting}><Trash2 size={13} />{deleting ? "در حال حذف…" : "حذف وظیفه"}</Btn>}
        </div>
      </Card>
    </div>
    <ConfirmModal open={confirmDelete} title="حذف وظیفه؟" danger message="این وظیفه برای همیشه حذف خواهد شد. این عملیات قابل بازگشت نیست." onConfirm={remove} onCancel={() => setConfirmDelete(false)} />
    </>
  );
}

// =============================================================================
//  Auth (Login Page)
// =============================================================================

export { TaskDetailModal };
