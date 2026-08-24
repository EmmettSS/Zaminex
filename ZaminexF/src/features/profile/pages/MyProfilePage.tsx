import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { Page, Role, Property, Listing, FollowUp, ConsultantItem, BadgeV, FollowUpCreatePayload } from "../../../shared/lib/types";
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
import { Pagination } from "../../../shared/components/Pagination";
import { DistrictCombobox } from "../../../shared/components/ui/DistrictCombobox";
import { apiFetch, readJson, apiErrorMessage, getCsrfToken } from "../../../shared/lib/apiClient";
import { toast } from "../../../shared/lib/utils";
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, MessageSquare, Sparkles, GripVertical, MoreVertical, Building, History, Flame, Image, Filter } from "lucide-react";
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, ReferenceLine, ScatterChart, Scatter, ZAxis, RadialBarChart, RadialBar } from "recharts";
function MyProfilePage({
  page,
  navigate,
  userName,
  role,
  csrfToken,
  onProfileUpdated,
  districtsList,
}: {
  page: Page;
  navigate: (p: Page) => void;
  userName: string;
  role: Role;
  csrfToken?: string;
  onProfileUpdated?: (newName: string) => void;
  districtsList: string[];
}) {
  const tabs: { label: string; page: Page }[] = [
    { label: "نمای کلی", page: "my-profile" },
    { label: "ویرایش پروفایل", page: "my-profile-edit" },
    { label: "امنیت", page: "my-profile-security" },
  ];

  // Admins use their own dedicated profile API; consultants use theirs.
  // The response shape is identical, so this whole page works for both roles.
  const profileApiBase = role === "admin" ? "/accounts/admins/" : "/accounts/consultants/";

  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editForm, setEditForm] = useState({
    firstName: "",
    lastName: "",
    fullName: "",
    email: "",
    mobile: "",
    branch: "شعبه مرکزی",
    notes: "",
  });
  const [savingProfile, setSavingProfile] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const [passForm, setPassForm] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [savingPassword, setSavingPassword] = useState(false);
  const [secError, setSecError] = useState<string | null>(null);

  const setEdit = (k: string, v: string) => setEditForm((p) => ({ ...p, [k]: v }));
  const setPass = (k: string, v: string) => setPassForm((p) => ({ ...p, [k]: v }));

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`${profileApiBase}me/`, { method: "GET" }, csrfToken);
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
        setEditForm({
          firstName: data.user?.first_name || "",
          lastName: data.user?.last_name || "",
          fullName: data.full_name || "",
          email: data.user?.email || "",
          mobile: data.mobile || "",
          branch: data.branch || "شعبه مرکزی",
          notes: data.notes || "",
        });
      } else {
        throw new Error("خطا در بارگذاری اطلاعات پروفایل");
      }
    } catch (err: any) {
      setError(err.message || "خطا در اتصال به سرور");
    } finally {
      setLoading(false);
    }
  }, [csrfToken, profileApiBase]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleSaveProfile = async () => {
    if (!editForm.firstName.trim() || !editForm.lastName.trim()) {
      toast({ type: "error", message: "نام و نام خانوادگی الزامی است." });
      return;
    }
    if (editForm.mobile.trim() && !/^09\d{9}$/.test(editForm.mobile.trim())) {
      toast({ type: "error", message: "شماره موبایل باید با 09 شروع شود و ۱۱ رقم باشد." });
      return;
    }
    if (editForm.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(editForm.email.trim())) {
      toast({ type: "error", message: "آدرس ایمیل نامعتبر است." });
      return;
    }
    setSavingProfile(true);
    setEditError(null);
    try {
      const payload = {
        first_name: editForm.firstName.trim(),
        last_name: editForm.lastName.trim(),
        full_name: editForm.fullName.trim() || `${editForm.firstName} ${editForm.lastName}`.trim(),
        email: editForm.email.trim(),
        mobile: editForm.mobile.trim(),
        branch: editForm.branch,
        notes: editForm.notes.trim(),
      };
      const res = await apiFetch(`${profileApiBase}me/`, { method: "PATCH", body: JSON.stringify(payload) }, csrfToken);
      const data = await readJson(res);
      if (!res.ok) {
        throw new Error(apiErrorMessage(data, "خطا در ویرایش پروفایل"));
      }
      setProfile(data);
      if (onProfileUpdated && data.full_name) {
        onProfileUpdated(data.full_name);
      }
      toast({ type: "success", message: "پروفایل شما با موفقیت ویرایش شد." });
      navigate("my-profile");
    } catch (err: any) {
      const msg = err.message || "خطا در ویرایش پروفایل";
      setEditError(msg);
      toast({ type: "error", message: msg });
    } finally {
      setSavingProfile(false);
    }
  };

  const handleChangePassword = async () => {
    if (!passForm.currentPassword || !passForm.newPassword || !passForm.confirmPassword) {
      toast({ type: "error", message: "تکمیل تمام فیلدهای رمز عبور الزامی است." });
      return;
    }
    if (passForm.newPassword.length < 8) {
      const msg = "رمز عبور جدید باید حداقل ۸ کاراکتر باشد.";
      setSecError(msg);
      toast({ type: "error", message: msg });
      return;
    }
    if (passForm.newPassword !== passForm.confirmPassword) {
      const msg = "تکرار رمز عبور جدید با رمز عبور جدید مطابقت ندارد.";
      setSecError(msg);
      toast({ type: "error", message: msg });
      return;
    }
    setSavingPassword(true);
    setSecError(null);
    try {
      const res = await apiFetch(`${profileApiBase}change-password/`, {
        method: "POST",
        body: JSON.stringify({
          current_password: passForm.currentPassword,
          new_password: passForm.newPassword,
        }),
      }, csrfToken);
      const data = await readJson(res);
      if (!res.ok) {
        throw new Error(apiErrorMessage(data, "خطا در تغییر رمز عبور"));
      }
      toast({ type: "success", message: "رمز عبور با موفقیت تغییر کرد." });
      setPassForm({ currentPassword: "", newPassword: "", confirmPassword: "" });
      navigate("my-profile");
    } catch (err: any) {
      const msg = err.message || "خطا در تغییر رمز عبور";
      setSecError(msg);
      toast({ type: "error", message: msg });
    } finally {
      setSavingPassword(false);
    }
  };

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <PageHeader title="پروفایل من" />
      <div className="flex gap-1 border-b border-border mb-5">{tabs.map((t) => <button key={t.page} onClick={() => navigate(t.page)} className={cx("px-4 py-2.5 text-xs font-semibold border-b-2 -mb-px transition-colors", page === t.page ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground")}>{t.label}</button>)}</div>
      {loading ? (
        <Card className="p-12 text-center text-sm text-muted-foreground">
          <Loader2 size={24} className="animate-spin mx-auto mb-3 text-primary" />
          در حال بارگذاری اطلاعات پروفایل…
        </Card>
      ) : error && page === "my-profile" ? (
        <Card className="p-8 text-center">
          <p className="text-sm text-red-600 mb-3">{error}</p>
          <Btn variant="secondary" size="sm" onClick={loadProfile}><RefreshCw size={13} />تلاش مجدد</Btn>
        </Card>
      ) : page === "my-profile" ? (
        <div className="space-y-5">
          <Card className="p-6">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="flex items-center gap-5">
                <ProfileAvatar imageUrl={profile?.profile_image} initials={(profile?.full_name || userName || "U").split(" ").map((w: string) => w[0]).join("").slice(0, 2).toUpperCase()} size="lg" />
                <div>
                  <h2 className="text-lg font-bold">{profile?.full_name || userName}</h2>
                  <p className="text-sm text-muted-foreground">{role === "admin" ? "مدیر ارشد" : "مشاور املاک"} · {profile?.branch || "شعبه مرکزی"}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <Badge label={profile?.is_active !== false ? "فعال" : "غیرفعال"} variant={profile?.is_active !== false ? "success" : "muted"} dot />
                    {profile?.user?.email && <span className="text-xs text-muted-foreground bg-secondary px-2.5 py-0.5 rounded-full">{profile.user.email}</span>}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Btn variant="secondary" size="sm" onClick={() => navigate("my-profile-edit")}>
                  <Edit2 size={13} />ویرایش پروفایل
                </Btn>
                <Btn variant="outline" size="sm" onClick={() => navigate("my-profile-security")}>
                  <Lock size={13} />تغییر رمز عبور
                </Btn>
              </div>
            </div>
          </Card>

          <Card className="p-6 space-y-4">
            <h3 className="text-sm font-semibold border-b border-border pb-3">اطلاعات شخصی و سازمانی</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[
                ["نام کامل", profile?.full_name || userName],
                ["نام کاربری", profile?.user?.username || "—"],
                ["آدرس ایمیل", profile?.user?.email || "ثبت نشده"],
                ["شماره موبایل", profile?.mobile || "ثبت نشده"],
                ["شعبه فعالیت", profile?.branch || "شعبه مرکزی"],
                ["تاریخ شروع همکاری", profile?.hired_at || "—"],
              ].map(([lbl, val]) => (
                <div key={lbl as string} className="p-3.5 bg-secondary rounded-xl">
                  <p className="text-xs text-muted-foreground mb-1">{lbl}</p>
                  <p className="text-sm font-semibold truncate">{val as string}</p>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="text-sm font-semibold mb-2">یادداشت‌ها و بیوگرافی</h3>
            <p className="text-sm text-foreground leading-relaxed bg-secondary rounded-xl p-4 min-h-[60px] whitespace-pre-line">
              {profile?.notes || "هیچ یادداشت یا بیوگرافی برای این حساب کاربری ثبت نشده است. از طریق بخش ویرایش پروفایل می‌توانید یادداشتی اضافه کنید."}
            </p>
          </Card>
        </div>
      ) : page === "my-profile-edit" ? (
        <Card className="p-6 space-y-5">
          <div>
            <h2 className="text-base font-semibold">ویرایش پروفایل کاربری</h2>
            <p className="mt-1 text-xs text-muted-foreground">اطلاعات هویتی، شماره تماس و یادداشت‌های پروفایل خود را ویرایش کنید.</p>
          </div>
          {editError && <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-600">{editError}</div>}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input label="نام" value={editForm.firstName} onChange={(v) => setEdit("firstName", v)} required />
            <Input label="نام خانوادگی" value={editForm.lastName} onChange={(v) => setEdit("lastName", v)} required />
            <Input label="نام کامل (نمایشی)" value={editForm.fullName} onChange={(v) => setEdit("fullName", v)} />
            <Input label="آدرس ایمیل" type="email" value={editForm.email} onChange={(v) => setEdit("email", v)} />
            <Input label="شماره موبایل" value={editForm.mobile} onChange={(v) => setEdit("mobile", v)} placeholder="۰۹1xxxxxxxx" />
            <DistrictCombobox label="شعبه فعالیت" value={editForm.branch} onChange={(v) => setEdit("branch", v)} districtsList={districtsList} required />
          </div>
          <Input label="یادداشت / بیوگرافی" value={editForm.notes} onChange={(v) => setEdit("notes", v)} textarea rows={4} placeholder="توضیحات کوتاهی درباره خود، تخصص و زمینه‌های فعالیت ملکی…" />
          <div className="flex items-center justify-end gap-2 pt-3 border-t border-border">
            <Btn variant="secondary" onClick={() => navigate("my-profile")}>انصراف</Btn>
            <Btn variant="primary" onClick={handleSaveProfile} disabled={savingProfile}>
              <Check size={13} />{savingProfile ? "در حال ذخیره…" : "ذخیره تغییرات"}
            </Btn>
          </div>
        </Card>
      ) : page === "my-profile-security" ? (
        <Card className="p-6 space-y-5">
          <div>
            <h2 className="text-base font-semibold">تغییر رمز عبور</h2>
            <p className="mt-1 text-xs text-muted-foreground">برای افزایش امنیت حساب کاربری خود، رمز عبور را به صورت دوره‌ای تغییر دهید.</p>
          </div>
          {secError && <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-600">{secError}</div>}
          <div className="space-y-4 max-w-md">
            <Input label="رمز عبور فعلی" type="password" placeholder="••••••••" value={passForm.currentPassword} onChange={(v) => setPass("currentPassword", v)} required />
            <Input label="رمز عبور جدید" type="password" placeholder="••••••••" value={passForm.newPassword} onChange={(v) => setPass("newPassword", v)} required />
            <Input label="تکرار رمز عبور جدید" type="password" placeholder="••••••••" value={passForm.confirmPassword} onChange={(v) => setPass("confirmPassword", v)} required />
            <p className="text-xs text-muted-foreground">رمز عبور جدید باید حداقل شامل ۸ کاراکتر باشد و توصیه می‌شود از ترکیب حروف و اعداد استفاده کنید.</p>
          </div>
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl flex items-start gap-3 mt-4">
            <Shield className="text-blue-600 flex-shrink-0 mt-0.5" size={16} />
            <div>
              <p className="text-xs font-semibold text-blue-800">نکته امنیتی</p>
              <p className="text-xs text-blue-700 mt-1 leading-relaxed">پس از تغییر موفقیت‌آمیز رمز عبور، نشست فعلی شما فعال باقی می‌ماند و نیازی به ورود مجدد نخواهید داشت.</p>
            </div>
          </div>
          <div className="flex items-center justify-end gap-2 pt-3 border-t border-border">
            <Btn variant="secondary" onClick={() => { setPassForm({ currentPassword: "", newPassword: "", confirmPassword: "" }); navigate("my-profile"); }}>انصراف</Btn>
            <Btn variant="primary" onClick={handleChangePassword} disabled={savingPassword}>
              <Lock size={13} />{savingPassword ? "در حال تغییر رمز…" : "تغییر رمز عبور"}
            </Btn>
          </div>
        </Card>
      ) : null}
    </div>
  );
}

// =============================================================================
//  App Root — bootstraps the SPA from the Django-injected initial data
// =============================================================================

type InitialData = {
  isAuthenticated: boolean;
  loginUrl: string;
  logoutUrl: string;
  csrfToken: string;
  role: "admin" | "consultant" | null;
  userName: string;
  currentConsultantId: string | null;
  initialPage: string;
  next: string;
  pageProps?: {
    properties?: Property[];
    property?: Property;
    consultants?: any[];
    items?: any[];
    pagination?: {
      currentPage: number;
      totalPages: number;
      totalItems: number;
      hasNext: boolean;
      hasPrevious: boolean;
    };
    filters?: Record<string, string>;
  };
};



export { MyProfilePage };
