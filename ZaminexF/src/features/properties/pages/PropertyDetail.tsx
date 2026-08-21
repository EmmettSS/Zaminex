import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { Page, Role, Property, Listing, FollowUp, ConsultantItem, BadgeV, PropertyDetailProps } from "../../../shared/lib/types";
import { fmtShort, toPersianType, toPersianDeal, toPersianPropertyStatus, toPersianTaskStatus, toPersianTaskType, toPersianPriority, toPersianChannel, propertyStatusToUI, toPersianFollowupType, isTaskOverdue, isFollowUpOverdue } from "../../../shared/lib/utils";
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
import { apiFetch, readJson, apiErrorMessage, getCsrfToken } from "../../../shared/lib/apiClient";
import { toast, formatPriceDeviation } from "../../../shared/lib/utils";
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, ReferenceLine, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis } from "recharts";
import { Building2, FileText, CheckSquare, BellRing, User, Users, Activity, Settings, Plus, RefreshCw, Eye, Edit2, Trash2, Archive, Clock, MapPin, Check, X, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, SlidersHorizontal, ArrowUpRight, LayoutGrid, List, Download, Search, MoreVertical, Phone, Mail, Calendar, TrendingUp, Star, Shield, Lock, Key, Send, Loader2, AlertTriangle, Info, XCircle, CheckCircle2, TriangleAlert, Columns, MessageSquare, Sparkles, GripVertical, Building, History, Flame, Image, Zap, LayoutDashboard, Command, Filter, Award, BarChart3, Layers, Circle } from "lucide-react";
import { PROPERTY_STATUS_TO_BACKEND, PROPERTY_STATUSES } from "../../../shared/lib/constants";
import { statusBadge } from "../../../shared/components/ui/StatusBadge";
import { Avatar } from "../../../shared/components/ui/Avatar";
import { GalleryTab } from "../components/GalleryTab";
import { PropertyLocationMap } from "../components/PropertyLocationMap";
import { PropertyAISummary } from "../components/PropertyAISummary";
import { formatJalali } from "../../../shared/lib/jdate";
function PropertyDetail({ navigate, role, property, onArchive, onDelete, onUpdateStatus, onToggleShared, openPropertyEdit, onDeleteImage, onUploadImages, onReorderImages, openPropertyReport }: PropertyDetailProps & { openPropertyReport?: (id: string) => void; }) {
  const [tab, setTab] = useState("نمای کلی");
  const [propStatus, setPropStatus] = useState(() => propertyStatusToUI(property?.propertyStatus));
  const [statusSaving, setStatusSaving] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [propertyListings, setPropertyListings] = useState<Listing[]>([]);
  const [propertyTasks, setPropertyTasks] = useState<any[]>([]);
  const [propertyFollowups, setPropertyFollowups] = useState<FollowUp[]>([]);
  const [listingsLoading, setListingsLoading] = useState(false);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [followupsLoading, setFollowupsLoading] = useState(false);
  const [sharedSaving, setSharedSaving] = useState(false);

  const tabs = ["نمای کلی", "گالری", "آگهی‌ها", "وظایف", "پیگیری‌ها", "گزارش"];

  const buildGallery = (images?: any[] | null) =>
    images && images.length > 0 ? images : [];

  const [gallery, setGallery] = useState<any[]>(() => buildGallery(property?.images));

  const propertyId = property?.id;
  const propertyImages = property?.images;
  const propertyStatus = property?.propertyStatus;
  useEffect(() => {
    setGallery(buildGallery(propertyImages));
    setPropStatus(propertyStatusToUI(propertyStatus));
  }, [propertyId, propertyImages, propertyStatus]);

  // Fetch property-related data
  useEffect(() => {
    if (!propertyId) return;

    // Fetch listings for this property (server-side property= so we are
    // not limited to the first unfiltered page of 20).
    const fetchPropertyListings = async () => {
      setListingsLoading(true);
      try {
        const pageSize = 1000;
        const collected: Listing[] = [];
        let page = 1;
        let total = Infinity;
        while (collected.length < total) {
          const params = new URLSearchParams({
            property: String(propertyId),
            page: String(page),
            page_size: String(pageSize),
            include_sold: "true",
          });
          const res = await apiFetch(`/listings/api/listings/?${params.toString()}`, { method: "GET" });
          if (!res.ok) break;
          const data = await res.json();
          const items = Array.isArray(data) ? data : (data.results ?? []);
          total = Array.isArray(data) ? items.length : (data.count ?? items.length);
          collected.push(...items);
          if (items.length < pageSize) break;
          page += 1;
        }
        setPropertyListings(collected);
      } catch (err) {
        console.error("Error fetching property listings:", err);
      } finally {
        setListingsLoading(false);
      }
    };

    // Fetch tasks for this property
    const fetchPropertyTasks = async () => {
      setTasksLoading(true);
      try {
        const res = await apiFetch(`/tasks/api/tasks/?propertyId=${propertyId}`, { method: "GET" });
        if (res.ok) {
          const data = await res.json();
          const items = Array.isArray(data) ? data : (data.results ?? []);
          setPropertyTasks(items);
        }
      } catch (err) {
        console.error("Error fetching property tasks:", err);
      } finally {
        setTasksLoading(false);
      }
    };

    // Fetch followups for this property
    const fetchPropertyFollowups = async () => {
      setFollowupsLoading(true);
      try {
        const res = await apiFetch(`/followupa/api/followups/?propertyId=${propertyId}`, { method: "GET" });
        if (res.ok) {
          const data = await res.json();
          const items = Array.isArray(data) ? data : (data.results ?? []);
          setPropertyFollowups(items);
        }
      } catch (err) {
        console.error("Error fetching property followups:", err);
      } finally {
        setFollowupsLoading(false);
      }
    };

    fetchPropertyListings();
    fetchPropertyTasks();
    fetchPropertyFollowups();
  }, [propertyId]);

  const handleSaveStatus = async () => {
    if (!onUpdateStatus || statusSaving || !property) return;
    setStatusSaving(true);
    try {
      const backendStatus = PROPERTY_STATUS_TO_BACKEND[propStatus] || propStatus.toUpperCase();
      const ok = await onUpdateStatus(String(property.id), backendStatus);
      if (!ok) setPropStatus(propertyStatusToUI(property.propertyStatus));
    } finally {
      setStatusSaving(false);
    }
  };

  const consultantRef = property?.consultantId ?? property?.consultant ?? null;
  const consultantRoleLabel = (() => {
    const raw = String(property?.consultantRole || "").toUpperCase();
    if (raw === "ADMIN") return "مدیر";
    if (raw === "AGENT") return "مشاور";
    return consultantRef ? "مشاور" : "";
  })();
  const isSharedProperty = Boolean((property as any)?.isShared);
  const showConsultantDetails = Boolean(
    consultantRef && (role === "admin" || (role === "consultant" && !isSharedProperty))
  );
  const openConsultantDetails = () => {
    if (!showConsultantDetails) return;
    if (role === "admin") navigate("consultants", consultantRef as string | number);
    else navigate("my-profile");
  };

  if (!property) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-12 text-slate-500 bg-background">
        <Search className="w-16 h-16 mb-4 opacity-20" />
        <p className="text-sm font-medium">داده‌های ملک بارگذاری نشد.</p>
        <button
          onClick={() => navigate("properties")}
          className="mt-4 text-xs bg-primary text-primary-foreground px-4 py-2 rounded-xl"
        >
          بازگشت به لیست املاک
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      {/* Header Section */}
      <div className="border-b border-border bg-white px-6 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-1.5 mb-2 text-xs text-muted-foreground">
              <button onClick={() => navigate("properties")} className="hover:text-foreground">
                املاک
              </button>
              <ChevronRight size={12} />
              <span className="text-foreground font-medium">{property.internalCode || '—'}</span>
            </div>
            <h1 className="text-lg font-bold">{property.title}</h1>
            <div className="flex items-center gap-2 mt-1">
              {statusBadge(propStatus)}
              <Badge label={toPersianDeal(property.transactionType || 'sale')} variant="muted" />
              {(property as any).isShared && <Badge label="همه مشاوران" variant="info" />}
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <MapPin size={10} />
                {(property as any).locationPath || [(property as any).provinceName, (property as any).cityName, property.district || property.neighborhood].filter(Boolean).join(" / ") || property.district || 'نامشخص'}
              </span>
              <span className="text-xs text-muted-foreground">
                {property.floor != null ? ` · طبقه ${property.floor}` : ''}{property.constructionYear != null ? ` · ساخت ${property.constructionYear}` : ''}
              </span>
            </div>
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <Btn variant="secondary" size="sm" onClick={() => { if (openPropertyEdit) openPropertyEdit(String(property.id)); else navigate("edit-property"); }}>
              <Edit2 size={13} />ویرایش
            </Btn>
            <Btn variant="secondary" size="sm" onClick={() => setConfirmArchive(true)}>
              <Archive size={13} />بایگانی
            </Btn>
            <Btn variant="danger" size="sm" onClick={() => setConfirmDelete(true)}>
              <Trash2 size={13} />حذف
            </Btn>
            <Btn variant="primary" size="sm" onClick={() => navigate("create-listing", property.id)}>
              <Plus size={13} />ساخت آگهی
            </Btn>
            {role === "admin" && onToggleShared && (
              <Btn
                variant={(property as any).isShared ? "danger" : "secondary"}
                size="sm"
                onClick={async () => {
                  setSharedSaving(true);
                  try {
                    await onToggleShared(String(property.id));
                  } finally {
                    setSharedSaving(false);
                  }
                }}
                disabled={sharedSaving}
              >
                {(property as any).isShared ? <User size={13} /> : <Users size={13} />}
                {sharedSaving ? "در حال ذخیره..." : ((property as any).isShared ? `قابل مشاهده فقط برای ${property.consultantName || "مشاور مربوطه"}` : "نمایش برای همه مشاوران")}
              </Btn>
            )}
          </div>
        </div>
        <div className="flex gap-0 mt-4 -mb-4">
          {tabs.map((t) => (
            <button 
              key={t} 
              onClick={() => setTab(t)} 
              className={cx(
                "px-4 py-2.5 text-xs font-medium border-b-2 transition-colors whitespace-nowrap", 
                tab === t ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 p-6 bg-background">
        {tab === "نمای کلی" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 max-w-6xl">
                        <div className="lg:col-span-2 space-y-5">
              <Card className="p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">جزئیات ملک</h3>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">وضعیت:</span>
                    <select 
                      value={propStatus} 
                      onChange={(e) => setPropStatus(e.target.value)} 
                      className="text-xs rounded-lg border border-border bg-input-background px-2.5 py-1.5 outline-none focus:ring-2 focus:ring-ring"
                    >
                      {PROPERTY_STATUSES.map((s) => <option key={s} value={s}>{toPersianPropertyStatus(s)}</option>)}
                    </select>
                    <Btn variant="primary" size="xs" onClick={handleSaveStatus} disabled={statusSaving}>
                      <Check size={11} />{statusSaving ? "در حال ذخیره..." : "ذخیره"}
                    </Btn>
                  </div>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                  {([
                    ["عنوان ملک", property.title || null],
                    ["کد داخلی", property.internalCode || null],
                    ["نوع ملک", property.type ? toPersianType(property.type) : (property as any).propertyTypeDisplay || (property as any).propertyTypeName || null],
                    ["کاربری", (property as any).propertyUsageName || (property as any).propertyUsage?.displayName || (property as any).property_usage?.displayName || (property as any).usage || null],
                    ["نوع معامله", (property.transactionType || (property as any).deal_type) ? toPersianDeal(property.transactionType || (property as any).deal_type) : null],
                    ["مساحت", property.area ? `${(property.area as number).toLocaleString("fa-IR")} متر مربع` : null],
                    ["تعداد خواب", (property.beds || (property as any).rooms) ? String(property.beds || (property as any).rooms) : null],
                    ["طبقه", property.floor != null ? String(property.floor) : null],
                    ["سال ساخت", (property.constructionYear || (property as any).built_year) ? String(property.constructionYear || (property as any).built_year) : null],
                    ["استان", (property as any).provinceName || (property as any).province?.displayName || (property as any).province?.display_name || (property as any).locationPath?.split(" / ")?.[0] || null],
                    ["شهر", (property as any).cityName || (property as any).city?.displayName || (property as any).city?.display_name || (property as any).locationPath?.split(" / ")?.[1] || null],
                    ["محله", (property as any).district || property.neighborhood || (typeof (property as any).district === 'object' ? ((property as any).district?.displayName || (property as any).district?.display_name || (property as any).district?.name) : null) || (property as any).locationPath?.split(" / ")?.slice(-1)?.[0] || null],
                    ["مسیر کامل موقعیت", (property as any).locationPath || ((property as any).provinceName && (property as any).cityName && (property as any).district ? `${(property as any).provinceName} / ${(property as any).cityName} / ${(property as any).district}` : null)],
                  ].filter(([, v]) => v !== null && v !== undefined && v !== '')).map(([k, v]) => (
                    <div key={k} className="p-3 bg-secondary rounded-xl">
                      <p className="text-xs text-muted-foreground mb-1">{k}</p>
                      <p className="text-sm font-semibold">{v as string}</p>
                    </div>
                  ))}
                </div>
                {property.description && (
                  <div className="mt-4">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">توضیحات</p>
                    <p className="text-sm text-foreground leading-relaxed bg-secondary rounded-xl p-3">{property.description}</p>
                  </div>
                )}
              </Card>
              {((property as any).attributeDetails?.length || (property as any).attribute_details?.length || (property.attributes && Object.values(property.attributes).some((v) => v !== null && v !== undefined && v !== ''))) && (
                <Card className="p-5">
                  <h3 className="text-sm font-semibold mb-3">ویژگی‌های تکمیلی</h3>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {( (property as any).attributeDetails || (property as any).attribute_details )?.length ? (
                      ((property as any).attributeDetails || (property as any).attribute_details).map((attr: any) => {
                        const label = attr.displayName || attr.display_name || attr.name;
                        const val = attr.displayValue || attr.display_value || attr.value;
                        const unit = attr.unit ? ` ${attr.unit}` : '';
                        if (val === null || val === undefined || val === '' || (Array.isArray(val) && val.length===0)) return null;
                        const dataType = attr.dataType || attr.data_type;
                        const isoDate = typeof val === "string" && /^\d{4}-\d{2}-\d{2}/.test(val) ? formatJalali(val.slice(0, 10)) : "";
                        const asDate = dataType === "date" || isoDate;
                        const displayText = Array.isArray(val) ? val.join("، ") : (asDate && isoDate ? isoDate : `${val}${unit}`);
                        const finalText = typeof displayText === 'boolean' ? (displayText ? 'بله' : 'خیر') : displayText;
                        return (
                          <div key={attr.name || label} className="p-3 bg-secondary rounded-xl">
                            <p className="text-xs text-muted-foreground mb-1">{label}</p>
                            <p className="text-sm font-semibold">{finalText}</p>
                          </div>
                        );
                      }).filter(Boolean)
                    ) : (
                      Object.entries(property.attributes || {})
                        .map(([k, v]) => {
                          if (v === null || v === undefined || v === '') return null;
                          const display = v === true || v === 'true' ? 'بله' : v === false || v === 'false' ? 'خیر' : String(v);
                          return [k, display] as const;
                        })
                        .filter((item): item is [string, string] => item !== null)
                        .map(([k, v]) => (
                          <div key={k} className="p-3 bg-secondary rounded-xl">
                            <p className="text-xs text-muted-foreground mb-1">{k}</p>
                            <p className="text-sm font-semibold">{v}</p>
                          </div>
                        ))
                    )}
                  </div>
                </Card>
              )}
              {(property.fullAddress || property.address || (property as any).locationPath || (property.latitude != null && property.longitude != null)) && (
              <Card className="p-5">
                <h3 className="text-sm font-semibold mb-2">آدرس کامل</h3>
                {(property.fullAddress || property.address || (property as any).locationPath) && (
                <p className="text-sm text-foreground flex items-start gap-2">
                  <MapPin size={14} className="text-muted-foreground mt-0.5 flex-shrink-0" />
                  <span>
                    {(property as any).locationPath ? `${(property as any).locationPath} - ` : ''}{property.fullAddress || property.address || "—"}
                  </span>
                </p>
                )}
                {(property as any).provinceName || (property as any).cityName || (property as any).district ? (
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    {(property as any).provinceName && <div className="p-2.5 bg-secondary rounded-xl"><p className="text-xs text-muted-foreground">استان</p><p className="text-sm font-medium">{(property as any).provinceName}</p></div>}
                    {(property as any).cityName && <div className="p-2.5 bg-secondary rounded-xl"><p className="text-xs text-muted-foreground">شهر</p><p className="text-sm font-medium">{(property as any).cityName}</p></div>}
                    {(property as any).district && <div className="p-2.5 bg-secondary rounded-xl"><p className="text-xs text-muted-foreground">محله</p><p className="text-sm font-medium">{(property as any).district}</p></div>}
                  </div>
                ) : null}
                {property.latitude != null && property.longitude != null && (
                  <div className="mt-4">
                    <PropertyLocationMap latitude={Number(property.latitude)} longitude={Number(property.longitude)} />
                  </div>
                )}
              </Card>
              )}
            </div>
            {/* Sidebar */}
            {/* Sidebar */}
            <div className="space-y-4">
              <Card className="p-4">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">مشاور</h3>
                <div className={cx("flex items-center gap-3", showConsultantDetails && "mb-3")}>
                  <Avatar 
                    initials={
                      (property.consultantName || (typeof property.consultant === "string" ? property.consultant : ""))
                        .split(" ").map((w) => w[0]).join("") 
                        || "CO"
                    } 
                    size="md" 
                  />
                  <div>
                    <p className="text-sm font-semibold">{property.consultantName || property.consultant || 'مشخص نشده'}</p>
                    {consultantRoleLabel ? (
                      <p className="text-xs text-muted-foreground">{consultantRoleLabel}</p>
                    ) : null}
                  </div>
                </div>
                {showConsultantDetails && (
                  <Btn variant="secondary" size="sm" className="w-full justify-center" onClick={openConsultantDetails}>
                    <Eye size={12} />جزئیات
                  </Btn>
                )}
              </Card>
              <PropertyAISummary property={property} />
              <Card className="p-4">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">شاخص‌های بازار</h3>
                <div className="space-y-3">
                  {([
                    ["روزهای حضور در بازار", property.daysOnMarket != null ? `${property.daysOnMarket.toLocaleString("fa-IR")} روز` : null],
                    ["انحراف قیمت از عرف محله", property.priceDeviationIndex != null ? formatPriceDeviation(property.priceDeviationIndex) : null],
                    ["تعداد تصاویر", (property.imagesCount ?? property.images?.length ?? 0) > 0 ? `${(property.imagesCount ?? property.images?.length ?? 0).toLocaleString("fa-IR")} تصویر` : null],
                    ["مختصات دقیق", property.geoPrecisionFlag ? "ثبت شده" : null],
                    ["امتیاز تقاضا (۳۰ روز)", (property.engagementHeatScore ?? property.views ?? 0) > 0 ? (property.engagementHeatScore ?? property.views ?? 0).toLocaleString("fa-IR") : null],
                  ].filter(([, v]) => v !== null && v !== '' && v !== undefined)).map(([k, v]) => (
                    <div key={k as string} className="flex justify-between items-start gap-2">
                      <span className="text-xs text-muted-foreground">{k}</span>
                      <span className="text-xs font-semibold text-left">{v as string}</span>
                    </div>
                  ))}
                </div>
              </Card>
              <Card className="p-4">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">تعامل</h3>
                <div className="space-y-3">
                  {[["فعالیت اخیر (۳۰ روز)", property.engagementHeatScore ?? property.views ?? 0]].map(([k, v]) => (
                    <div key={k as string} className="flex justify-between items-center">
                      <span className="text-xs text-muted-foreground">{k}</span>
                      <span className="text-sm font-bold font-mono">{(v as number).toLocaleString("fa-IR")}</span>
                    </div>
                  ))}
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    بر اساس پیگیری‌ها و وظایف ثبت‌شده در ۳۰ روز اخیر محاسبه می‌شود.
                  </p>
                </div>
              </Card>
            </div>
          </div>
        )}

        {tab === "گالری" && property && (
          <GalleryTab
            propertyId={String(property.id)}
            gallery={gallery}
            setGallery={setGallery}
            onDeleteImage={onDeleteImage}
            onUploadImages={onUploadImages}
            onReorderImages={onReorderImages}
          />
        )}

        {tab === "گزارش" && (
          <div className="max-w-4xl space-y-4">
            <Card className="p-5">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <h3 className="text-sm font-semibold mb-1">گزارش تحلیلی ملک</h3>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    گزارش کامل این ملک شامل ۱۵ شاخص کلیدی، نمودارها و خروجی CSV در صفحه اختصاصی گزارش‌ها در دسترس است.
                  </p>
                </div>
                {openPropertyReport && (
                  <Btn variant="primary" size="sm" onClick={() => openPropertyReport(String(property.id))}>
                    <BarChart3 size={13} />مشاهده گزارش کامل
                  </Btn>
                )}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm mt-4">
                {[
                  ["قیمت هر مترمربع", property.pricePerSqm != null ? `${property.pricePerSqm.toLocaleString("fa-IR")} تومان` : "—"],
                  ["تعداد تصاویر", String(property.imagesCount ?? property.images?.length ?? 0)],
                  ["روزهای حضور در بازار", property.daysOnMarket != null ? `${property.daysOnMarket.toLocaleString("fa-IR")} روز` : "—"],
                  ["تراکم فضایی", property.spatialDensityRatio != null ? String(property.spatialDensityRatio) : "—"],
                  ["انحراف قیمت از عرف محله", formatPriceDeviation(property.priceDeviationIndex)],
                  ["دقت مختصات جغرافیایی", property.geoPrecisionFlag ? "دقیق" : "نادقیق"],
                  ["امتیاز حرارت تعامل", (property.engagementHeatScore ?? property.views ?? 0).toLocaleString("fa-IR")],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3 p-3 bg-secondary rounded-xl">
                    <span className="text-xs text-muted-foreground">{k}</span>
                    <span className="text-xs font-semibold">{v}</span>
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted-foreground mt-4 leading-relaxed">
                انحراف قیمت برای غربالگری اولیه است؛ عواملی مانند سن بنا و موقعیت دقیق نیز بر ارزش اثر می‌گذارند.
              </p>
            </Card>
            <PropertyAISummary property={property} />
          </div>
        )}

        {tab === "آگهی‌ها" && (
          <div className="max-w-5xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">آگهی‌های این ملک</h3>
              <Btn variant="primary" size="sm" onClick={() => navigate("create-listing", property.id)}>
                <Plus size={13} />ساخت آگهی جدید
              </Btn>
            </div>
            {listingsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 size={24} className="animate-spin text-primary" />
              </div>
            ) : propertyListings.length === 0 ? (
              <EmptyState
                icon={<FileText size={28} />}
                title="آگهی‌ای وجود ندارد"
                description="هنوز آگهی برای این ملک ثبت نشده است."
                action={<Btn variant="primary" size="sm" onClick={() => navigate("create-listing", property.id)}><Plus size={13} />ایجاد اولین آگهی</Btn>}
              />
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {propertyListings.map((l) => {
                  const consultantName = l.assigned_to_detail?.name || property.consultantName || "نامشخص";
                  return (
                    <Card key={l.id} hover onClick={() => navigate("listing-detail", l.id)} className="overflow-hidden">
                      <div 
                        className="h-28 relative flex items-end p-4 bg-gradient-to-br from-slate-400 to-slate-600"
                        style={
                          l.property_detail?.image_url || (property.images && property.images.length > 0 ? property.images[0].url : undefined)
                            ? { backgroundImage: `url(${l.property_detail?.image_url || property.images?.[0]?.url})`, backgroundSize: 'cover', backgroundPosition: 'center' }
                            : undefined
                        }
                      >
                        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/30 to-transparent" />
                        <div className="absolute top-3 left-3 z-10 flex items-center gap-1.5 flex-wrap">
                          {statusBadge(l.status)}
                          <Badge label={(l as any).dealTypeDisplay || toPersianDeal((l as any).dealTypeName) || "—"} variant="muted" />
                        </div>
                      </div>
                      <div className="p-4">
                        <h3 className="text-sm font-semibold mb-1 truncate">{l.title}</h3>
                        <p className="text-xs text-muted-foreground mb-2">
                          کد: {l.id} | ملک: {l.property_detail?.title || property.title || "—"}
                        </p>
                        <div className="flex flex-wrap gap-1 mb-3">
                          {(l.channels || []).map((c) => (
                            <Badge key={c} label={toPersianChannel(c)} variant="muted" />
                          ))}
                        </div>
                        <div className="space-y-1.5">
                          {(() => {
                            const salePrice = (l as any).salePrice ?? (l as any).sale_price;
                            const deposit = (l as any).deposit;
                            const monthlyRent = (l as any).monthlyRent ?? (l as any).monthly_rent;
                            const dealDisplay = (l as any).dealTypeDisplay || toPersianDeal((l as any).dealTypeName) || "";
                            const rows: { label: string; value: any }[] = [];
                            if (monthlyRent != null) {
                              rows.push({ label: "اجاره ماهانه", value: monthlyRent });
                            }
                            if (deposit != null) {
                              let label = "ودیعه";
                              if (dealDisplay.includes("رهن") && !dealDisplay.includes("اجاره")) {
                                label = "برای رهن";
                              } else if (monthlyRent != null) {
                                label = "ودیعه";
                              } else {
                                label = dealDisplay ? `برای ${dealDisplay}` : "ودیعه";
                              }
                              rows.push({ label, value: deposit });
                            }
                            if (salePrice != null) {
                              let label = "قیمت فروش";
                              if (dealDisplay.includes("فروش")) label = "قیمت فروش";
                              else if (dealDisplay.includes("پیش")) label = "پیش‌فروش";
                              else if (dealDisplay) label = `برای ${dealDisplay}`;
                              else label = "قیمت";
                              rows.push({ label, value: salePrice });
                            }
                            if (rows.length === 0) {
                              return <span className="text-xs text-muted-foreground">بدون قیمت • توافقی</span>;
                            }
                            return rows.map((r, idx) => (
                              <div key={idx} className="flex justify-between items-center text-xs">
                                <span className="text-muted-foreground">{r.label}</span>
                                <span className="font-semibold font-mono">{fmtShort(Number(r.value) || 0)}</span>
                              </div>
                            ));
                          })()}
                        </div>
                        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border">
                          <ProfileAvatar
                            initials={consultantName
                              .split(" ")
                              .map((w: string) => w[0])
                              .join("") || "CO"}
                            size="xs"
                          />
                          <span className="text-xs text-muted-foreground truncate flex-1">{consultantName}</span>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {tab === "وظایف" && (
          <div className="max-w-5xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">وظایف مرتبط با این ملک</h3>
              <Btn variant="primary" size="sm" onClick={() => navigate("tasks-kanban")}>
                <Plus size={13} />ایجاد وظیفه
              </Btn>
            </div>
            {tasksLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 size={24} className="animate-spin text-primary" />
              </div>
            ) : propertyTasks.length === 0 ? (
              <EmptyState
                icon={<CheckSquare size={28} />}
                title="وظیفه‌ای وجود ندارد"
                description="هنوز وظیفه‌ای برای این ملک ثبت نشده است."
                action={<Btn variant="primary" size="sm" onClick={() => navigate("tasks-kanban")}><Plus size={13} />ایجاد اولین وظیفه</Btn>}
              />
            ) : (
              <div className="space-y-3">
                {propertyTasks.map((t) => (
                  <Card key={t.id} className="p-4 flex items-start gap-3">
                    <div className="mt-0.5 flex-shrink-0">{t.status === "COMPLETED" ? <CheckCircle2 size={16} className="text-emerald-500" /> : <Circle size={16} className="text-muted-foreground" />}</div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold">{t.title}</p>
                      {t.description && <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{t.description}</p>}
                      <div className="flex items-center gap-3 mt-2 flex-wrap">
                        {statusBadge(t.priority)}
                        <Badge label={t.taskType || toPersianTaskType(t.task_type)} variant="muted" />
                        {isTaskOverdue(t) && <Badge label="از تاریخ گذشته" variant="danger" />}
                        <span className="text-xs text-muted-foreground flex items-center gap-1"><Clock size={10} />سررسید {t.due || t.due_date || "—"}</span>
                        {t.assigned_to_detail?.name && (
                          <div className="flex items-center gap-1.5">
                            <ProfileAvatar imageUrl={t.assigned_to_detail.profile_image} initials={(t.assigned_to_detail.name || "?").split(" ").map((w: string) => w[0]).join("").slice(0, 2)} size="xs" />
                            <span className="text-xs text-muted-foreground">{t.assigned_to_detail.name}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "پیگیری‌ها" && (
          <div className="max-w-5xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">پیگیری‌های این ملک</h3>
              <Btn variant="primary" size="sm" onClick={() => navigate("create-followup")}>
                <Plus size={13} />ثبت پیگیری
              </Btn>
            </div>
            {followupsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 size={24} className="animate-spin text-primary" />
              </div>
            ) : propertyFollowups.length === 0 ? (
              <EmptyState
                icon={<BellRing size={28} />}
                title="پیگیری‌ای وجود ندارد"
                description="هنوز پیگیری برای این ملک ثبت نشده است."
                action={<Btn variant="primary" size="sm" onClick={() => navigate("create-followup")}><Plus size={13} />ثبت اولین پیگیری</Btn>}
              />
            ) : (
              <div className="relative">
                <div className="absolute right-5 top-0 bottom-0 w-px bg-border" />
                <div className="space-y-4">
                  {propertyFollowups.map((fu) => (
                    <div key={fu.id} className="flex gap-4">
                      <div className="relative z-10 flex-shrink-0">
                        <div className={cx("w-10 h-10 rounded-xl flex items-center justify-center text-white", fu.type === "Call" ? "bg-blue-500" : fu.type === "Meeting" ? "bg-purple-500" : fu.type === "Email" ? "bg-slate-400" : "bg-emerald-500")}>
                          {fu.type === "Call" ? <Phone size={14} /> : fu.type === "Meeting" ? <Users size={14} /> : fu.type === "Email" ? <Mail size={14} /> : <MapPin size={14} />}
                        </div>
                      </div>
                      <Card className="flex-1 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">{statusBadge(fu.type)}{statusBadge(fu.status)}{isFollowUpOverdue(fu) && <Badge label="از تاریخ گذشته" variant="danger" />}</div>
                            <h3 className="text-sm font-semibold">{fu.title}</h3>
                            <p className="text-xs text-muted-foreground mt-1">مخاطب: <strong>{fu.contact}</strong> · {fu.consultant} · {fu.date}</p>
                            {fu.outcome && <div className="mt-2 px-3 py-2 bg-secondary rounded-xl text-xs"><span className="font-medium">نتیجه:</span> {fu.outcome}</div>}
                          </div>
                        </div>
                      </Card>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {tab !== "نمای کلی" && tab !== "گالری" && tab !== "آگهی‌ها" && tab !== "وظایف" && tab !== "پیگیری‌ها" && tab !== "گزارش" && (
          <div className="max-w-3xl">
            <EmptyState
              icon={<Info size={28} />}
              title="به‌زودی"
              description={`بخش ${tab} در حال توسعه است و به‌زودی از بک اند تأمین خواهد شد.`}
            />
          </div>
        )}
      </div>

      <ConfirmModal 
        open={confirmArchive} 
        title="بایگانی ملک؟" 
        message="این ملک بایگانی شده و از آگهی‌های فعال مخفی می‌شود. بعداً قابل بازیابی است." 
        onConfirm={() => { 
          if (property) onArchive(String(property.id));
          setConfirmArchive(false); 
        }} 
        onCancel={() => setConfirmArchive(false)} 
      />
      <ConfirmModal 
        open={confirmDelete} 
        danger 
        title="حذف ملک؟" 
        message="این ملک و تمام داده‌های مرتبط با آن برای همیشه حذف خواهند شد. این عملیات غیرقابل بازگشت است." 
        onConfirm={() => { 
          if (property) onDelete(String(property.id));
          setConfirmDelete(false); 
        }} 
        onCancel={() => setConfirmDelete(false)} 
      />
    </div>
  );
}


// =============================================================================
//  Add Property Wizard
// =============================================================================

export { PropertyDetail };
