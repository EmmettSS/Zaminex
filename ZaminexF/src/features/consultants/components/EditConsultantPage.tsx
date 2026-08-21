import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
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
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, MessageSquare, Sparkles, GripVertical, MoreVertical, Building, History, Flame, Image, Filter } from "lucide-react";
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, ReferenceLine, ScatterChart, Scatter, ZAxis, RadialBarChart, RadialBar } from "recharts";
function EditConsultantPage({
  navigate,
  consultant,
  onSubmit,
  isSubmitting,
  submitError,
  districtsList,
}: {
  navigate: (p: Page) => void;
  consultant: ConsultantItem | undefined;
  onSubmit: (id: string, payload: Record<string, any>) => Promise<any>;
  isSubmitting: boolean;
  submitError: string | null;
  districtsList: string[];
}) {
  const [form, setForm] = useState({
    firstName: consultant?.user?.first_name || "",
    lastName: consultant?.user?.last_name || "",
    fullName: consultant?.full_name || "",
    email: consultant?.user?.email || "",
    phone: consultant?.mobile || "",
    branch: consultant?.branch || "",
    notes: (consultant as any)?.notes || "",
  });

  const [profileImage, setProfileImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(consultant?.profile_image || null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (consultant) {
      setForm({
        firstName: consultant.user?.first_name || "",
        lastName: consultant.user?.last_name || "",
        fullName: consultant.full_name || "",
        email: consultant.user?.email || "",
        phone: consultant.mobile || "",
        branch: consultant.branch || "",
        notes: (consultant as any)?.notes || "",
      });
      setImagePreview(consultant.profile_image || null);
    }
  }, [consultant]);

  const set = (k: string, v: string) => setForm((p) => ({ ...p, [k]: v }));

  const handleSubmit = async () => {
    if (!consultant) return;
    const mobile = form.phone.trim();
    if (mobile && !/^09\d{9}$/.test(mobile)) {
      toast({ type: "error", message: "شماره موبایل باید با 09 شروع شود و ۱۱ رقم باشد." });
      return;
    }
    if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
      toast({ type: "error", message: "ایمیل معتبر نیست" });
      return;
    }

    const payload: Record<string, any> = {
      first_name: form.firstName.trim(),
      last_name: form.lastName.trim(),
      full_name: form.fullName.trim() || `${form.firstName} ${form.lastName}`.trim(),
      email: form.email.trim(),
      mobile: form.phone.trim(),
      branch: form.branch,
      notes: form.notes.trim(),
    };

    if (profileImage) {
      payload.profile_image = profileImage;
    }

    const result = await onSubmit(String(consultant.id), payload);
    if (result?.ok) {
      navigate("consultants");
    }
  };

  if (!consultant) {
    return <div className="p-6 text-sm text-muted-foreground">در حال بارگذاری…</div>;
  }

  return (
    <div className="mx-auto max-w-2xl p-6">
      <div className="mb-6 flex items-center gap-1.5 text-xs text-muted-foreground">
        <button onClick={() => navigate("consultants")} className="hover:text-foreground">
          مشاوران
        </button>
        <ChevronRight size={12} />
        <span className="font-medium text-foreground">ویرایش مشاور</span>
      </div>

      <Card className="space-y-5 p-6">
        <div>
          <h2 className="text-base font-semibold">ویرایش حساب مشاور</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            اطلاعات پروفایل و حساب کاربری {consultant.full_name} را ویرایش کنید.
          </p>
        </div>

        {submitError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {submitError}
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-4">
          <Input label="نام" value={form.firstName} onChange={(v) => set("firstName", v)} required />
          <Input label="نام خانوادگی" value={form.lastName} onChange={(v) => set("lastName", v)} required />
          <Input label="نام کامل" value={form.fullName} onChange={(v) => set("fullName", v)} />
          <Input label="آدرس ایمیل" type="email" value={form.email} onChange={(v) => set("email", v)} />
          <Input label="تلفن" value={form.phone} onChange={(v) => set("phone", v)} />
          <DistrictCombobox
            label="شعبه"
            value={form.branch}
            onChange={(v) => set("branch", v)}
            districtsList={districtsList}
            required
          />
          <Input label="یادداشت" value={form.notes} onChange={(v) => set("notes", v)} />
        </div>

        {/* Profile Image Upload */}
        <div className="space-y-3">
          <label className="text-sm font-medium text-foreground">تصویر پروفایل</label>
          <div className="flex items-start gap-4">
            {/* Preview */}
            <div className="flex-shrink-0">
              {imagePreview ? (
                <div className="relative">
                  <img 
                    src={imagePreview} 
                    alt="پیش‌نمایش پروفایل"
                    className="w-24 h-24 rounded-full object-cover border-2 border-border"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      setProfileImage(null);
                      setImagePreview(null);
                      if (fileInputRef.current) fileInputRef.current.value = "";
                    }}
                    className="absolute -top-1 -right-1 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center hover:bg-red-600 transition-colors"
                  >
                    <X size={12} />
                  </button>
                </div>
              ) : (
                <div className="w-24 h-24 rounded-full bg-secondary border-2 border-dashed border-border flex items-center justify-center">
                  <User size={32} className="text-muted-foreground" />
                </div>
              )}
            </div>

            {/* Upload Area */}
            <div className="flex-1">
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-border rounded-xl p-6 text-center hover:border-primary hover:bg-primary/5 transition-colors cursor-pointer"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      setProfileImage(file);
                      setImagePreview(URL.createObjectURL(file));
                    }
                  }}
                />
                <Upload size={20} className="text-muted-foreground mx-auto mb-2" />
                <p className="text-sm font-medium text-foreground mb-1">
                  {imagePreview ? "تغییر تصویر" : "انتخاب تصویر"}
                </p>
                <p className="text-xs text-muted-foreground">
                  JPG, PNG, WebP · حداکثر ۵ مگابایت
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Btn variant="secondary" onClick={() => navigate("consultants")}>
            انصراف
          </Btn>
          <Btn variant="primary" onClick={handleSubmit} disabled={isSubmitting}>
            <Check size={13} />
            {isSubmitting ? "در حال ذخیره…" : "ذخیره تغییرات"}
          </Btn>
        </div>
      </Card>
    </div>
  );
}

// =============================================================================
//  Follow-Ups
// =============================================================================

export { EditConsultantPage };
