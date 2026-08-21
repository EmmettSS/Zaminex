import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { fuzzyFilter } from "../../../shared/lib/fuzzySearch";
import { Page, Role, Property, Listing, FollowUp, ConsultantItem, BadgeV } from "../../../shared/lib/types";
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
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, GripVertical, MoreVertical, Building, History, Flame, Image, Filter } from "lucide-react";
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, ReferenceLine, ScatterChart, Scatter, ZAxis, RadialBarChart, RadialBar } from "recharts";
import { ConsultantAnalyticsSection } from "../components/ConsultantAnalyticsSection";
import { AIDescription, makeAIDescriptionFetcher } from "../../../shared/components/ui/AIDescription";
import { AdminPasswordChangeModal } from "../../../shared/components/AdminPasswordChangeModal";
function ConsultantsPage({
  navigate,
  consultants,
  loading,
  error,
  onToggleActive,
  onDelete,
  onEdit,
  csrfToken,
  initialConsultantId,
}: {
  navigate: (p: Page) => void;
  consultants: any[];
  loading: boolean;
  error: string | null;
  onToggleActive: (id: string, active: boolean) => void;
  onDelete: (id: string) => void;
  onEdit: (id: string) => void;
  csrfToken?: string;
  initialConsultantId?: string | null;
}) {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<any | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [showPasswordChange, setShowPasswordChange] = useState(false);
  const appliedFocusRef = useRef<string | null>(null);

  const filtered = useMemo(() => {
    return fuzzyFilter(consultants, search, (c) => `${c.full_name || ""} ${c.user?.role || ""} ${c.branch || ""}`);
  }, [consultants, search]);

  useEffect(() => {
    if (!consultants.length) {
      setSelected(null);
      return;
    }

    const focusId = initialConsultantId ? String(initialConsultantId) : null;
    if (focusId && appliedFocusRef.current !== focusId) {
      const match = consultants.find((c) =>
        String(c.user?.id ?? "") === focusId || String(c.id) === focusId
      );
      if (match) {
        appliedFocusRef.current = focusId;
        setSelected(match);
        return;
      }
    }

    setSelected((prev) => {
      if (!prev) return consultants[0];
      const updated = consultants.find((c) => String(c.id) === String(prev.id));
      return updated || consultants[0];
    });
  }, [consultants, initialConsultantId]);

  const cActions = (c: any) => [
    {
      label: "ویرایش مشاور",
      icon: <Edit2 size={12} />,
      onClick: () => onEdit(String(c.id)),
    },
    c.is_active
      ? {
          label: "بایگانی حساب",
          icon: <Archive size={12} />,
          onClick: () => onToggleActive(String(c.id), false),
        }
      : {
          label: "فعال کردن حساب",
          icon: <CheckCircle2 size={12} />,
          onClick: () => onToggleActive(String(c.id), true),
        },
    {
      label: "حذف حساب",
      icon: <Trash2 size={12} />,
      onClick: () => setConfirmDelete(String(c.id)),
      danger: true,
    },
  ];

  if (loading) return <div className="p-6 text-sm text-muted-foreground">در حال بارگذاری مشاوران…</div>;
  if (error) return <div className="p-6 text-sm text-red-600">{error}</div>;

  return (
    <div className="flex h-full overflow-hidden">
      <div className="w-72 flex-shrink-0 border-r border-border bg-white flex flex-col">
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between mb-3"><h2 className="text-sm font-bold">فضای کاری مشاوران</h2><Btn variant="primary" size="xs" onClick={() => navigate("add-consultant")}><Plus size={11} />افزودن</Btn></div>
          <p className="text-xs text-muted-foreground mb-3">{consultants.filter((c) => c.is_active).length.toLocaleString("fa-IR")} فعال · {consultants.length.toLocaleString("fa-IR")} کل</p>
          <div className="relative"><Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="جستجوی نام، نقش، شعبه…" className="w-full pl-8 pr-3 py-2 text-xs rounded-xl border border-border bg-secondary outline-none focus:ring-2 focus:ring-ring" /></div>
        </div>
        <div className="flex-1 overflow-y-auto py-2" style={{ scrollbarWidth: "none" }}>
          {filtered.map((c) => (
            <button key={c.id} onClick={() => setSelected(c)} className={cx("w-full flex items-center gap-3 px-4 py-3 text-right transition-colors hover:bg-secondary/50 group", selected?.id === c.id && "bg-primary/5 border-r-2 border-primary")}>
              <div className="relative flex-shrink-0">{c.profile_image ? <img src={c.profile_image} alt={c.full_name} className="w-8 h-8 rounded-full object-cover" /> : <User size={32} />}<div className={cx("absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-white", c.is_active ? "bg-emerald-400" : "bg-muted-foreground")} /></div>
              <div className="flex-1 min-w-0 text-right">
                <div className="flex items-center justify-between"><p className="text-xs font-semibold truncate text-right">{c.full_name}</p><div onClick={(e) => e.stopPropagation()}><ActionMenu actions={cActions(c)} /></div></div>
                <p className="text-xs text-muted-foreground truncate text-right">{c.user?.role}</p>
                <p className="text-xs text-muted-foreground truncate text-right">{c.branch}</p>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto bg-background p-6">
        {!selected ? (
          <div className="max-w-3xl mx-auto">
            <Card className="p-6">
              <p className="text-sm text-muted-foreground">
                مشاوری انتخاب نشده است.
              </p>
            </Card>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto space-y-5">
            <Card className="p-5">
              <div className="flex items-start gap-4">
                <div className="relative">{selected.profile_image ? <img src={selected.profile_image} alt={selected.full_name} className="w-12 h-12 rounded-full object-cover" /> : <User size={48}/>}<div className={cx("absolute -bottom-0.5 -right-0.5 w-4 h-4 rounded-full border-2 border-white", selected?.is_active ? "bg-emerald-400" : "bg-muted-foreground")} /></div>
                <div className="flex-1">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-bold">{selected.full_name}</h2>
                      <p className="text-sm text-muted-foreground">{selected.user?.role} · {selected.branch}</p>
                      <div className="flex items-center gap-2 mt-1"><Badge label={selected?.is_active ? "فعال" : "غیرفعال"} variant={selected?.is_active ? "success" : "muted"} dot /></div>
                    </div>
                    <div className="flex gap-2">
                      <Btn variant="secondary" size="sm" onClick={() => setShowPasswordChange(true)}><Key size={12} />تغییر رمز عبور</Btn>
                      <Btn variant="secondary" size="sm" onClick={() => onEdit(String(selected.id))}><Edit2 size={12} />ویرایش</Btn>
                      {selected?.is_active
                        ? <Btn variant="secondary" size="sm" onClick={() => onToggleActive(String(selected.id), false)}><Archive size={12} />بایگانی</Btn>
                        : <Btn variant="secondary" size="sm" onClick={() => onToggleActive(String(selected.id), true)}><CheckCircle2 size={12} />فعال کردن</Btn>}
                      <Btn variant="danger" size="sm" onClick={() => setConfirmDelete(String(selected.id))}><Trash2 size={12} />حذف</Btn>
                    </div>
                  </div>
                </div>
              </div>
            </Card>

            <Card className="p-5">
              <h3 className="text-sm font-semibold mb-3">اطلاعات تماس و شعبه</h3>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div className="flex items-center gap-2.5 p-3 bg-secondary rounded-xl"><User size={14} className="text-muted-foreground flex-shrink-0" /><div><p className="text-xs text-muted-foreground">نام کاربری</p><p className="text-xs font-medium">{selected.user?.username || "—"}</p></div></div>
                <div className="flex items-center gap-2.5 p-3 bg-secondary rounded-xl"><Mail size={14} className="text-muted-foreground flex-shrink-0" /><div><p className="text-xs text-muted-foreground">ایمیل</p><p className="text-xs font-medium">{selected.user?.email}</p></div></div>
                <div className="flex items-center gap-2.5 p-3 bg-secondary rounded-xl"><Phone size={14} className="text-muted-foreground flex-shrink-0" /><div><p className="text-xs text-muted-foreground">موبایل</p><p className="text-xs font-medium">{selected.mobile || "—"}</p></div></div>
                <div className="flex items-center gap-2.5 p-3 bg-secondary rounded-xl"><Building size={14} className="text-muted-foreground flex-shrink-0" /><div><p className="text-xs text-muted-foreground">شعبه</p><p className="text-xs font-medium">{selected.branch}</p></div></div>
              </div>
            </Card>

            {selected && (
              <AIDescription
                key={selected.id}
                reloadKey={selected.id}
                title={`تحلیل کاربر ${selected.full_name} توسط هوش مصنوعی`}
                fetchFn={makeAIDescriptionFetcher("consultant", selected.id, csrfToken)}
              />
            )}

            {csrfToken && selected && (
              <ConsultantAnalyticsSection consultantId={selected.id} csrfToken={csrfToken} />
            )}

            <Card className="p-5">
              <h3 className="text-sm font-semibold mb-3">شاخص‌های عملکرد</h3>
              <div className="grid grid-cols-2 gap-3">
                {[
                  ["سابقه کاری (روز)", (selected.tenureDays ?? 0).toLocaleString("fa-IR")],
                  ["وظایف تأخیردار", (selected.tasksOverdueCount ?? 0).toLocaleString("fa-IR")],
                  ["پیگیری‌های تأخیردار", (selected.followupsOverdueCount ?? 0).toLocaleString("fa-IR")],
                  ["معاملات بسته‌شده (۹۰ روز)", (selected.closedDealsCount ?? 0).toLocaleString("fa-IR")],
                  ["کارهای تکمیل‌شده (۳۰ روز)", (selected.completedWorkCount ?? 0).toLocaleString("fa-IR")],
                  ["شناسه مشاور", String(selected.agentId ?? selected.id)],
                ].map(([k, v]) => (
                  <div key={k as string} className="p-3 bg-secondary rounded-xl">
                    <p className="text-xs text-muted-foreground mb-1">{k}</p>
                    <p className="text-sm font-semibold">{v as string}</p>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-5">
              <h3 className="text-sm font-semibold mb-3">ملک‌های واگذارشده</h3>
              <p className="text-xs text-muted-foreground">برای مشاهده ملک‌های این مشاور به صفحه املاک بروید و فیلتر مشاور را اعمال کنید.</p>
            </Card>
          </div>
        )}
      </div>
      <ConfirmModal open={!!confirmDelete} title="حذف مشاور؟" danger message="این حساب مشاور و تمام داده‌های مرتبط برای همیشه حذف خواهند شد." onConfirm={() => { if (confirmDelete) onDelete(confirmDelete); setConfirmDelete(null); }} onCancel={() => setConfirmDelete(null)} />
      
      <AdminPasswordChangeModal
        open={showPasswordChange}
        onClose={() => setShowPasswordChange(false)}
        userId={selected?.user?.id || selected?.id}
        userName={selected?.full_name || selected?.user?.username}
        onSuccess={() => {
          toast({ type: "success", message: "رمز عبور با موفقیت تغییر کرد" });
        }}
      />
    </div>
  );
}

// =============================================================================
//  Add Consultant Page
// =============================================================================


export { ConsultantsPage };
