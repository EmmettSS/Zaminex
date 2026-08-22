import React, { useCallback, useEffect, useMemo, useState } from "react";
import { cx } from "../../../shared/lib/utils";
import type { Page, Role, Property, ConsultantItem, FollowUp } from "../../../shared/lib/types";
import { toPersianFollowupType, isFollowUpOverdue } from "../../../shared/lib/utils";
import { Badge } from "../../../shared/components/ui/Badge";
import { Btn } from "../../../shared/components/ui/Btn";
import { Card } from "../../../shared/components/ui/Card";
import { EmptyState } from "../../../shared/components/ui/EmptyState";
import { PageHeader } from "../../../shared/components/ui/PageHeader";
import { formatJalaliDT } from "../../../shared/lib/jdate";
import { JalaliDateInput } from "../../../shared/components/ui/JalaliDateInput";
import { ConfirmModal } from "../../../shared/components/ConfirmModal";
import { ConsultantCombobox } from "../../../shared/components/ui/ConsultantCombobox";
import { PropertyCombobox } from "../../../shared/components/ui/PropertyCombobox";
import { statusBadge } from "../../../shared/components/ui/StatusBadge";
import { ActionMenu } from "../../../shared/components/ActionMenu";
import { BellRing, Phone, Users, Mail, MapPin, Edit2, Check, Archive, Trash2 } from "lucide-react";

type FollowUpFilters = {
  type?: string;
  consultantId?: string;
  propertyId?: string;
  scheduledDateFrom?: string;
  scheduledDateTo?: string;
};

