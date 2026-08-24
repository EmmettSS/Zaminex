import React, { useEffect, useMemo, useState } from "react";
import { cx } from "../../../shared/lib/utils";
import { Badge } from "../../../shared/components/ui/Badge";
import { Card } from "../../../shared/components/ui/Card";
import { EmptyState } from "../../../shared/components/ui/EmptyState";
import { PageHeader } from "../../../shared/components/ui/PageHeader";
import { formatJalali } from "../../../shared/lib/jdate";
import { JalaliDateInput } from "../../../shared/components/ui/JalaliDateInput";
import { ConfirmModal } from "../../../shared/components/ConfirmModal";
import { statusBadge } from "../../../shared/components/ui/StatusBadge";
import { ActionMenu } from "../../../shared/components/ActionMenu";
import { TaskDetailModal } from "../../../shared/components/TaskDetailModal";
import { toast } from "../../../shared/lib/utils";
import { isTaskOverdue, toPersianTaskStatus } from "../../../shared/lib/utils";
import { CheckCircle2, Clock, Circle, CheckSquare, Eye, Check, Trash2 } from "lucide-react";

type TaskRow = {
  id: string | number;
  title: string;
  description?: string;
  status: string;
  priority: string;
  taskType?: string;
  due?: string;
  completionDate?: string | null;
  assigneeId?: string | number | null;
  [k: string]: unknown;
};

type TaskFilters = {
  status?: string;
  dueDateFrom?: string;
  dueDateTo?: string;
};

