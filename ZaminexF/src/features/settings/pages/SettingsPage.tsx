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
const EMPTY_COMPANY = {
  companyName: "",
  licenseNumber: "",
  email: "",
  phone: "",
  address: "",
};

function SettingsPage({ page, navigate, role, csrfToken }: { page: Page; navigate: (p: Page) => void; role: Role; csrfToken: string }) {
  const isAdmin = role === "admin";
  const tabs: { label: string; page: Page }[] = [
    { label: "فضای کاری", page: "settings-workspace" },
    { label: "دسترسی‌ها", page: "settings-permissions" },
  ];

  // Real consultant capabilities, derived from backend queryset/action
  // guards and the consultant sidebar — not a decorative matrix.
  const rolePermissions: { label: string; admin: boolean; consultant: boolean }[] = [
    { label: "ساخت ملک", admin: true, consultant: true },
    { label: "ویرایش ملک خود", admin: true, consultant: true },
    { label: "مشاهده املاک اشتراکی", admin: true, consultant: true },
    { label: "بایگانی ملک خود", admin: true, consultant: true },
    { label: "حذف ملک در دسترس خود", admin: true, consultant: true },
    { label: "اشتراک‌گذاری ملک برای همه مشاوران", admin: true, consultant: false },
    { label: "واگذاری ملک به مشاور دیگر", admin: true, consultant: false },
    { label: "ساخت و ویرایش آگهی خود", admin: true, consultant: true },
    { label: "تایید یا رد آگهی", admin: true, consultant: false },
    { label: "تغییر وضعیت آگهی خود", admin: true, consultant: true },
    { label: "ثبت و ویرایش پیگیری خود", admin: true, consultant: true },
    { label: "ساخت و ویرایش وظیفه خود", admin: true, consultant: true },
    { label: "افزودن و حذف مشاور", admin: true, consultant: false },
    { label: "مشاهده گزارش فعالیت کل سامانه", admin: true, consultant: false },
    { label: "خروجی گزارش ملک‌های در دسترس", admin: true, consultant: true },
    { label: "ویرایش اطلاعات شرکت", admin: true, consultant: false },
    { label: "مدیریت مناطق و ویژگی‌ها", admin: true, consultant: false },
    { label: "ویرایش پروفایل و رمز عبور خود", admin: true, consultant: true },
  ];

  const [company, setCompany] = useState(EMPTY_COMPANY);
  const [companyLoading, setCompanyLoading] = useState(false);
  const [companySaving, setCompanySaving] = useState(false);

  useEffect(() => {
    if (page === "settings-users") navigate("settings-workspace");
  }, [page, navigate]);

  useEffect(() => {
    if (page !== "settings-workspace") return;
    let cancelled = false;
    setCompanyLoading(true);
    (async () => {
      try {
        const res = await apiFetch("/common/api/company-settings/", { method: "GET" }, csrfToken);
        const data = await readJson(res);
        if (cancelled) return;
        if (!res.ok) throw new Error(apiErrorMessage(data, "خطا در دریافت تنظیمات شرکت"));
        setCompany({
          companyName: data.companyName ?? "",
          licenseNumber: data.licenseNumber ?? "",
          email: data.email ?? "",
          phone: data.phone ?? "",
          address: data.address ?? "",
        });
      } catch (err: any) {
        if (cancelled) return;
        setCompany(EMPTY_COMPANY);
        toast({ type: "error", message: err?.message || "خطا در دریافت تنظیمات شرکت" });
      } finally {
        if (!cancelled) setCompanyLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [page, csrfToken]);

  const setCompanyField = (k: string, v: string) => setCompany((p) => ({ ...p, [k]: v }));

  const saveCompany = async () => {
    try {
      setCompanySaving(true);
      const res = await apiFetch("/common/api/company-settings/", { method: "PATCH", body: JSON.stringify(company) }, csrfToken);
      const data = await readJson(res);
      if (!res.ok) throw new Error(apiErrorMessage(data, "خطا در ذخیره تنظیمات"));
      setCompany({
        companyName: data.companyName ?? "",
        licenseNumber: data.licenseNumber ?? "",
        email: data.email ?? "",
        phone: data.phone ?? "",
        address: data.address ?? "",
      });
      toast({ type: "success", message: "تنظیمات ذخیره شد." });
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطا در ذخیره تنظیمات" });
    } finally {
      setCompanySaving(false);
    }
  };
  return (
    <div className="p-6 max-w-4xl mx-auto">
      <PageHeader title="تنظیمات" />
      <div className="flex gap-1 border-b border-border mb-5">{tabs.map((t) => <button key={t.page} onClick={() => navigate(t.page)} className={cx("px-4 py-2.5 text-xs font-semibold border-b-2 -mb-px transition-colors", page === t.page ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground")}>{t.label}</button>)}</div>
      {page === "settings-workspace" && (
        <Card className="p-6 space-y-4">
          <h2 className="text-sm font-semibold">اطلاعات شرکت</h2>
          {companyLoading ? (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
              <Loader2 size={16} className="animate-spin text-primary" />
              در حال بارگذاری تنظیمات…
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-4"><Input label="نام شرکت" value={company.companyName} onChange={(v) => setCompanyField("companyName", v)} readOnly={!isAdmin} /><Input label="شماره پروانه کسب اتحادیه" value={company.licenseNumber} onChange={(v) => setCompanyField("licenseNumber", v)} readOnly={!isAdmin} /><Input label="ایمیل ثبت‌شده" value={company.email} onChange={(v) => setCompanyField("email", v)} readOnly={!isAdmin} /><Input label="تلفن دفتر" value={company.phone} onChange={(v) => setCompanyField("phone", v)} readOnly={!isAdmin} /></div>
              <Input label="آدرس دفتر" value={company.address} onChange={(v) => setCompanyField("address", v)} textarea rows={2} readOnly={!isAdmin} />
              {isAdmin && <Btn variant="primary" onClick={saveCompany} disabled={companySaving || companyLoading}><Check size={13} />{companySaving ? "در حال ذخیره…" : "ذخیره تغییرات"}</Btn>}
            </>
          )}
        </Card>
      )}
      {page === "settings-permissions" && (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground leading-relaxed">
            دسترسی نقش مشاور بر اساس قوانین واقعی سامانه است؛ املاک و آگهی و پیگیری و وظیفه فقط در محدودهٔ خود مشاور، و موارد مدیریتی فقط برای مدیر.
          </p>
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border bg-secondary/30">
                  <tr>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-muted-foreground">دسترسی</th>
                    {["مدیر", "مشاور"].map((r) => (
                      <th key={r} className="text-center px-4 py-3 text-xs font-semibold text-muted-foreground">{r}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {rolePermissions.map((row) => (
                    <tr key={row.label} className="hover:bg-secondary/30">
                      <td className="px-4 py-3 text-xs font-medium">{row.label}</td>
                      {[row.admin, row.consultant].map((allowed, i) => (
                        <td key={i} className="px-4 py-3 text-center">
                          {allowed
                            ? <CheckCircle2 size={14} className="text-emerald-500 mx-auto" />
                            : <XCircle size={14} className="text-muted-foreground/30 mx-auto" />}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

// =============================================================================
//  Consultant Portal
// =============================================================================

export { SettingsPage };
