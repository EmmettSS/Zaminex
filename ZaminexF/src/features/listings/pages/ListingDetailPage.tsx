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
import { toast, delegationLabel } from "../../../shared/lib/utils";
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, MessageSquare, Sparkles, GripVertical, MoreVertical, Building, History, Flame, Image, Filter } from "lucide-react";
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, ReferenceLine, ScatterChart, Scatter, ZAxis, RadialBarChart, RadialBar } from "recharts";
import { StatusChangeModal } from "../components/StatusChangeModal";
function ListingDetailPage({ 
  navigate, 
  role,
  listing,
  onAction
}: { 
  navigate: (p: any, id?: string | number) => void; 
  role: Role;
  listing?: Listing;
  onAction: (action: any, id: string | number, status?: string) => void;
}) {
  if (!listing) {
    return <div className="p-6 text-center text-sm text-muted-foreground">در حال بارگذاری جزئیات…</div>;
  }

  const isAdmin = role === "admin";
  const [statusModal, setStatusModal] = useState(false);
  const consultantName = listing.assigned_to_detail?.name || "واگذار نشده";

  const statusBadge = (st: string) => {
    const map: Record<string, string> = {
      "ACTIVE": "bg-emerald-100 text-emerald-800",
      "DRAFT": "bg-gray-100 text-gray-800",
      "PAUSED": "bg-amber-100 text-amber-800",
      "SOLD": "bg-purple-100 text-purple-800",
      "EXPIRED": "bg-red-100 text-red-800",
      "ARCHIVED": "bg-blue-100 text-blue-800",
    };
    return <span className={`px-2 py-0.5 rounded text-xs font-semibold ${map[st] || "bg-gray-100"}`}>{toPersianListingStatus(st)}</span>;
  };

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-border bg-white px-6 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-1.5 mb-2 text-xs text-muted-foreground">
              <button onClick={() => navigate("listings")} className="hover:text-foreground">آگهی‌ها</button>
              <ChevronRight size={12} /><span className="text-foreground font-medium">{listing.id}</span>
            </div>
            <h1 className="text-lg font-bold">{listing.title}</h1>
            <div className="flex items-center gap-2 mt-1">
              {statusBadge(listing.status)}
              <span className="text-xs text-muted-foreground">کانال: {toPersianChannel(listing.publish_channel)}</span>
            </div>
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <Btn variant="secondary" size="sm" onClick={() => navigate("edit-listing", listing.id)}><Edit2 size={13} />ویرایش</Btn>
            <Btn variant="outline" size="sm" onClick={() => setStatusModal(true)}><RefreshCw size={13} />تغییر وضعیت</Btn>
            <Btn variant="danger" size="sm" onClick={() => onAction("delete", listing.id)}><Trash2 size={13} />حذف</Btn>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 bg-background">
        <div className="max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2 space-y-5">
            {listing.property_detail && (
              <Card className="p-5 overflow-hidden">
                <h3 className="text-sm font-semibold mb-3">ملک مرتبط</h3>
                <div className="flex gap-4 items-start">
                  {listing.property_detail.image_url ? (
                    <div className="w-28 h-20 flex-shrink-0 rounded-xl overflow-hidden bg-secondary">
                      <img src={listing.property_detail.image_url} alt={listing.property_detail.title || 'ملک'} className="w-full h-full object-cover" />
                    </div>
                  ) : null}
                  <div className="flex-1 min-w-0">
                    <h4 className="text-base font-bold truncate">{listing.property_detail.title || 'عنوان نامشخص'}</h4>
                    <div className="flex flex-wrap gap-2 mt-2 text-xs text-muted-foreground">
                      {listing.property_detail.internal_code && <span>کد: {listing.property_detail.internal_code}</span>}
                      {listing.property_detail.district && <span>· {listing.property_detail.district}</span>}
                      {listing.property_detail.area != null && <span>· مساحت: {(listing.property_detail.area as number).toLocaleString("fa-IR")} متر</span>}
                      {listing.property_detail.floor != null && <span>· طبقه: {listing.property_detail.floor}</span>}
                    </div>
                    <Btn variant="secondary" size="xs" className="mt-3" onClick={() => navigate("property-detail", listing.property_detail.id)}>
                      مشاهده جزئیات ملک
                    </Btn>
                  </div>
                </div>
              </Card>
            )}

            <Card className="p-5">
              <h3 className="text-sm font-semibold mb-3">اطلاعات پایه آگهی</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {[
                  ["شناسه آگهی", listing.id != null ? String(listing.id) : null],
                  ["نوع معامله", (listing.deal_type || listing.transactionType) ? toPersianDeal(listing.deal_type || listing.transactionType) : null],
                  ["اولویت", listing.priority != null ? toPersianPriority(String(listing.priority)) : null],
                  ["آگهی ویژه", listing.is_featured === true ? "بله" : null],
                  ["وضعیت", listing.status ? toPersianListingStatus(listing.status) : null],
                  ["کانال انتشار", listing.publish_channel ? toPersianChannel(listing.publish_channel) : null],
                  ["مشاور", consultantName || null],
                ].filter(([, v]) => v !== null && v !== '').map(([k, v]) => (
                  <div key={k} className="p-3 bg-secondary rounded-xl"><p className="text-xs text-muted-foreground mb-1">{k}</p><p className="text-sm font-semibold">{v}</p></div>
                ))}
              </div>
            </Card>

            {listing.description && (
              <Card className="p-5">
                <h3 className="text-sm font-semibold mb-3">توضیحات</h3>
                <p className="text-sm text-foreground whitespace-pre-line leading-relaxed">{listing.description}</p>
              </Card>
            )}

            {(() => {
              const salePrice = (listing as any).salePrice ?? (listing as any).sale_price;
              const deposit = (listing as any).deposit;
              const monthlyRent = (listing as any).monthlyRent ?? (listing as any).monthly_rent;
              const dealDisplay = (listing as any).dealTypeDisplay || toPersianDeal((listing as any).dealTypeName || (listing as any).deal_type) || "—";
              const hasPrice = salePrice != null || deposit != null || monthlyRent != null;
              if (!hasPrice && !dealDisplay) return null;
              
              const priceRows: { label: string; value: string; hint?: string }[] = [];
              
              // نوع معامله
              // price rows logic حرفه‌ای فارسی
              if (monthlyRent != null && monthlyRent !== '') {
                priceRows.push({ 
                  label: "اجاره ماهانه", 
                  value: fmtShort(Number(monthlyRent) || 0),
                  hint: "برای اجاره"
                });
              }
              if (deposit != null && deposit !== '') {
                const isRahnOnly = dealDisplay.includes("رهن") && !dealDisplay.includes("اجاره");
                const label = isRahnOnly ? "قیمت رهن" : (monthlyRent != null ? "ودیعه" : (dealDisplay.includes("رهن") ? "رهن" : "ودیعه"));
                const hint = isRahnOnly ? "برای رهن کامل" : (monthlyRent != null ? "ودیعه اولیه" : `برای ${dealDisplay}`);
                priceRows.push({ label, value: fmtShort(Number(deposit) || 0), hint });
              }
              if (salePrice != null && salePrice !== '') {
                let label = "قیمت فروش";
                let hint = `برای ${dealDisplay}`;
                if (dealDisplay.includes("فروش")) {
                  label = "قیمت فروش";
                  hint = "برای خرید";
                } else if (dealDisplay.includes("پیش")) {
                  label = "قیمت پیش‌فروش";
                  hint = "پیش‌فروش";
                } else if (dealDisplay) {
                  label = `قیمت ${dealDisplay}`;
                  hint = `برای ${dealDisplay}`;
                }
                priceRows.push({ label, value: fmtShort(Number(salePrice) || 0), hint });
              }

              return (
                <Card className="p-5">
                  <h3 className="text-sm font-semibold mb-3">اطلاعات قیمت و معامله</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="p-3 bg-secondary rounded-xl">
                      <p className="text-xs text-muted-foreground mb-1">نوع معامله</p>
                      <p className="text-sm font-semibold">{dealDisplay}</p>
                    </div>
                    {priceRows.map((row, idx) => (
                      <div key={idx} className="p-3 bg-secondary rounded-xl">
                        <p className="text-xs text-muted-foreground mb-1">{row.label}</p>
                        <p className="text-sm font-semibold">{row.value}</p>
                        {row.hint && <p className="text-xs text-muted-foreground mt-1">{row.hint}</p>}
                      </div>
                    ))}
                    {priceRows.length === 0 && (
                      <div className="p-3 bg-secondary rounded-xl">
                        <p className="text-xs text-muted-foreground mb-1">مبلغ</p>
                        <p className="text-sm font-semibold">توافقی</p>
                      </div>
                    )}
                    {(listing as any).priceDetails && typeof (listing as any).priceDetails === 'object' && Object.keys((listing as any).priceDetails || {}).length > 0 && (
                      <div className="p-3 bg-secondary rounded-xl col-span-1 sm:col-span-2">
                        <p className="text-xs text-muted-foreground mb-1">جزئیات پرداخت</p>
                        <p className="text-sm font-mono">{JSON.stringify((listing as any).priceDetails)}</p>
                      </div>
                    )}
                    {(listing as any).price_details && typeof (listing as any).price_details === 'object' && Object.keys((listing as any).price_details || {}).length > 0 && !(listing as any).priceDetails && (
                      <div className="p-3 bg-secondary rounded-xl col-span-1 sm:col-span-2">
                        <p className="text-xs text-muted-foreground mb-1">جزئیات پرداخت</p>
                        <p className="text-sm font-mono">{JSON.stringify((listing as any).price_details)}</p>
                      </div>
                    )}
                  </div>
                </Card>
              );
            })()}

            {(listing.attributes && Object.values(listing.attributes).some((v) => v !== null && v !== undefined && v !== '')) && (
              <Card className="p-5">
                <h3 className="text-sm font-semibold mb-3">ویژگی‌های تکمیلی آگهی</h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {Object.entries(listing.attributes || {})
                    .map(([k, v]) => {
                      if (v === null || v === undefined || v === '') return null;
                      const display = v === true || v === 'true' ? 'بله' : v === false || v === 'false' ? 'خیر' : String(v);
                      return [k, display];
                    })
                    .filter((item) => item !== null)
                    .map(([k, v]) => (
                      <div key={k} className="p-3 bg-secondary rounded-xl"><p className="text-xs text-muted-foreground mb-1">{k}</p><p className="text-sm font-semibold">{v}</p></div>
                    ))}
                </div>
              </Card>
            )}

            <Card className="p-5">
              <h3 className="text-sm font-semibold mb-3">جزئیات انتشار</h3>
              <div className="grid grid-cols-2 gap-4">
                {[
                  ["تاریخ شروع", listing.start_date ? new Date(listing.start_date).toLocaleDateString("fa-IR", { year: 'numeric', month: 'long', day: 'numeric' }) : null],
                  ["تاریخ پایان", listing.end_date ? new Date(listing.end_date).toLocaleDateString("fa-IR", { year: 'numeric', month: 'long', day: 'numeric' }) : null],
                  ["کانال", listing.publish_channel ? toPersianChannel(listing.publish_channel) : null],
                  ["مشاور", consultantName || null],
                  ["تاریخ ایجاد آگهی", listing.created_at ? new Date(listing.created_at).toLocaleDateString("fa-IR", { year: 'numeric', month: 'long', day: 'numeric' }) : null],
                ].filter(([, v]) => v !== null && v !== '').map(([k, v]) => (
                  <div key={k} className="p-3 bg-secondary rounded-xl"><p className="text-xs text-muted-foreground mb-1">{k}</p><p className="text-sm font-semibold">{v}</p></div>
                ))}
              </div>
            </Card>

            {((listing.effectiveExposureDays != null && listing.effectiveExposureDays > 0) || (listing.delegationIndicator != null && listing.delegationIndicator !== '') || (listing.generatedHighProbLeads != null && listing.generatedHighProbLeads > 0) || (listing.contentRichnessScore != null && listing.contentRichnessScore > 0) || listing.isBurnedListing === true) && (
              <Card className="p-5">
                <h3 className="text-sm font-semibold mb-3">گزارش تحلیلی آگهی</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                  {[
                    ["امتیاز کیفیت", listing.score != null ? `${listing.score}/۱۰۰` : null],
                    ["امتیاز تقاضا (حرارت تعامل)", listing.views != null ? (listing.views ?? 0).toLocaleString("fa-IR") : null],
                    ["روزهای نمایش مؤثر", listing.effectiveExposureDays != null ? `${listing.effectiveExposureDays.toLocaleString("fa-IR")} روز` : null],
                    ["شاخص تفویض", listing.delegationIndicator ? delegationLabel(listing.delegationIndicator) : null],
                    ["سرنخ‌های باکیفیت (≥۷۰٪)", (listing.generatedHighProbLeads ?? 0) > 0 ? (listing.generatedHighProbLeads ?? 0).toLocaleString("fa-IR") : null],
                    ["غنای محتوا", (listing.contentRichnessScore ?? 0) > 0 ? `${listing.contentRichnessScore}/۵` : null],
                    ["وضعیت اتلاف", listing.isBurnedListing === true ? "بله" : null],
                  ].filter(([, v]) => v !== null && v !== '').map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-3 p-3 bg-secondary rounded-xl">
                      <span className="text-xs text-muted-foreground">{k}</span>
                      <span className="text-xs font-semibold">{v}</span>
                    </div>
                  ))}
                </div>
              </Card>
            )}
          </div>

          <div className="space-y-4">
            <Card className="p-4">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">عملیات سریع</h3>
              <div className="space-y-2">
                {isAdmin && listing.status === "DRAFT" && <Btn variant="primary" size="sm" fullWidth onClick={() => onAction("approve", listing.id)}><Check size={13} />تایید و انتشار</Btn>}
                {listing.status === "ARCHIVED"
                  ? <Btn variant="secondary" size="sm" fullWidth onClick={() => onAction("unarchive", listing.id)}><CheckCircle2 size={13} />فعال کردن آگهی</Btn>
                  : <Btn variant="secondary" size="sm" fullWidth onClick={() => onAction("archive", listing.id)}><Archive size={13} />بایگانی آگهی</Btn>}
              </div>
            </Card>
          </div>
        </div>
      </div>

      {statusModal && (
        <StatusChangeModal listing={listing} onClose={() => setStatusModal(false)} onApply={(newSt) => onAction("set_status", listing.id, newSt)} />
      )}
    </div>
  );
}

// =============================================================================
//  Tasks (Kanban, Calendar) — fully driven by the API
// =============================================================================

export { ListingDetailPage };
