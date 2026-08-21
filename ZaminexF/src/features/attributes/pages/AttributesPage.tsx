import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { fuzzyFilter, fuzzyMatch } from "../../../shared/lib/fuzzySearch";
import { Page, Role, Property, Listing, FollowUp, ConsultantItem, BadgeV, FollowUpCreatePayload } from "../../../shared/lib/types";
import { fmtShort, toPersianType, toPersianDeal, toPersianPropertyStatus, toPersianTaskStatus, toPersianTaskType, toPersianPriority, toPersianChannel, propertyStatusToUI, toPersianFollowupType, toPersianListingStatus } from "../../../shared/lib/utils";
import { Badge } from "../../../shared/components/ui/Badge";
import { Btn } from "../../../shared/components/ui/Btn";
import { Input } from "../../../shared/components/ui/Input";
import { Card } from "../../../shared/components/ui/Card";
import { SelectField } from "../../../shared/components/ui/SelectField";
import { EmptyState } from "../../../shared/components/ui/EmptyState";
import { PageHeader } from "../../../shared/components/ui/PageHeader";
import { apiFetch, readJson, apiErrorMessage, getCsrfToken } from "../../../shared/lib/apiClient";
import { toast } from "../../../shared/lib/utils";
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, MessageSquare, Sparkles, GripVertical, MoreVertical, Building, History, Flame, Image, Filter, SlidersVertical } from "lucide-react";
import { AttributeCombobox } from "../../../shared/components/ui/AttributeCombobox";

// =============================================================================
//  Base data: custom fields
//
//  Two tabs sharing one layout, mirroring the regions screen:
//    • ویژگی‌ها  — define a field once (label, data type, unit, options)
//    • اتصال‌ها  — decide which property/deal types show it
//
//  Core attributes (متراژ، تعداد اتاق …) map to real database columns. They are
//  listed so an administrator can see the full picture, but their type cannot
//  be changed and they cannot be deleted, so those controls are hidden.
// =============================================================================

type TabKey = "attributes" | "bindings";

type Option = { id: number; value: string; displayName: string; isActive: boolean };

type Attribute = {
  id: number;
  name: string;
  displayName: string;
  dataType: string;
  inputType: string;
  filterType: string;
  entity: "property" | "listing";
  unit: string;
  isFacility: boolean;
  isCore: boolean;
  coreField: string;
  sortOrder: string;
  isActive: boolean;
  options: Option[];
  usageCount: number;
};

type TypeRow = { id: number; name: string; displayName: string };

type Binding = {
  id: number;
  attribute: number;
  attributeDetail: { id: number; name: string; displayName: string; dataType: string; isCore: boolean };
  isRequired: boolean;
  sortOrder: string;
  isActive: boolean;
};

const DATA_TYPES = [
  { label: "متن", value: "text" },
  { label: "عدد صحیح", value: "integer" },
  { label: "عدد اعشاری", value: "decimal" },
  { label: "بله / خیر", value: "boolean" },
  { label: "تاریخ", value: "date" },
  { label: "انتخاب یکی", value: "select" },
  { label: "انتخاب چندتایی", value: "multiselect" },
];

const DATA_TYPE_LABEL: Record<string, string> = Object.fromEntries(
  DATA_TYPES.map((t) => [t.value, t.label])
);

const ENTITIES = [
  { label: "ملک", value: "property" },
  { label: "آگهی", value: "listing" },
];

const FILTER_TYPES = [
  { label: "بدون فیلتر", value: "none" },
  { label: "تطابق دقیق", value: "exact" },
  { label: "بازه‌ای", value: "range" },
  { label: "وجود دارد", value: "exists" },
];

const HAS_OPTIONS = (dataType: string) => dataType === "select" || dataType === "multiselect";

/** Sensible list-filter for a new field so binding it also shows in search. */
const defaultFilterType = (dataType: string) => {
  if (dataType === "integer" || dataType === "decimal" || dataType === "date") return "range";
  if (dataType === "boolean") return "exists";
  return "exact";
};

