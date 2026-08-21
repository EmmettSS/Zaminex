import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { Page, Role, Property, Listing, FollowUp, ConsultantItem, BadgeV, FollowUpCreatePayload } from "../../../shared/lib/types";
import { fmtShort, toPersianType, toPersianDeal, toPersianPropertyStatus, toPersianTaskStatus, toPersianTaskType, toPersianPriority, toPersianChannel, propertyStatusToUI, toPersianFollowupType, toPersianListingStatus, isFollowUpOverdue } from "../../../shared/lib/utils";
import { Badge } from "../../../shared/components/ui/Badge";
import { Btn } from "../../../shared/components/ui/Btn";
import { Input } from "../../../shared/components/ui/Input";
import { Card } from "../../../shared/components/ui/Card";
import { SelectField } from "../../../shared/components/ui/SelectField";
import { ProfileAvatar } from "../../../shared/components/ui/ProfileAvatar";
import { KpiCard } from "../../../shared/components/ui/KpiCard";
import { EmptyState } from "../../../shared/components/ui/EmptyState";
import { PageHeader } from "../../../shared/components/ui/PageHeader";
import { formatJalaliDT } from "../../../shared/lib/jdate";
import { ConfirmModal } from "../../../shared/components/ConfirmModal";
import { Pagination } from "../../../shared/components/Pagination";
import { ConsultantCombobox } from "../../../shared/components/ui/ConsultantCombobox";
import { PropertyCombobox } from "../../../shared/components/ui/PropertyCombobox";
import { DistrictCombobox } from "../../../shared/components/ui/DistrictCombobox";
import { apiFetch, readJson, apiErrorMessage, getCsrfToken } from "../../../shared/lib/apiClient";
import { toast } from "../../../shared/lib/utils";
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, MessageSquare, Sparkles, GripVertical, MoreVertical, Building, History, Flame, Image, Filter } from "lucide-react";
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, ReferenceLine } from "recharts";
import { statusBadge } from "../../../shared/components/ui/StatusBadge";
import { ActionMenu } from "../../../shared/components/ActionMenu";
function FollowUpsPage({
  navigate,
  followups,
  loading,
  error,
  onArchive,
  onDelete,
  onComplete,
  onEdit,
  currentUserId,
  page,
  role,
  consultants = [],
  properties = [],
}: {
  navigate: (p: Page) => void;
  followups: FollowUp[];
  loading: boolean;
  error: string | null;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
  onComplete: (id: string, outcome: string, probability: number) => void;
  onEdit: (id: string) => void;
  currentUserId?: string | null;
  page: Page;
  role: Role;
  consultants?: ConsultantItem[];
  properties?: Property[];
}) {
  const isAdminList = role === "admin" && page === "follow-ups";
  const [typeFilter, setTypeFilter] = useState("all");
  const [consultantFilter, setConsultantFilter] = useState("");
  const [propertyFilter, setPropertyFilter] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const hasListFilters = Boolean(consultantFilter || propertyFilter);
  const clearListFilters = () => {
    setConsultantFilter("");
    setPropertyFilter("");
  };

  const scoped =
    role === "consultant" && currentUserId
      ? followups.filter((f) => String(f.consultantId) === String(currentUserId))
      : followups;

  // Newest activity first: a follow-up that was created or edited most
  // recently surfaces at the top, regardless of its scheduled date or
  // overdue state — the order updates dynamically after every edit.
  const orderedScoped = [...scoped].sort((a, b) => {
    const timeA = new Date(a.updatedAt || a.createdAt || a.date || 0).getTime();
    const timeB = new Date(b.updatedAt || b.createdAt || b.date || 0).getTime();
    if (timeA !== timeB) return timeB - timeA;
    return String(b.id).localeCompare(String(a.id));
  });

  const shown =
    page === "my-followups"
      ? currentUserId
        ? orderedScoped.filter((f) => String(f.consultantId) === String(currentUserId))
        : []
      : orderedScoped.filter((f) => {
          if (typeFilter !== "all" && f.type !== typeFilter) return false;
          if (isAdminList && consultantFilter && String(f.consultantId) !== String(consultantFilter)) return false;
          if (isAdminList && propertyFilter && String(f.propertyId ?? "") !== String(propertyFilter)) return false;
          return true;
        });

  const fuActions = (fu: FollowUp) => [
    { label: "ویرایش", icon: <Edit2 size={12} />, onClick: () => onEdit(fu.id) },
    { label: "تکمیل", icon: <Check size={12} />, onClick: () => onComplete(fu.id, "پیگیری تکمیل شد", fu.probability || 50) },
    { label: "بایگانی", icon: <Archive size={12} />, onClick: () => onArchive(fu.id) },
    { label: "حذف", icon: <Trash2 size={12} />, onClick: () => setConfirmDelete(fu.id), danger: true },
  ];

  if (loading) return <div className="p-6 text-sm text-muted-foreground">در حال بارگذاری پیگیری‌ها…</div>;
  if (error) return <div className="p-6 text-sm text-red-600">{error}</div>;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <PageHeader
        title="هوش پیگیری"
        subtitle={`${shown.filter((f) => f.status === "scheduled").length.toLocaleString("fa-IR")} زمان‌بندی‌شده · ${shown.length.toLocaleString("fa-IR")} یافت شده`}
        actions={
          <Btn onClick={() => navigate("create-followup")}>
            زمان‌بندی پیگیری
          </Btn>
        }
      />
      <div className="flex gap-1.5 mb-5 flex-wrap">
        {["all", "Call", "Meeting", "Email", "Site Visit"].map((t) => (
          <button key={t} onClick={() => setTypeFilter(t)} className={cx("px-3 py-1.5 rounded-lg text-xs font-medium transition-colors", typeFilter === t ? "bg-primary text-white shadow-sm" : "bg-white border border-border hover:bg-secondary")}>{t === "all" ? "همه انواع" : toPersianFollowupType(t)}</button>
        ))}
      </div>
      {isAdminList && (
        <Card className="p-4 mb-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-end">
            <ConsultantCombobox label="مشاور" value={consultantFilter} onChange={setConsultantFilter} consultants={consultants} />
            <PropertyCombobox label="ملک" value={propertyFilter} onChange={setPropertyFilter} properties={properties} />
          </div>
          <div className="flex justify-end mt-3">
            <button
              type="button"
              onClick={clearListFilters}
              disabled={!hasListFilters}
              className={cx(
                "text-xs whitespace-nowrap transition-colors",
                hasListFilters ? "text-destructive hover:underline" : "text-muted-foreground/50 cursor-not-allowed"
              )}
            >
              پاک کردن فیلتر
            </button>
          </div>
        </Card>
      )}
      <div className="relative">
        <div className="absolute left-5 top-0 bottom-0 w-px bg-border" />
        <div className="space-y-4">
          {shown.length === 0 ? (
            <EmptyState icon={<BellRing size={28} />} title="پیگیری‌ای یافت نشد" description="برای ایجاد اولین پیگیری، دکمه زمان‌بندی را بزنید." />
          ) : shown.map((fu) => (
            <div key={fu.id} className="flex gap-4">
              <div className="relative z-10 flex-shrink-0"><div className={cx("w-10 h-10 rounded-xl flex items-center justify-center text-white", fu.type === "Call" ? "bg-blue-500" : fu.type === "Meeting" ? "bg-purple-500" : fu.type === "Email" ? "bg-slate-400" : "bg-emerald-500")}>{fu.type === "Call" ? <Phone size={14} /> : fu.type === "Meeting" ? <Users size={14} /> : fu.type === "Email" ? <Mail size={14} /> : <MapPin size={14} />}</div></div>
              <Card className="flex-1 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1"><div className="flex items-center gap-2 mb-1 flex-wrap">{statusBadge(fu.type)}{statusBadge(fu.status)}{isFollowUpOverdue(fu) && <Badge label="از تاریخ گذشته" variant="danger" />}</div><h3 className="text-sm font-semibold">{fu.title}</h3><p className="text-xs text-muted-foreground mt-1">مخاطب: <strong>{fu.contact}</strong> · {fu.consultant} · {formatJalaliDT(fu.date)}</p>{fu.outcome && <div className="mt-2 px-3 py-2 bg-secondary rounded-xl text-xs"><span className="font-medium">نتیجه:</span> {fu.outcome}</div>}</div>
                  <div className="flex-shrink-0">
                    <ActionMenu actions={fuActions(fu)} />
                  </div>
                </div>
              </Card>
            </div>
          ))}
        </div>
      </div>
      <ConfirmModal open={!!confirmDelete} title="حذف پیگیری؟" danger message="این پیگیری برای همیشه حذف خواهد شد." onConfirm={() => { if (confirmDelete) onDelete(confirmDelete); setConfirmDelete(null); }} onCancel={() => setConfirmDelete(null)} />
    </div>
  );
}

export { FollowUpsPage };
