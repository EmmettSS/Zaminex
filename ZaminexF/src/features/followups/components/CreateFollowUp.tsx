import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { Page, Role, Property, Listing, FollowUp, ConsultantItem, BadgeV, FollowUpCreatePayload } from "../../../shared/lib/types";
import { fmtShort, toPersianType, toPersianDeal, toPersianPropertyStatus, toPersianTaskStatus, toPersianTaskType, toPersianPriority, toPersianChannel, propertyStatusToUI, toPersianFollowupType, toPersianListingStatus } from "../../../shared/lib/utils";
import { Badge } from "../../../shared/components/ui/Badge";
import { Btn } from "../../../shared/components/ui/Btn";
import { Input } from "../../../shared/components/ui/Input";
import { JalaliDateInput } from "../../../shared/components/ui/JalaliDateInput";
import { Card } from "../../../shared/components/ui/Card";
import { SelectField } from "../../../shared/components/ui/SelectField";
import { ProfileAvatar } from "../../../shared/components/ui/ProfileAvatar";
import { KpiCard } from "../../../shared/components/ui/KpiCard";
import { EmptyState } from "../../../shared/components/ui/EmptyState";
import { PageHeader } from "../../../shared/components/ui/PageHeader";
import { ConfirmModal } from "../../../shared/components/ConfirmModal";
import { Pagination } from "../../../shared/components/Pagination";
import { ConsultantCombobox } from "../../../shared/components/ui/ConsultantCombobox";
import { DistrictCombobox } from "../../../shared/components/ui/DistrictCombobox";
import { apiFetch, readJson, apiErrorMessage, getCsrfToken } from "../../../shared/lib/apiClient";
import { toast } from "../../../shared/lib/utils";
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, MessageSquare, Sparkles, GripVertical, MoreVertical, Building, History, Flame, Image, Filter } from "lucide-react";
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, ReferenceLine } from "recharts";
import { PropertyCombobox } from "../../../shared/components/ui/PropertyCombobox";
function toLocalDateTimeValue(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return iso.includes("T") ? iso.slice(0, 16) : iso;
  }
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function CreateFollowUp({
  navigate,
  role,
  onSubmit,
  isSubmitting,
  submitError,
  currentUserId,
  consultants,
  properties,
  userName,
  editingFollowup,
}: {
  navigate: (p: Page) => void;
  role?: Role;
  onSubmit: (payload: FollowUpCreatePayload, followupId?: string | null) => Promise<void>;
  isSubmitting: boolean;
  submitError: string | null;
  currentUserId?: string | null;
  consultants: ConsultantItem[];
  properties: Property[];
  userName: string;
  editingFollowup?: FollowUp | null;
}) {
  const isConsultant = role === "consultant";
  const isEdit = Boolean(editingFollowup);

  const [form, setForm] = useState({
    title: editingFollowup?.title || "",
    type: (editingFollowup?.type || "Call") as FollowUp["type"],
    contact: editingFollowup?.contact || "",
    date: toLocalDateTimeValue(editingFollowup?.date),
    propertyId: editingFollowup?.propertyId != null ? String(editingFollowup.propertyId) : "",
    consultantId: isConsultant ? (currentUserId || "") : (editingFollowup?.consultantId != null ? String(editingFollowup.consultantId) : ""),
    notes: editingFollowup?.notes || "",
  });

  useEffect(() => {
    if (!editingFollowup) return;
    setForm({
      title: editingFollowup.title || "",
      type: (editingFollowup.type || "Call") as FollowUp["type"],
      contact: editingFollowup.contact || "",
      date: toLocalDateTimeValue(editingFollowup.date),
      propertyId: editingFollowup.propertyId != null ? String(editingFollowup.propertyId) : "",
      consultantId: isConsultant ? (currentUserId || "") : (editingFollowup.consultantId != null ? String(editingFollowup.consultantId) : ""),
      notes: editingFollowup.notes || "",
    });
  }, [editingFollowup, isConsultant, currentUserId]);
  
  const set = (k: string, v: string) => setForm((p) => ({ ...p, [k]: v }));
  const currentConsultant = consultants.find((c) => String(c.user?.id || c.id) === String(currentUserId));

  const consultantProperties = useMemo(() => {
    const selectedId = form.propertyId ? String(form.propertyId) : "";
    const matchesConsultant = (p: Property) =>
      String(p.consultantId ?? p.consultant ?? "") === String(form.consultantId) || (p as any).isShared === true;
    if (!form.consultantId) return properties;
    return properties.filter((p) => matchesConsultant(p) || (selectedId && String(p.id) === selectedId));
  }, [properties, form.consultantId, form.propertyId]);

  const handleSubmit = async () => {
    if (!form.title.trim()) {
      toast({ type: "error", message: "عنوان پیگیری الزامی است." });
      return;
    }
    if (!form.contact.trim()) {
      toast({ type: "error", message: "نام مخاطب الزامی است." });
      return;
    }
    if (!form.date) {
      toast({ type: "error", message: "تاریخ و زمان پیگیری الزامی است." });
      return;
    }
    if (!form.consultantId) {
      toast({ type: "error", message: "انتخاب مشاور الزامی است." });
      return;
    }
    try {
      await onSubmit({
        title: form.title,
        type: form.type,
        contact: form.contact,
        date: form.date,
        propertyId: form.propertyId || null,
        consultantId: form.consultantId || null,
        notes: form.notes,
      }, isEdit ? String(editingFollowup?.id) : null);
      toast({ type: "success", message: isEdit ? "پیگیری با موفقیت ویرایش شد." : "پیگیری با موفقیت ثبت شد." });
      navigate(isConsultant ? "my-followups" : "follow-ups");
    } catch (err: any) {
      toast({ type: "error", message: err?.message || (isEdit ? "خطا در ویرایش پیگیری" : "خطا در ثبت پیگیری") });
    }
  };

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-1.5 mb-6 text-xs text-muted-foreground">
        <button onClick={() => navigate(isConsultant ? "my-followups" : "follow-ups")} className="hover:text-foreground">پیگیری‌ها</button>
        <ChevronRight size={12} /><span className="text-foreground font-medium">{isEdit ? "ویرایش پیگیری" : "ایجاد پیگیری"}</span>
      </div>
      <Card className="p-6 space-y-4">
        <h2 className="text-base font-semibold">{isEdit ? "ویرایش پیگیری" : "پیگیری جدید"}</h2>
        <Input label="عنوان" placeholder="مثال: تماس پیگیری پس از بازدید ملک" value={form.title} onChange={(v) => set("title", v)} required />
        <div className="grid grid-cols-2 gap-4">
          <SelectField label="نوع" value={form.type} onChange={(v) => set("type", v)} options={["Call", "Meeting", "Email", "Site Visit"].map((t) => ({ label: toPersianFollowupType(t), value: t }))} required />
          <Input label="نام مخاطب" placeholder="مثال: علیرضا محمدی" value={form.contact} onChange={(v) => set("contact", v)} required />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <JalaliDateInput
            label="تاریخ برنامه‌ریزی"
            value={form.date.split("T")[0] || ""}
            onChange={(v) => set("date", form.date.includes("T") ? `${v}T${form.date.split("T")[1]}` : v)}
            required
          />
          <Input
            label="زمان"
            type="time"
            value={form.date.includes("T") ? form.date.split("T")[1].slice(0, 5) : ""}
            onChange={(v) => set("date", form.date.split("T")[0] ? `${form.date.split("T")[0]}T${v}` : v)}
          />
        </div>

        {isConsultant ? (
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-foreground">واگذار به</label>
            <div className="flex items-center gap-2.5 rounded-xl border border-border bg-muted px-3.5 py-2.5 opacity-75 cursor-not-allowed">
              <ProfileAvatar imageUrl={currentConsultant?.profile_image} initials={(currentConsultant?.full_name || userName || "U").slice(0, 2).toUpperCase()} size="xs" />
              <span className="flex-1 text-sm font-medium text-foreground">
                {currentConsultant?.full_name || userName || "مشاور جاری"}
              </span>
              <span className="text-xs text-muted-foreground bg-secondary px-2 py-0.5 rounded-full">خودکار</span>
            </div>
            <p className="text-xs text-muted-foreground">پیگیری‌ها به‌طور خودکار به حساب مشاور لاگین‌شده واگذار می‌شوند.</p>
          </div>
        ) : (
          <ConsultantCombobox label="مشاور مسئول" value={form.consultantId} onChange={(v) => setForm((p) => {
            if (v === p.consultantId) return p;
            const keepProperty = !p.propertyId || !v || properties.some((x) => String(x.id) === String(p.propertyId) && String(x.consultantId ?? "") === String(v));
            return { ...p, consultantId: v, propertyId: keepProperty ? p.propertyId : "" };
          })} required consultants={consultants}/>
        )}

        <PropertyCombobox label="ملک مرتبط" value={form.propertyId} onChange={(v) => set("propertyId", v)} properties={consultantProperties} />

        <Input label="یادداشت‌ها" placeholder="یادداشت‌های آمادگی یا زمینه…" value={form.notes} onChange={(v) => set("notes", v)} textarea rows={3} />
        <div className="flex gap-2 justify-end pt-2">
          <Btn variant="secondary" onClick={() => navigate(isConsultant ? "my-followups" : "follow-ups")}>انصراف</Btn>
          <Btn variant="primary" onClick={handleSubmit} disabled={isSubmitting}>{isSubmitting ? "در حال ذخیره…" : (isEdit ? "ذخیره تغییرات" : "ذخیره پیگیری")}</Btn>
        </div>
        {submitError && <div className="text-red-500 text-xs">{submitError}</div>}
      </Card>
    </div>
  );
}

// =============================================================================
//  Property-scoped Reports
// =============================================================================

const CHART_COLORS = ["#0BB68A", "#3B82F6", "#F59E0B", "#8B5CF6", "#EF4444", "#EC4899", "#14B8A6", "#F97316"];
const DELEGATION_COLORS = { selfManaged: "#0BB68A", delegated: "#3B82F6", unassigned: "#94A3B8" };

export { CreateFollowUp };