function AttributesPage({ csrfToken }: { csrfToken: string }) {
  const [tab, setTab] = useState<TabKey>("attributes");

  // --- attributes -------------------------------------------------------
  const [attributes, setAttributes] = useState<Attribute[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [entityFilter, setEntityFilter] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [optionDrafts, setOptionDrafts] = useState<Record<number, string>>({});

  const [form, setForm] = useState({
    displayName: "",
    dataType: "text",
    entity: "property",
    unit: "",
    filterType: "exact",
    isFacility: false,
  });
  const [adding, setAdding] = useState(false);

  // --- bindings ---------------------------------------------------------
  const [propertyTypes, setPropertyTypes] = useState<TypeRow[]>([]);
  const [dealTypes, setDealTypes] = useState<TypeRow[]>([]);
  const [bindKind, setBindKind] = useState<"property" | "listing">("property");
  const [bindTypeId, setBindTypeId] = useState("");
  const [bindings, setBindings] = useState<Binding[]>([]);
  const [bindingsLoading, setBindingsLoading] = useState(false);
  const [bindAttrId, setBindAttrId] = useState("");
  const [binding, setBinding] = useState(false);

  const fetchAttributes = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch("/basics/api/attributes/?all=1", { method: "GET" }, csrfToken);
      if (res.ok) setAttributes(await res.json());
    } catch {
      toast({ type: "error", message: "خطا در دریافت ویژگی‌ها" });
    } finally {
      setLoading(false);
    }
  }, [csrfToken]);

  const fetchTypes = useCallback(async () => {
    try {
      const res = await apiFetch("/basics/api/catalog/", { method: "GET" }, csrfToken);
      if (res.ok) {
        const data = await res.json();
        setPropertyTypes(data.propertyTypes ?? []);
        setDealTypes(data.dealTypes ?? []);
      }
    } catch {
      // Non-fatal: the type dropdown renders empty and the bind button stays
      // disabled, which is the right outcome when the list cannot load.
    }
  }, [csrfToken]);

  useEffect(() => { fetchAttributes(); }, [fetchAttributes]);
  useEffect(() => { fetchTypes(); }, [fetchTypes]);

  // Default to the first type once the catalogue arrives, so the bindings tab
  // is never shown with an empty selector.
  useEffect(() => {
    const list = bindKind === "property" ? propertyTypes : dealTypes;
    if (!bindTypeId && list.length) setBindTypeId(String(list[0].id));
  }, [bindKind, propertyTypes, dealTypes, bindTypeId]);

  const fetchBindings = useCallback(async () => {
    if (!bindTypeId) { setBindings([]); return; }
    setBindingsLoading(true);
    try {
      const path =
        bindKind === "property"
          ? `/basics/api/property-type-attributes/?propertyType=${bindTypeId}`
          : `/basics/api/deal-type-attributes/?dealType=${bindTypeId}`;
      const res = await apiFetch(path, { method: "GET" }, csrfToken);
      if (res.ok) setBindings(await res.json());
    } catch {
      toast({ type: "error", message: "خطا در دریافت اتصال‌ها" });
    } finally {
      setBindingsLoading(false);
    }
  }, [csrfToken, bindKind, bindTypeId]);

  useEffect(() => { if (tab === "bindings") fetchBindings(); }, [tab, fetchBindings]);

  // --- attribute actions --------------------------------------------------

  const handleAdd = async () => {
    if (!form.displayName.trim()) return;
    setAdding(true);
    try {
      const res = await apiFetch(
        "/basics/api/attributes/",
        { method: "POST", body: JSON.stringify({ ...form, displayName: form.displayName.trim() }) },
        csrfToken
      );
      if (res.ok) {
        toast({ type: "success", message: "ویژگی اضافه شد." });
        setForm({ displayName: "", dataType: "text", entity: "property", unit: "", filterType: "exact", isFacility: false });
        await fetchAttributes();
      } else {
        const data = await res.json().catch(() => null);
        toast({ type: "error", message: data?.displayName?.[0] || data?.detail || "خطا در افزودن ویژگی" });
      }
    } catch {
      toast({ type: "error", message: "خطا در ارتباط با سرور" });
    } finally {
      setAdding(false);
    }
  };

  const handleToggleActive = async (row: Attribute) => {
    try {
      const res = await apiFetch(
        `/basics/api/attributes/${row.id}/`,
        { method: "PATCH", body: JSON.stringify({ isActive: !row.isActive }) },
        csrfToken
      );
      if (res.ok) {
        toast({ type: "success", message: row.isActive ? "ویژگی غیرفعال شد." : "ویژگی فعال شد." });
        await fetchAttributes();
      }
    } catch {
      toast({ type: "error", message: "خطا در ارتباط با سرور" });
    }
  };

  const handleDelete = async (row: Attribute) => {
    const warning = row.usageCount
      ? `«${row.displayName}» به ${row.usageCount.toLocaleString("fa-IR")} نوع متصل است. حذف شود؟`
      : `آیا از حذف ویژگی «${row.displayName}» مطمئن هستید؟`;
    if (!confirm(warning)) return;
    try {
      const res = await apiFetch(`/basics/api/attributes/${row.id}/`, { method: "DELETE" }, csrfToken);
      if (res.ok || res.status === 204) {
        toast({ type: "success", message: "ویژگی حذف شد." });
        await fetchAttributes();
      } else {
        const data = await res.json().catch(() => null);
        toast({ type: "error", message: (Array.isArray(data) ? data[0] : data?.detail) || "خطا در حذف ویژگی" });
      }
    } catch {
      toast({ type: "error", message: "خطا در ارتباط با سرور" });
    }
  };

  const handleAddOption = async (attr: Attribute) => {
    const label = (optionDrafts[attr.id] || "").trim();
    if (!label) return;
    try {
      const res = await apiFetch(
        `/basics/api/attributes/${attr.id}/options/`,
        { method: "POST", body: JSON.stringify({ displayName: label }) },
        csrfToken
      );
      if (res.ok) {
        setOptionDrafts((p) => ({ ...p, [attr.id]: "" }));
        await fetchAttributes();
      } else {
        const data = await res.json().catch(() => null);
        toast({ type: "error", message: data?.displayName?.[0] || "خطا در افزودن گزینه" });
      }
    } catch {
      toast({ type: "error", message: "خطا در ارتباط با سرور" });
    }
  };

  const handleDeleteOption = async (attr: Attribute, option: Option) => {
    try {
      const res = await apiFetch(
        `/basics/api/attributes/${attr.id}/options/${option.id}/`,
        { method: "DELETE" },
        csrfToken
      );
      if (res.ok || res.status === 204) {
        await fetchAttributes();
      } else {
        const data = await res.json().catch(() => null);
        toast({ type: "error", message: data?.detail || "خطا در حذف گزینه" });
      }
    } catch {
      toast({ type: "error", message: "خطا در ارتباط با سرور" });
    }
  };

  // --- binding actions ----------------------------------------------------

  const handleBind = async () => {
    if (!bindAttrId || !bindTypeId) return;
    setBinding(true);
    try {
      const path = bindKind === "property"
        ? "/basics/api/property-type-attributes/"
        : "/basics/api/deal-type-attributes/";
      const body = bindKind === "property"
        ? { propertyType: Number(bindTypeId), attribute: Number(bindAttrId) }
        : { dealType: Number(bindTypeId), attribute: Number(bindAttrId) };
      const res = await apiFetch(path, { method: "POST", body: JSON.stringify(body) }, csrfToken);
      if (res.ok) {
        toast({ type: "success", message: "ویژگی به این نوع اضافه شد." });
        setBindAttrId("");
        await fetchBindings();
        await fetchAttributes();
      } else {
        const data = await res.json().catch(() => null);
        const message =
          data?.attribute?.[0] || data?.non_field_errors?.[0] || data?.detail || "خطا در افزودن اتصال";
        toast({ type: "error", message });
      }
    } catch {
      toast({ type: "error", message: "خطا در ارتباط با سرور" });
    } finally {
      setBinding(false);
    }
  };

  const patchBinding = async (row: Binding, payload: Record<string, any>) => {
    const path = bindKind === "property"
      ? `/basics/api/property-type-attributes/${row.id}/`
      : `/basics/api/deal-type-attributes/${row.id}/`;
    try {
      const res = await apiFetch(path, { method: "PATCH", body: JSON.stringify(payload) }, csrfToken);
      if (res.ok) await fetchBindings();
    } catch {
      toast({ type: "error", message: "خطا در ارتباط با سرور" });
    }
  };

  const handleUnbind = async (row: Binding) => {
    if (!confirm(`«${row.attributeDetail.displayName}» از این نوع حذف شود؟`)) return;
    const path = bindKind === "property"
      ? `/basics/api/property-type-attributes/${row.id}/`
      : `/basics/api/deal-type-attributes/${row.id}/`;
    try {
      const res = await apiFetch(path, { method: "DELETE" }, csrfToken);
      if (res.ok || res.status === 204) {
        toast({ type: "success", message: "اتصال حذف شد." });
        await fetchBindings();
        await fetchAttributes();
      }
    } catch {
      toast({ type: "error", message: "خطا در ارتباط با سرور" });
    }
  };

  /** Move a binding up or down by swapping its order with its neighbour. */
  const moveBinding = async (index: number, delta: number) => {
    const target = index + delta;
    if (target < 0 || target >= bindings.length) return;
    const a = bindings[index];
    const b = bindings[target];
    const payload = [
      { id: a.id, sortOrder: Number(b.sortOrder) },
      { id: b.id, sortOrder: Number(a.sortOrder) },
    ];
    if (bindKind !== "property") {
      // The deal-type endpoint has no bulk reorder; two patches are enough.
      await patchBinding(a, { sortOrder: Number(b.sortOrder) });
      await patchBinding(b, { sortOrder: Number(a.sortOrder) });
      return;
    }
    try {
      const res = await apiFetch(
        "/basics/api/property-type-attributes/reorder/",
        { method: "POST", body: JSON.stringify(payload) },
        csrfToken
      );
      if (res.ok) await fetchBindings();
    } catch {
      toast({ type: "error", message: "خطا در ارتباط با سرور" });
    }
  };

  // --- derived ------------------------------------------------------------

  const filtered = useMemo(() => {
    const searchFiltered = search ? fuzzyFilter(attributes, search, (a) => `${a.displayName} ${a.name} ${a.unit}`) : attributes;
    return searchFiltered.filter((a) => !entityFilter || a.entity === entityFilter);
  }, [attributes, search, entityFilter]);

  const boundIds = new Set(bindings.map((b) => b.attribute));
  const bindableAttributes = attributes.filter(
    (a) => a.isActive && a.entity === bindKind && !boundIds.has(a.id)
  );

  const currentTypes = bindKind === "property" ? propertyTypes : dealTypes;

  const subtitleFor = (a: Attribute) => {
    const parts = [DATA_TYPE_LABEL[a.dataType] ?? a.dataType];
    if (a.unit) parts.push(a.unit);
    parts.push(a.entity === "property" ? "ملک" : "آگهی");
    if (a.isCore) parts.push("فیلد ثابت");
    else parts.push(`${a.usageCount.toLocaleString("fa-IR")} نوع`);
    return parts.join(" · ");
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">
      <PageHeader title="مدیریت ویژگی‌ها" subtitle="تعریف فیلدهای سفارشی و اتصال آن‌ها به نوع ملک و نوع معامله" />

      {/* Tabs */}
      <div className="flex items-center gap-1 p-1 bg-secondary rounded-xl w-fit">
        {([["attributes", "ویژگی‌ها"], ["bindings", "اتصال به انواع"]] as [TabKey, string][]).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={cx(
              "px-4 py-2 text-xs font-medium rounded-lg transition-colors",
              tab === key ? "bg-white text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "attributes" && (
        <>
          {/* Add new attribute */}
          <Card className="p-5">
            <h3 className="text-sm font-semibold mb-3">افزودن ویژگی جدید</h3>
            <div className="grid grid-cols-2 gap-4">
              <Input label="نام ویژگی" placeholder="مثال: جهت ساختمان" value={form.displayName} onChange={(v) => setForm((p) => ({ ...p, displayName: v }))} />
              <SelectField
                label="نوع داده"
                value={form.dataType}
                onChange={(v) => setForm((p) => ({
                  ...p,
                  dataType: v,
                  isFacility: v === "boolean" ? p.isFacility : false,
                  filterType: defaultFilterType(v),
                }))}
                options={DATA_TYPES}
              />
            </div>
            <div className="grid grid-cols-3 gap-4 mt-4">
              <SelectField label="مربوط به" value={form.entity} onChange={(v) => setForm((p) => ({ ...p, entity: v }))} options={ENTITIES} />
              <SelectField label="نوع فیلتر" value={form.filterType} onChange={(v) => setForm((p) => ({ ...p, filterType: v }))} options={FILTER_TYPES} />
              <Input label="واحد (اختیاری)" placeholder="مثال: متر مربع" value={form.unit} onChange={(v) => setForm((p) => ({ ...p, unit: v }))} />
            </div>
            <div className="flex items-center justify-between mt-4">
              <label className="flex items-center gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.isFacility}
                  onChange={(e) => {
                    const on = e.target.checked;
                    setForm((p) => on
                      ? { ...p, isFacility: true, dataType: "boolean", filterType: "exists" }
                      : { ...p, isFacility: false });
                  }}
                  className="w-4 h-4 rounded border-border accent-primary"
                />
                <span className="text-sm text-foreground">جزو امکانات رفاهی است</span>
              </label>
              <Btn variant="primary" onClick={handleAdd} disabled={adding || !form.displayName.trim()}>
                {adding ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
                افزودن
              </Btn>
            </div>
            {HAS_OPTIONS(form.dataType) && (
              <p className="text-xs text-muted-foreground mt-2.5">پس از ایجاد، گزینه‌های این ویژگی را از فهرست زیر اضافه کنید.</p>
            )}
          </Card>

          {/* Attribute list */}
          <Card className="overflow-hidden">
            <div className="px-5 py-3.5 border-b border-border bg-secondary/30">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold">لیست ویژگی‌ها ({filtered.length.toLocaleString("fa-IR")})</h3>
                <div className="flex items-center gap-2">
                  <select
                    value={entityFilter}
                    onChange={(e) => setEntityFilter(e.target.value)}
                    className="px-2.5 py-2 text-xs rounded-xl border border-border bg-white outline-none focus:ring-2 focus:ring-ring"
                  >
                    <option value="">همه</option>
                    <option value="property">ملک</option>
                    <option value="listing">آگهی</option>
                  </select>
                  <div className="relative max-w-xs">
                    <Search size={12} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                    <input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="جستجوی ویژگی..."
                      className="w-full pl-3 pr-8 py-2 text-xs rounded-xl border border-border bg-white outline-none focus:ring-2 focus:ring-ring"
                    />
                  </div>
                </div>
              </div>
            </div>

            {loading ? (
              <div className="p-12 text-center text-sm text-muted-foreground">
                <Loader2 size={24} className="animate-spin mx-auto mb-3 text-primary" />
                در حال بارگذاری...
              </div>
            ) : filtered.length === 0 ? (
              <EmptyState
                icon={<SlidersHorizontal size={28} />}
                title="ویژگی‌ای یافت نشد"
                description={search ? "با عبارت جستجوی شما موردی پیدا نشد." : "هنوز ویژگی‌ای ثبت نشده است."}
              />
            ) : (
              <div className="divide-y divide-border">
                {filtered.map((a) => (
                  <div key={a.id}>
                    <div className="flex items-center justify-between gap-3 px-5 py-3.5 hover:bg-secondary/20 transition-colors">
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <div className={cx("w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0", a.isActive ? "bg-emerald-100 text-emerald-600" : "bg-gray-100 text-gray-400")}>
                          {a.isFacility ? <Zap size={14} /> : <SlidersHorizontal size={14} />}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className={cx("text-sm font-semibold truncate", !a.isActive && "text-gray-400")}>{a.displayName}</p>
                          <p className="text-xs text-muted-foreground mt-0.5">{subtitleFor(a)}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        {a.isCore && <Badge label="ثابت" variant="info" />}
                        <Badge label={a.isActive ? "فعال" : "غیرفعال"} variant={a.isActive ? "success" : "muted"} dot />
                        {HAS_OPTIONS(a.dataType) && (
                          <Btn
                            variant="ghost"
                            size="xs"
                            onClick={() => setExpanded(expanded === a.id ? null : a.id)}
                            title="گزینه‌ها"
                          >
                            {expanded === a.id ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                          </Btn>
                        )}
                        <Btn variant="ghost" size="xs" onClick={() => handleToggleActive(a)} title={a.isActive ? "غیرفعال کردن" : "فعال کردن"}>
                          {a.isActive ? <Archive size={12} /> : <CheckCircle2 size={12} />}
                        </Btn>
                        {!a.isCore && (
                          <Btn variant="ghost" size="xs" onClick={() => handleDelete(a)} className="!text-red-500 hover:!bg-red-50" title="حذف">
                            <Trash2 size={12} />
                          </Btn>
                        )}
                      </div>
                    </div>

                    {/* Options editor, shown inline for select attributes */}
                    {expanded === a.id && HAS_OPTIONS(a.dataType) && (
                      <div className="px-5 pb-4 pt-1 bg-secondary/20">
                        <div className="flex flex-wrap gap-2 mb-3">
                          {a.options.length === 0 ? (
                            <p className="text-xs text-muted-foreground">هنوز گزینه‌ای تعریف نشده است.</p>
                          ) : (
                            a.options.map((o) => (
                              <span key={o.id} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs bg-white border border-border">
                                {o.displayName}
                                <button type="button" onClick={() => handleDeleteOption(a, o)} className="text-muted-foreground hover:text-red-500" title="حذف گزینه">
                                  <X size={10} />
                                </button>
                              </span>
                            ))
                          )}
                        </div>
                        <div className="flex gap-2">
                          <input
                            value={optionDrafts[a.id] || ""}
                            onChange={(e) => setOptionDrafts((p) => ({ ...p, [a.id]: e.target.value }))}
                            onKeyDown={(e) => { if (e.key === "Enter") handleAddOption(a); }}
                            placeholder="نام گزینه جدید…"
                            className="flex-1 px-3 py-2 text-xs rounded-xl border border-border bg-white outline-none focus:ring-2 focus:ring-ring"
                          />
                          <Btn variant="secondary" size="xs" onClick={() => handleAddOption(a)} disabled={!(optionDrafts[a.id] || "").trim()}>
                            <Plus size={12} />افزودن گزینه
                          </Btn>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      )}

      {tab === "bindings" && (
        <>
          {/* Pick a type, then attach attributes to it */}
          <Card className="p-5">
            <h3 className="text-sm font-semibold mb-3">انتخاب نوع</h3>
            <div className="grid grid-cols-2 gap-4">
              <SelectField
                label="دسته"
                value={bindKind}
                onChange={(v) => { setBindKind(v as "property" | "listing"); setBindTypeId(""); setBindAttrId(""); }}
                options={[{ label: "نوع ملک", value: "property" }, { label: "نوع معامله", value: "listing" }]}
              />
              <SelectField
                label={bindKind === "property" ? "نوع ملک" : "نوع معامله"}
                value={bindTypeId}
                onChange={(v) => { setBindTypeId(v); setBindAttrId(""); }}
                options={currentTypes.map((t) => ({ label: t.displayName, value: String(t.id) }))}
                placeholder="انتخاب کنید"
              />
            </div>
            <div className="flex gap-3 items-end mt-4">
              <div className="flex-1">
                <label className="text-sm font-medium text-foreground mb-1.5 block">افزودن ویژگی به این نوع</label>
                <AttributeCombobox
                  value={bindAttrId}
                  onChange={setBindAttrId}
                  attributes={bindableAttributes.map((a) => ({ id: a.id, displayName: a.displayName, name: a.name, dataType: a.dataType, isCore: a.isCore, isFacility: a.isFacility }))}
                  placeholder={bindableAttributes.length ? "انتخاب ویژگی" : "ویژگی قابل افزودنی نیست"}
                />
              </div>
              <Btn variant="primary" onClick={handleBind} disabled={binding || !bindAttrId || !bindTypeId}>
                {binding ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
                افزودن
              </Btn>
            </div>
          </Card>

          <Card className="overflow-hidden">
            <div className="px-5 py-3.5 border-b border-border bg-secondary/30">
              <h3 className="text-sm font-semibold">
                ویژگی‌های این نوع ({bindings.length.toLocaleString("fa-IR")})
              </h3>
            </div>

            {bindingsLoading ? (
              <div className="p-12 text-center text-sm text-muted-foreground">
                <Loader2 size={24} className="animate-spin mx-auto mb-3 text-primary" />
                در حال بارگذاری...
              </div>
            ) : bindings.length === 0 ? (
              <EmptyState
                icon={<Layers size={28} />}
                title="ویژگی‌ای متصل نشده"
                description="برای این نوع هنوز ویژگی‌ای تعریف نشده است."
              />
            ) : (
              <div className="divide-y divide-border">
                {bindings.map((b, i) => (
                  <div key={b.id} className="flex items-center justify-between gap-3 px-5 py-3.5 hover:bg-secondary/20 transition-colors">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <div className="flex flex-col">
                        <button type="button" onClick={() => moveBinding(i, -1)} disabled={i === 0} className="text-muted-foreground hover:text-foreground disabled:opacity-30" title="بالاتر">
                          <ChevronUp size={12} />
                        </button>
                        <button type="button" onClick={() => moveBinding(i, 1)} disabled={i === bindings.length - 1} className="text-muted-foreground hover:text-foreground disabled:opacity-30" title="پایین‌تر">
                          <ChevronDown size={12} />
                        </button>
                      </div>
                      <div className={cx("w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0", b.isActive ? "bg-emerald-100 text-emerald-600" : "bg-gray-100 text-gray-400")}>
                        <SlidersHorizontal size={14} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className={cx("text-sm font-semibold truncate", !b.isActive && "text-gray-400")}>{b.attributeDetail.displayName}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {DATA_TYPE_LABEL[b.attributeDetail.dataType] ?? b.attributeDetail.dataType}
                          {b.attributeDetail.isCore ? " · فیلد ثابت" : ""}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <label className="flex items-center gap-1.5 cursor-pointer" title="پر کردن این فیلد اجباری باشد">
                        <input
                          type="checkbox"
                          checked={b.isRequired}
                          onChange={() => patchBinding(b, { isRequired: !b.isRequired })}
                          className="w-3.5 h-3.5 rounded border-border accent-primary"
                        />
                        <span className="text-xs text-muted-foreground">اجباری</span>
                      </label>
                      <Btn variant="ghost" size="xs" onClick={() => patchBinding(b, { isActive: !b.isActive })} title={b.isActive ? "غیرفعال کردن" : "فعال کردن"}>
                        {b.isActive ? <Archive size={12} /> : <CheckCircle2 size={12} />}
                      </Btn>
                      <Btn variant="ghost" size="xs" onClick={() => handleUnbind(b)} className="!text-red-500 hover:!bg-red-50" title="حذف اتصال">
                        <Trash2 size={12} />
                      </Btn>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}

export { AttributesPage };