function FollowUpsPage({
  navigate,
  onArchive,
  onDelete,
  onComplete,
  onEdit,
  onLoad,
  refreshKey = 0,
  currentUserId,
  page,
  role,
  consultants = [],
  properties = [],
}: {
  navigate: (p: Page) => void;
  followups?: FollowUp[];
  loading?: boolean;
  error?: string | null;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
  onComplete: (id: string, outcome: string, probability: number) => void;
  onEdit: (id: string) => void;
  onLoad: (filters: FollowUpFilters) => Promise<FollowUp[] | void>;
  refreshKey?: number;
  currentUserId?: string | null;
  page: Page;
  role: Role;
  consultants?: ConsultantItem[];
  properties?: Property[];
}) {
  const isAdminList = role === "admin" && page === "follow-ups";
  const isMyFollowupsList = page === "my-followups";

  const [typeFilter, setTypeFilter] = useState("all");
  const [consultantFilter, setConsultantFilter] = useState("");
  const [propertyFilter, setPropertyFilter] = useState("");
  const [scheduledDateFrom, setScheduledDateFrom] = useState("");
  const [scheduledDateTo, setScheduledDateTo] = useState("");

  const [rows, setRows] = useState<FollowUp[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const rangeInvalid = Boolean(
    scheduledDateFrom && scheduledDateTo && scheduledDateFrom > scheduledDateTo
  );

  const hasDateFilter = Boolean(scheduledDateFrom || scheduledDateTo);
  const hasListFilters = Boolean(
    consultantFilter || propertyFilter || typeFilter !== "all" || hasDateFilter
  );

  const clearListFilters = () => {
    setTypeFilter("all");
    setConsultantFilter("");
    setPropertyFilter("");
    setScheduledDateFrom("");
    setScheduledDateTo("");
  };

  // Build the server-side filter query. The Jalali picker already converts
  // its selection to Gregorian "YYYY-MM-DD"; both endpoints are inclusive and
  // interpreted in Asia/Tehran on the server.
  const filters: FollowUpFilters = useMemo(() => {
    const f: FollowUpFilters = {
      type: typeFilter,
      scheduledDateFrom: scheduledDateFrom || undefined,
      scheduledDateTo: scheduledDateTo || undefined,
    };
    if (isAdminList) {
      f.consultantId = consultantFilter || undefined;
      f.propertyId = propertyFilter || undefined;
    } else if (isMyFollowupsList && currentUserId) {
      // Belt-and-suspenders: the server already scopes non-admins to their
      // own follow-ups, but state the consultant explicitly so the query is
      // unambiguous and index-friendly.
      f.consultantId = String(currentUserId);
    }
    return f;
  }, [
    typeFilter,
    consultantFilter,
    propertyFilter,
    scheduledDateFrom,
    scheduledDateTo,
    isAdminList,
    isMyFollowupsList,
    currentUserId,
  ]);

  useEffect(() => {
    if (rangeInvalid) {
      // Don't fire a query with a reversed range; the UI shows the error.
      setRows([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    void onLoad(filters)
      .then((data) => {
        if (cancelled) return;
        setRows(Array.isArray(data) ? data : []);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setLoadError(err instanceof Error ? err.message : "خطا در بارگذاری پیگیری‌ها");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [onLoad, filters, rangeInvalid, refreshKey]);

  // Newest activity first: a follow-up that was created or edited most
  // recently surfaces at the top, regardless of its scheduled date or
  // overdue state — the order updates dynamically after every edit. The
  // server already orders this way, but re-sort defensively so the UI stays
  // correct regardless of the endpoint used.
  const shown = useMemo(() => {
    return [...rows].sort((a, b) => {
      const timeA = new Date(a.updatedAt || a.createdAt || a.date || 0).getTime();
      const timeB = new Date(b.updatedAt || b.createdAt || b.date || 0).getTime();
      if (timeA !== timeB) return timeB - timeA;
      return String(b.id).localeCompare(String(a.id));
    });
  }, [rows]);

  const fuActions = useCallback(
    (fu: FollowUp) => [
      { label: "ویرایش", icon: <Edit2 size={12} />, onClick: () => onEdit(fu.id) },
      {
        label: "تکمیل",
        icon: <Check size={12} />,
        onClick: () => onComplete(fu.id, "پیگیری تکمیل شد", fu.probability || 50),
      },
      { label: "بایگانی", icon: <Archive size={12} />, onClick: () => onArchive(fu.id) },
      {
        label: "حذف",
        icon: <Trash2 size={12} />,
        onClick: () => setConfirmDelete(fu.id),
        danger: true,
      },
    ],
    [onArchive, onComplete, onEdit]
  );

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <PageHeader
        title="هوش پیگیری"
        subtitle={`${shown
          .filter((f) => f.status === "scheduled")
          .length.toLocaleString("fa-IR")} زمان‌بندی‌شده · ${shown.length.toLocaleString("fa-IR")} یافت شده`}
        actions={<Btn onClick={() => navigate("create-followup")}>زمان‌بندی پیگیری</Btn>}
      />
      <div className="flex gap-1.5 mb-5 flex-wrap">
        {["all", "Call", "Meeting", "Email", "Site Visit"].map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t)}
            className={cx(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
              typeFilter === t
                ? "bg-primary text-white shadow-sm"
                : "bg-white border border-border hover:bg-secondary"
            )}
          >
            {t === "all" ? "همه انواع" : toPersianFollowupType(t)}
          </button>
        ))}
      </div>

      {(isAdminList || isMyFollowupsList) && (
        <Card className="p-4 mb-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-end">
            {isAdminList && (
              <ConsultantCombobox
                label="مشاور"
                value={consultantFilter}
                onChange={setConsultantFilter}
                consultants={consultants}
              />
            )}
            {isAdminList && (
              <PropertyCombobox
                label="ملک"
                value={propertyFilter}
                onChange={setPropertyFilter}
                properties={properties}
              />
            )}
            {isMyFollowupsList && (
              <JalaliDateInput
                label="از تاریخ پیگیری"
                value={scheduledDateFrom}
                onChange={setScheduledDateFrom}
              />
            )}
            {isMyFollowupsList && (
              <JalaliDateInput
                label="تا تاریخ پیگیری"
                value={scheduledDateTo}
                onChange={setScheduledDateTo}
              />
            )}
          </div>
          {rangeInvalid && (
            <p className="text-xs text-destructive mt-2">
              تاریخ شروع نمی‌تواند پس از تاریخ پایان باشد.
            </p>
          )}
          <div className="flex justify-end mt-3">
            <button
              type="button"
              onClick={clearListFilters}
              disabled={!hasListFilters}
              className={cx(
                "text-xs whitespace-nowrap transition-colors",
                hasListFilters
                  ? "text-destructive hover:underline"
                  : "text-muted-foreground/50 cursor-not-allowed"
              )}
            >
              پاک کردن فیلتر
            </button>
          </div>
        </Card>
      )}

      {loadError && (
        <div className="mb-4 rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
          {loadError}
        </div>
      )}

      {loading ? (
        <div className="p-6 text-center text-sm text-muted-foreground">در حال بارگذاری پیگیری‌ها…</div>
      ) : rangeInvalid ? (
        <EmptyState
          icon={<BellRing size={28} />}
          title="بازه تاریخ نامعتبر است"
          description="تاریخ شروع را پیش از تاریخ پایان انتخاب کنید."
        />
      ) : (
        <div className="relative">
          <div className="absolute left-5 top-0 bottom-0 w-px bg-border" />
          <div className="space-y-4">
            {shown.length === 0 ? (
              <EmptyState
                icon={<BellRing size={28} />}
                title="پیگیری‌ای یافت نشد"
                description="برای ایجاد اولین پیگیری، دکمه زمان‌بندی را بزنید."
              />
            ) : (
              shown.map((fu) => (
                <div key={fu.id} className="flex gap-4">
                  <div className="relative z-10 flex-shrink-0">
                    <div
                      className={cx(
                        "w-10 h-10 rounded-xl flex items-center justify-center text-white",
                        fu.type === "Call"
                          ? "bg-blue-500"
                          : fu.type === "Meeting"
                          ? "bg-purple-500"
                          : fu.type === "Email"
                          ? "bg-slate-400"
                          : "bg-emerald-500"
                      )}
                    >
                      {fu.type === "Call" ? (
                        <Phone size={14} />
                      ) : fu.type === "Meeting" ? (
                        <Users size={14} />
                      ) : fu.type === "Email" ? (
                        <Mail size={14} />
                      ) : (
                        <MapPin size={14} />
                      )}
                    </div>
                  </div>
                  <Card className="flex-1 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          {statusBadge(fu.type)}
                          {statusBadge(fu.status)}
                          {isFollowUpOverdue(fu) && <Badge label="از تاریخ گذشته" variant="danger" />}
                        </div>
                        <h3 className="text-sm font-semibold">{fu.title}</h3>
                        <p className="text-xs text-muted-foreground mt-1">
                          مخاطب: <strong>{fu.contact}</strong> · {fu.consultant} ·{" "}
                          {formatJalaliDT(fu.date)}
                        </p>
                        {fu.outcome && (
                          <div className="mt-2 px-3 py-2 bg-secondary rounded-xl text-xs">
                            <span className="font-medium">نتیجه:</span> {fu.outcome}
                          </div>
                        )}
                      </div>
                      <div className="flex-shrink-0">
                        <ActionMenu actions={fuActions(fu)} />
                      </div>
                    </div>
                  </Card>
                </div>
              ))
            )}
          </div>
        </div>
      )}
      <ConfirmModal
        open={!!confirmDelete}
        title="حذف پیگیری؟"
        danger
        message="این پیگیری برای همیشه حذف خواهد شد."
        onConfirm={() => {
          if (confirmDelete) onDelete(confirmDelete);
          setConfirmDelete(null);
        }}
        onCancel={() => setConfirmDelete(null)}
      />
    </div>
  );
}

export { FollowUpsPage };