function MyTasksPage({
  tasks: initialTasks,
  consultantId,
  role,
  onLoad,
  refreshKey = 0,
  onSave,
  onStatusChange,
  onDelete,
}: {
  tasks: TaskRow[];
  consultantId: string | null;
  role: "admin" | "consultant";
  onLoad: (filters?: TaskFilters) => Promise<TaskRow[] | void>;
  refreshKey?: number;
  onSave: (id: string, patch: Record<string, unknown>) => Promise<void>;
  onStatusChange: (id: string, status: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const [statusFilter, setStatusFilter] = useState("all");
  const [dueDateFrom, setDueDateFrom] = useState("");
  const [dueDateTo, setDueDateTo] = useState("");
  const [rows, setRows] = useState<TaskRow[]>(initialTasks);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedTask, setSelectedTask] = useState<TaskRow | null>(null);
  const [confirmDeleteTask, setConfirmDeleteTask] = useState<string | null>(null);

  // For consultants the server already scopes results via assignedTo, so
  // there is no client-side assignee filtering. For an admin impersonally
  // viewing "my-tasks" (not a normal flow) keep the explicit own-task guard.
  const effectiveFilters: TaskFilters = useMemo(
    () => ({
      status: statusFilter,
      dueDateFrom: dueDateFrom || undefined,
      dueDateTo: dueDateTo || undefined,
    }),
    [statusFilter, dueDateFrom, dueDateTo]
  );

  // Reload from the server whenever the filters or an external mutation
  // change. The backend applies the inclusive due-date range (and status),
  // using the existing (due_date, status) index, so the list stays correct
  // even for large datasets and is never a slice of already-paginated data.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    void onLoad(effectiveFilters)
      .then((data) => {
        if (cancelled) return;
        if (Array.isArray(data)) setRows(data);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setLoadError(err instanceof Error ? err.message : "خطا در بارگذاری وظایف");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [onLoad, effectiveFilters, refreshKey]);

  // Keep local rows in sync with the global list when no server fetch has
  // run yet (initial render) or when the parent pushes new data.
  useEffect(() => {
    setRows(initialTasks);
  }, [initialTasks]);

  const myTasks =
    role === "consultant"
      ? rows
      : rows.filter((t) => String(t.assigneeId ?? "") === String(consultantId ?? ""));

  const hasDateFilter = Boolean(dueDateFrom || dueDateTo);
  const rangeInvalid = Boolean(dueDateFrom && dueDateTo && dueDateFrom > dueDateTo);

  const handleDeleteConfirm = async () => {
    const id = confirmDeleteTask;
    setConfirmDeleteTask(null);
    if (!id) return;
    try {
      await onDelete(id);
      toast({ type: "success", message: "وظیفه با موفقیت حذف شد." });
    } catch (err: unknown) {
      toast({ type: "error", message: err instanceof Error ? err.message : "خطا در حذف وظیفه" });
    }
  };

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <PageHeader title="وظایف من" />
      <div className="flex gap-1.5 mb-5 flex-wrap">
        {["all", "PENDING", "IN_PROGRESS", "COMPLETED", "CANCELLED"].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={cx(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
              statusFilter === s
                ? "bg-primary text-white shadow-sm"
                : "bg-white border border-border hover:bg-secondary"
            )}
          >
            {s === "all" ? "همه وظایف" : toPersianTaskStatus(s)}
          </button>
        ))}
      </div>
      <Card className="p-4 mb-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <JalaliDateInput label="از تاریخ سررسید" value={dueDateFrom} onChange={setDueDateFrom} />
          <JalaliDateInput label="تا تاریخ سررسید" value={dueDateTo} onChange={setDueDateTo} />
        </div>
        {rangeInvalid && (
          <p className="text-xs text-destructive mt-2">
            تاریخ شروع نمی‌تواند پس از تاریخ پایان باشد.
          </p>
        )}
        <div className="flex justify-end mt-3">
          <button
            type="button"
            onClick={() => {
              setDueDateFrom("");
              setDueDateTo("");
            }}
            disabled={!hasDateFilter}
            className={cx(
              "text-xs transition-colors",
              hasDateFilter
                ? "text-destructive hover:underline"
                : "text-muted-foreground/50 cursor-not-allowed"
            )}
          >
            پاک کردن فیلتر تاریخ
          </button>
        </div>
      </Card>

      {loadError && (
        <div className="mb-4 rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
          {loadError}
        </div>
      )}

      {loading ? (
        <div className="p-6 text-center text-sm text-muted-foreground">در حال بارگذاری…</div>
      ) : rangeInvalid ? (
        <EmptyState
          icon={<CheckSquare size={28} />}
          title="بازه تاریخ نامعتبر است"
          description="تاریخ شروع را پیش از تاریخ پایان انتخاب کنید."
        />
      ) : myTasks.length === 0 ? (
        <EmptyState
          icon={<CheckCircle2 size={28} />}
          title="وظیفه‌ای نیست"
          description="با فیلتر فعلی هیچ وظیفه‌ای پیدا نشد."
        />
      ) : (
        <div className="space-y-3">
          {myTasks.map((t) => (
            <Card
              key={String(t.id)}
              className="p-4 flex items-start gap-3 cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => setSelectedTask(t)}
            >
              <div className="mt-0.5 flex-shrink-0">
                {t.status === "COMPLETED" ? (
                  <CheckCircle2 size={16} className="text-emerald-500" />
                ) : (
                  <Circle size={16} className="text-muted-foreground" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold">{t.title}</p>
                {t.description && (
                  <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{t.description}</p>
                )}
                <div className="flex items-center gap-3 mt-2 flex-wrap">
                  {statusBadge(t.priority)}
                  {t.taskType && <Badge label={t.taskType} variant="muted" />}
                  {isTaskOverdue(t) && <Badge label="از تاریخ گذشته" variant="danger" />}
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Clock size={10} />سررسید {formatJalali(t.due as string | null | undefined)}
                  </span>
                  {t.completionDate && (
                    <span className="text-xs text-emerald-600 flex items-center gap-1">
                      <CheckCircle2 size={10} />تکمیل {formatJalali(t.completionDate)}
                    </span>
                  )}
                </div>
              </div>
              <div onClick={(e) => e.stopPropagation()}>
                <ActionMenu
                  actions={[
                    {
                      label: "مشاهده و ویرایش",
                      icon: <Eye size={12} />,
                      onClick: () => setSelectedTask(t),
                    },
                    {
                      label: "تکمیل",
                      icon: <Check size={12} />,
                      onClick: () => onStatusChange(String(t.id), "COMPLETED"),
                    },
                    {
                      label: "حذف",
                      icon: <Trash2 size={12} />,
                      onClick: () => setConfirmDeleteTask(String(t.id)),
                      danger: true,
                    },
                  ]}
                />
              </div>
            </Card>
          ))}
        </div>
      )}

      {selectedTask && (
        <TaskDetailModal
          task={selectedTask}
          onClose={() => setSelectedTask(null)}
          onSave={async (patch) => {
            await onSave(String(selectedTask.id), patch);
          }}
          onDelete={async () => {
            await onDelete(String(selectedTask.id));
          }}
        />
      )}
      <ConfirmModal
        open={!!confirmDeleteTask}
        title="حذف وظیفه؟"
        danger
        message="این وظیفه برای همیشه حذف خواهد شد. این عملیات قابل بازگشت نیست."
        onConfirm={handleDeleteConfirm}
        onCancel={() => setConfirmDeleteTask(null)}
      />
    </div>
  );
}

export { MyTasksPage };
