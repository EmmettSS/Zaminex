import React, { useState, useEffect, useCallback, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { Page, Role, Property, Listing, ConsultantItem } from "../../../shared/lib/types";
import { fmtShort, toPersianDeal, toPersianListingStatus, toPersianChannel } from "../../../shared/lib/utils";
import { Badge } from "../../../shared/components/ui/Badge";
import { Btn } from "../../../shared/components/ui/Btn";
import { Card } from "../../../shared/components/ui/Card";
import { ProfileAvatar } from "../../../shared/components/ui/ProfileAvatar";
import { KpiCard } from "../../../shared/components/ui/KpiCard";
import { PageHeader } from "../../../shared/components/ui/PageHeader";
import { ConfirmModal } from "../../../shared/components/ConfirmModal";
import { ActionMenu } from "../../../shared/components/ActionMenu";
import { Pagination } from "../../../shared/components/Pagination";
import { BulkActionBar } from "../../../shared/components/BulkActionBar";
import { PropertyCombobox } from "../../../shared/components/ui/PropertyCombobox";
import { ConsultantCombobox } from "../../../shared/components/ui/ConsultantCombobox";
import { PriceRangeFilter } from "../../../shared/components/ui/PriceRangeFilter";
import { DealTypeCombobox } from "../../../shared/components/ui/DealTypeCombobox";
import { useBasicsCatalog } from "../../../shared/lib/useAttributeSchema";
import { apiFetch } from "../../../shared/lib/apiClient";
import { FileText, Eye, Search, SlidersHorizontal, LayoutGrid, List, Plus, CheckCircle2, Archive, Trash2, Edit2, RefreshCw, Check, Award, Layers } from "lucide-react";
import { StatusChangeModal } from "../components/StatusChangeModal";

function ListingsPage({
  navigate,
  role,
  currentConsultantId,
  consultants,
  properties,
  listings: initialListings,
  onAction,
  loading: initialLoading,
}: {
  navigate: (p: any, id?: string | number) => void;
  role?: Role;
  currentConsultantId?: string | null;
  consultants: ConsultantItem[];
  properties: Property[];
  listings: Listing[];
  onAction: (action: any, id: string | number) => void;
  loading: boolean;
}) {
  const isAdmin = role === "admin";
  const [view, setView] = useState<"table" | "card">("card");
  const [search, setSearch] = useState("");
  const [showSoldOnly, setShowSoldOnly] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({
    status: "",
    consultant: "",
    property: "",
    dealType: "",
    rentMin: "",
    rentMax: "",
    depositMin: "",
    depositMax: "",
    saleMin: "",
    saleMax: "",
  });
  const { catalog } = useBasicsCatalog();
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [statusModal, setStatusModal] = useState<Listing | null>(null);

  // Server-side pagination
  const [serverListings, setServerListings] = useState<Listing[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [activeCount, setActiveCount] = useState(0);
  const [serverLoading, setServerLoading] = useState(false);

  const setFilter = (k: string, v: string) => {
    setFilters((p) => ({ ...p, [k]: v }));
    setCurrentPage(1);
    setSelected(new Set());
  };

  const toggleSort = (col: string) => {
    if (sortCol === col) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortCol(col);
      setSortDir("asc");
    }
  };
  const SortIcon = ({ col }: { col: string }) =>
    sortCol !== col ? (
      <span className="text-muted-foreground/30 mr-1">↕</span>
    ) : sortDir === "asc" ? (
      <span className="text-primary mr-1">↑</span>
    ) : (
      <span className="text-primary mr-1">↓</span>
    );

  const fetchServerListings = useCallback(async (opts?: { silent?: boolean }) => {
    if (!opts?.silent) setServerLoading(true);
    try {
      const params = new URLSearchParams();
      params.append("page", String(currentPage));
      params.append("page_size", String(pageSize));
      if (search.trim()) params.append("q", search.trim());
      
      if (showSoldOnly) {
        params.append("status", "SOLD");
        params.append("show_sold", "true");
      } else if (filters.status) {
        params.append("status", filters.status);
      }

      if (filters.consultant) params.append("consultant", filters.consultant);
      if (filters.property) params.append("property", filters.property);
      if (filters.dealType) params.append("dealType", filters.dealType);
      if (filters.rentMin) params.append("rentMin", filters.rentMin);
      if (filters.rentMax) params.append("rentMax", filters.rentMax);
      if (filters.depositMin) params.append("depositMin", filters.depositMin);
      if (filters.depositMax) params.append("depositMax", filters.depositMax);
      if (filters.saleMin) params.append("saleMin", filters.saleMin);
      if (filters.saleMax) params.append("saleMax", filters.saleMax);

      const url = `/listings/api/listings/?${params.toString()}`;
      const res = await apiFetch(url, { method: "GET" });
      if (!res.ok) throw new Error("خطا در دریافت آگهی‌ها");
      const data = await res.json();
      const rows = Array.isArray(data) ? data : (data.results ?? []);
      const count = Array.isArray(data) ? data.length : (data.count ?? rows.length);
      setServerListings(rows);
      setTotalCount(count);

      if (showSoldOnly || (filters.status && filters.status !== "ACTIVE")) {
        setActiveCount(rows.filter((l: Listing) => l.status === "ACTIVE").length);
      } else if (filters.status === "ACTIVE") {
        setActiveCount(count);
      } else {
        const activeParams = new URLSearchParams(params);
        activeParams.set("status", "ACTIVE");
        activeParams.set("page", "1");
        activeParams.set("page_size", "1");
        const activeRes = await apiFetch(`/listings/api/listings/?${activeParams.toString()}`, { method: "GET" });
        if (activeRes.ok) {
          const activeData = await activeRes.json();
          const activeRows = Array.isArray(activeData) ? activeData : (activeData.results ?? []);
          setActiveCount(Array.isArray(activeData) ? activeData.length : (activeData.count ?? activeRows.length));
        } else {
          setActiveCount(rows.filter((l: Listing) => l.status === "ACTIVE").length);
        }
      }
    } catch (e) {
      console.error(e);
      setServerListings([]);
      setTotalCount(0);
      setActiveCount(0);
    } finally {
      if (!opts?.silent) setServerLoading(false);
    }
  }, [currentPage, pageSize, search, filters, showSoldOnly]);

  useEffect(() => {
    fetchServerListings();
  }, [fetchServerListings]);

  const runAction = useCallback(
    (action: any, id: string | number) => {
      return Promise.resolve(onAction(action, id)).finally(() => {
        void fetchServerListings({ silent: true });
      });
    },
    [onAction, fetchServerListings]
  );

  const hasAdvancedFilters = !!(
    filters.consultant ||
    filters.property ||
    filters.dealType ||
    filters.rentMin ||
    filters.rentMax ||
    filters.depositMin ||
    filters.depositMax ||
    filters.saleMin ||
    filters.saleMax
  );
  const advancedCount = [
    filters.consultant,
    filters.property,
    filters.dealType,
    filters.rentMin,
    filters.rentMax,
    filters.depositMin,
    filters.depositMax,
    filters.saleMin,
    filters.saleMax,
  ].filter(Boolean).length;

  const sorted = useMemo(() => {
    const arr = [...serverListings];
    if (!sortCol) return arr;
    return arr.sort((a, b) => {
      const av = (a as any)[sortCol];
      const bv = (b as any)[sortCol];
      if (typeof av === "number") return sortDir === "asc" ? av - bv : bv - av;
      return sortDir === "asc" ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
  }, [serverListings, sortCol, sortDir]);

  const paginated = sorted;

  const toggleSelect = (id: string) =>
    setSelected((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  const toggleAll = () =>
    setSelected((s) => (s.size === paginated.length ? new Set() : new Set(paginated.map((l) => String(l.id)))));

  const rowActions = (l: Listing) => [
    { label: "مشاهده جزئیات", icon: <Eye size={12} />, onClick: () => navigate("listing-detail", l.id) },
    { label: "ویرایش آگهی", icon: <Edit2 size={12} />, onClick: () => navigate("edit-listing", l.id) },
    { label: "تغییر وضعیت", icon: <RefreshCw size={12} />, onClick: () => setStatusModal(l) },
    { label: "ثبت واگذاری / فروش", icon: <CheckCircle2 size={12} />, onClick: () => runAction("sold", l.id) },
    l.status === "ARCHIVED"
      ? { label: "فعال کردن", icon: <CheckCircle2 size={12} />, onClick: () => runAction("unarchive", l.id) }
      : { label: "بایگانی", icon: <Archive size={12} />, onClick: () => runAction("archive", l.id) },
    { label: "حذف", icon: <Trash2 size={12} />, onClick: () => setConfirmDelete(String(l.id)), danger: true },
  ];

  // List of listings to compute dynamic KPI statistics from
  const currentListings = useMemo(() => {
    return serverListings.length > 0 ? serverListings : initialListings;
  }, [serverListings, initialListings]);

  // Dynamic Total Views / کل بازدیدها
  const totalViews = useMemo(() => {
    return currentListings.reduce((sum, l) => {
      const v = (l as any).views ?? (l as any).engagementHeatScore ?? 0;
      return sum + (typeof v === "number" ? v : Number(v) || 0);
    }, 0);
  }, [currentListings]);

  // Formatted Total Views
  const formattedTotalViews = useMemo(() => {
    if (totalViews >= 10000) {
      return `${(totalViews / 1000).toLocaleString("fa-IR", { maximumFractionDigits: 1 })}K`;
    }
    return totalViews.toLocaleString("fa-IR");
  }, [totalViews]);

  // Dynamic Average Quality Score / میانگین امتیاز کیفیت
  const avgQualityScore = useMemo(() => {
    if (currentListings.length === 0) return 0;
    
    const totalScore = currentListings.reduce((sum, l) => {
      let score = (l as any).score;
      if (score == null) {
        const richness = (l as any).contentRichnessScore;
        if (richness != null) score = Math.round((richness / 5) * 100);
      }
      if (score == null) score = 70;
      return sum + (typeof score === "number" ? score : Number(score) || 70);
    }, 0);

    return Math.round(totalScore / currentListings.length);
  }, [currentListings]);

  const statusBadge = (st: string) => {
    const map: Record<string, string> = {
      ACTIVE: "bg-emerald-100 text-emerald-800",
      DRAFT: "bg-gray-100 text-gray-800",
      PAUSED: "bg-amber-100 text-amber-800",
      SOLD: "bg-purple-100 text-purple-800",
      EXPIRED: "bg-red-100 text-red-800",
      ARCHIVED: "bg-blue-100 text-blue-800",
    };
    return <span className={`px-2 py-0.5 rounded text-xs font-semibold ${map[st] || "bg-gray-100"}`}>{toPersianListingStatus(st)}</span>;
  };

  const isLoading = initialLoading || serverLoading;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <PageHeader
        title="مرکز آگهی‌ها"
        subtitle={`${activeCount.toLocaleString("fa-IR")} فعال · ${totalCount.toLocaleString("fa-IR")} یافت شده`}
        actions={
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs font-medium cursor-pointer bg-amber-50 hover:bg-amber-100/80 text-amber-900 border border-amber-200/80 px-3 py-1.5 rounded-xl transition-colors select-none">
              <input
                type="checkbox"
                checked={showSoldOnly}
                onChange={(e) => {
                  setShowSoldOnly(e.target.checked);
                  setCurrentPage(1);
                  setSelected(new Set());
                }}
                className="w-3.5 h-3.5 rounded text-amber-600 focus:ring-amber-500 border-amber-300"
              />
              <span>نمایش آگهی‌های فروخته‌شده</span>
            </label>
            <Btn variant="primary" size="sm" onClick={() => navigate("create-listing")}>
              <Plus size={13} />
              آگهی جدید
            </Btn>
          </div>
        }
      />

      {/* Toolbar — always visible so the search input never loses focus */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <div className="relative min-w-48 flex-1 max-w-64">
          <Search size={13} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setCurrentPage(1);
            }}
            placeholder="جستجوی آگهی…"
            className="w-full pl-10 pr-3 py-2 text-sm rounded-xl border border-border bg-white outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div className="flex gap-1 flex-wrap">
          {["", "ACTIVE", "DRAFT", "PAUSED", "ARCHIVED"].map((s) => (
            <button
              key={s || "all"}
              onClick={() => setFilter("status", s)}
              className={cx(
                "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1",
                filters.status === s ? "bg-primary text-white shadow-sm" : "bg-white border border-border hover:bg-secondary"
              )}
            >
              {s ? toPersianListingStatus(s) : "همه"}
            </button>
          ))}
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={cx(
            "flex items-center gap-1.5 px-3 py-2 rounded-xl border text-xs font-medium transition-colors",
            showFilters || hasAdvancedFilters ? "border-primary bg-primary/5 text-primary" : "border-border bg-white hover:bg-secondary"
          )}
        >
          <SlidersHorizontal size={12} />
          فیلترها
          {advancedCount > 0 && (
            <span className="w-4 h-4 rounded-full bg-primary text-white text-xs flex items-center justify-center">{advancedCount}</span>
          )}
        </button>
        <button
          onClick={() => {
            setFilters((prev: any) => ({
              ...prev,
              consultant: "",
              property: "",
              dealType: "",
              rentMin: "",
              rentMax: "",
              depositMin: "",
              depositMax: "",
              saleMin: "",
              saleMax: "",
            }));
            setCurrentPage(1);
            setSelected(new Set());
          }}
          disabled={!hasAdvancedFilters}
          className={cx(
            "text-xs whitespace-nowrap transition-colors",
            hasAdvancedFilters ? "text-destructive hover:underline" : "text-muted-foreground/50 cursor-not-allowed"
          )}
        >
          پاک کردن فیلتر
        </button>
        <div className="ml-auto flex items-center border border-border rounded-xl overflow-hidden bg-white">
          <button
            onClick={() => setView("table")}
            className={cx("px-2.5 py-1.5 transition-colors", view === "table" ? "bg-primary text-white" : "hover:bg-secondary text-muted-foreground")}
            title="نمای جدولی"
          >
            <List size={14} />
          </button>
          <button
            onClick={() => setView("card")}
            className={cx("px-2.5 py-1.5 transition-colors", view === "card" ? "bg-primary text-white" : "hover:bg-secondary text-muted-foreground")}
            title="نمای کارتی"
          >
            <LayoutGrid size={14} />
          </button>
        </div>
      </div>

      {showFilters && (
        <Card className="p-4 mb-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 items-end">
            {isAdmin && <ConsultantCombobox value={filters.consultant} onChange={(v) => setFilter("consultant", v)} consultants={consultants} />}
            <PropertyCombobox value={filters.property} onChange={(v) => setFilter("property", v)} properties={properties} />
            <DealTypeCombobox
              value={filters.dealType}
              onChange={(v) => setFilter("dealType", v)}
              dealTypes={(catalog?.dealTypes || []).map((d: any) => ({ id: d.id, displayName: d.displayName, name: d.name }))}
            />
            <PriceRangeFilter
              label="قیمت اجاره"
              placeholder="قیمت اجاره"
              value={{ min: filters.rentMin, max: filters.rentMax }}
              onChange={(v) => {
                setFilters((prev: any) => ({ ...prev, rentMin: v.min, rentMax: v.max }));
                setCurrentPage(1);
              }}
            />
            <PriceRangeFilter
              label="قیمت ودیعه"
              placeholder="قیمت ودیعه"
              value={{ min: filters.depositMin, max: filters.depositMax }}
              onChange={(v) => {
                setFilters((prev: any) => ({ ...prev, depositMin: v.min, depositMax: v.max }));
                setCurrentPage(1);
              }}
            />
            <PriceRangeFilter
              label="قیمت فروش/رهن"
              placeholder="قیمت فروش/رهن"
              value={{ min: filters.saleMin, max: filters.saleMax }}
              onChange={(v) => {
                setFilters((prev: any) => ({ ...prev, saleMin: v.min, saleMax: v.max }));
                setCurrentPage(1);
              }}
            />
          </div>
        </Card>
      )}

      {selected.size > 0 && (
        <div className="mb-3">
          <BulkActionBar
            count={selected.size}
            onArchive={() => {
              selected.forEach((id) => runAction("archive", id));
              setSelected(new Set());
            }}
            onDelete={() => {
              selected.forEach((id) => runAction("delete", id));
              setSelected(new Set());
            }}
            onClear={() => setSelected(new Set())}
          />
        </div>
      )}

      {isLoading ? (
        <div className="text-center py-12 text-sm text-muted-foreground">در حال بارگذاری آگهی‌ها…</div>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
            <KpiCard
              label="آگهی‌های فعال"
              value={activeCount.toLocaleString("fa-IR")}
              icon={<FileText size={16} />}
              color="bg-primary/10 text-primary"
            />
            <KpiCard
              label="کل بازدیدها"
              value={formattedTotalViews}
              sub={`${totalViews.toLocaleString("fa-IR")} بازدید ثبت‌شده`}
              icon={<Eye size={16} />}
              color="bg-blue-50 text-blue-600"
            />
            <KpiCard
              label="میانگین امتیاز کیفیت"
              value={`${avgQualityScore.toLocaleString("fa-IR")}/۱۰۰`}
              sub="سنجش هوشمند محتوا و تصاویر"
              icon={<Award size={16} />}
              color="bg-purple-50 text-purple-600"
            />
            <KpiCard
              label="کل آگهی‌ها"
              value={totalCount.toLocaleString("fa-IR")}
              icon={<Layers size={16} />}
              color="bg-emerald-50 text-emerald-600"
            />
          </div>

          {/* Card view */}
          {view === "card" && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {paginated.length === 0 ? (
                  <div className="col-span-full py-16 text-center flex flex-col items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-secondary flex items-center justify-center">
                      <FileText size={20} className="text-muted-foreground" />
                    </div>
                    <p className="text-sm font-medium">آگهی‌ای یافت نشد</p>
                    <Btn variant="primary" size="sm" onClick={() => navigate("create-listing")}>
                      <Plus size={13} />
                      اولین آگهی را بسازید
                    </Btn>
                  </div>
                ) : (
                  paginated.map((l) => {
                    const consultantName = l.assigned_to_detail?.name || "نامشخص";
                    return (
                      <Card key={l.id} hover onClick={() => navigate("listing-detail", l.id)} className="overflow-hidden">
                        <div
                          className="h-28 relative flex items-end p-4 bg-gradient-to-br from-slate-400 to-slate-600"
                          style={
                            l.property_detail?.image_url
                              ? { backgroundImage: `url(${l.property_detail.image_url})`, backgroundSize: "cover", backgroundPosition: "center" }
                              : undefined
                          }
                        >
                          <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/30 to-transparent" />
                          <div className="absolute top-3 left-3 z-10 flex items-center gap-1.5 flex-wrap">
                            {statusBadge(l.status)}
                            <Badge label={(l as any).dealTypeDisplay || toPersianDeal((l as any).dealTypeName) || "—"} variant="muted" />
                          </div>
                          <div className="absolute top-3 right-3 z-10" onClick={(e) => e.stopPropagation()}>
                            <ActionMenu actions={rowActions(l)} />
                          </div>
                        </div>
                        <div className="p-4">
                          <h3 className="text-sm font-semibold mb-1 truncate">{l.title}</h3>
                          <p className="text-xs text-muted-foreground mb-2">
                            کد: {l.id} | ملک: {l.property_detail?.title || "—"}
                          </p>
                          <div className="flex flex-wrap gap-1 mb-3">
                            {l.channels.map((c) => (
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
                              imageUrl={consultants.find((c) => String(c.user?.id || c.id) === String(l.assigned_to))?.profile_image}
                              initials={consultantName
                                .split(" ")
                                .map((w) => w[0])
                                .join("")}
                              size="xs"
                            />
                            <span className="text-xs text-muted-foreground truncate flex-1">{consultantName}</span>
                            {l.status === "DRAFT" && isAdmin && (
                              <Btn
                                variant="primary"
                                size="xs"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  runAction("approve", l.id);
                                }}
                              >
                                <Check size={11} />
                                تایید
                              </Btn>
                            )}
                          </div>
                        </div>
                      </Card>
                    );
                  })
                )}
              </div>
              {paginated.length > 0 && (
                <div className="mt-4 px-1">
                  <Pagination
                    page={currentPage}
                    total={totalCount}
                    pageSize={pageSize}
                    onPageChange={setCurrentPage}
                    onPageSizeChange={(s) => {
                      setPageSize(s);
                      setCurrentPage(1);
                    }}
                  />
                </div>
              )}
            </>
          )}

          {/* Table view */}
          {view === "table" && (
            <Card className="overflow-hidden">
              <div className="overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="border-b border-border bg-secondary/50 sticky top-0 z-10">
                    <tr>
                      <th className="px-4 py-3 w-10">
                        <input
                          type="checkbox"
                          checked={paginated.length > 0 && paginated.every((l) => selected.has(String(l.id)))}
                          onChange={toggleAll}
                          className="rounded"
                        />
                      </th>
                      {[
                        ["status", "وضعیت"],
                        ["title", "عنوان"],
                        ["dealType", "نوع معامله"],
                        ["channels", "کانال‌ها"],
                        ["created_at", "تاریخ ایجاد"],
                        ["consultant", "مشاور"],
                      ].map(([col, label]) => (
                        <th
                          key={col}
                          className="text-right px-4 py-3 text-xs font-semibold text-muted-foreground whitespace-nowrap cursor-pointer hover:text-foreground select-none"
                          onClick={() => toggleSort(col)}
                        >
                          {label}
                          <SortIcon col={col} />
                        </th>
                      ))}
                      <th className="px-4 py-3 text-xs font-semibold text-muted-foreground">عملیات</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {paginated.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="px-4 py-16 text-center">
                          <div className="flex flex-col items-center gap-3">
                            <div className="w-12 h-12 rounded-xl bg-secondary flex items-center justify-center">
                              <FileText size={20} className="text-muted-foreground" />
                            </div>
                            <p className="text-sm font-medium">آگهی‌ای یافت نشد</p>
                            <Btn variant="primary" size="sm" onClick={() => navigate("create-listing")}>
                              <Plus size={13} />
                              اولین آگهی را بسازید
                            </Btn>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      paginated.map((l) => {
                        const consultantName = l.assigned_to_detail?.name || "—";
                        return (
                          <tr key={l.id} className={cx("hover:bg-secondary/30 transition-colors", selected.has(String(l.id)) && "bg-primary/5")}>
                            <td className="px-4 py-3">
                              <input type="checkbox" checked={selected.has(String(l.id))} onChange={() => toggleSelect(String(l.id))} className="rounded" />
                            </td>
                            <td className="px-4 py-3">{statusBadge(l.status)}</td>
                            <td className="px-4 py-3">
                              <p className="text-xs font-semibold max-w-44 truncate">{l.title}</p>
                              <p className="text-xs text-muted-foreground">ملک: {l.property_detail?.title || "—"}</p>
                            </td>
                            <td className="px-4 py-3">
                              <Badge label={(l as any).dealTypeDisplay || toPersianDeal((l as any).dealTypeName) || "—"} variant="muted" />
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex flex-wrap gap-1">
                                {l.channels.map((c) => (
                                  <Badge key={c} label={toPersianChannel(c)} variant="muted" />
                                ))}
                              </div>
                            </td>
                            <td className="px-4 py-3 text-xs text-muted-foreground font-mono">{new Date(l.created_at).toLocaleDateString("fa-IR")}</td>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2">
                                <ProfileAvatar
                                  imageUrl={consultants.find((c) => String(c.user?.id || c.id) === String(l.assigned_to))?.profile_image}
                                  initials={consultantName
                                    .split(" ")
                                    .map((w) => w[0])
                                    .join("")}
                                  size="xs"
                                />
                                <span className="text-xs">{consultantName}</span>
                              </div>
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-0.5">
                                {l.status === "DRAFT" && isAdmin && (
                                  <Btn variant="primary" size="xs" onClick={() => runAction("approve", l.id)}>
                                    <Check size={11} />
                                    تایید
                                  </Btn>
                                )}
                                <ActionMenu actions={rowActions(l)} />
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
              <div className="px-4 py-3 border-t border-border bg-white">
                <Pagination
                  page={currentPage}
                  total={totalCount}
                  pageSize={pageSize}
                  onPageChange={setCurrentPage}
                  onPageSizeChange={(s) => {
                    setPageSize(s);
                    setCurrentPage(1);
                  }}
                />
              </div>
            </Card>
          )}
        </>
      )}

      <ConfirmModal
        open={!!confirmDelete}
        title="حذف آگهی؟"
        danger
        message="این آگهی برای همیشه حذف خواهد شد."
        onConfirm={() => {
          if (confirmDelete) runAction("delete", confirmDelete);
          setConfirmDelete(null);
        }}
        onCancel={() => setConfirmDelete(null)}
      />
      {statusModal && (
        <StatusChangeModal
          listing={statusModal}
          onClose={() => setStatusModal(null)}
          onApply={(newSt) => {
            if (newSt === "ACTIVE") runAction("approve", statusModal.id);
            else if (newSt === "DRAFT") runAction("reject", statusModal.id);
            else if (newSt === "PAUSED") runAction("pause", statusModal.id);
            else if (newSt === "ARCHIVED") runAction("archive", statusModal.id);
            else if (newSt === "SOLD") runAction("sold", statusModal.id);
          }}
        />
      )}
    </div>
  );
}

export { ListingsPage };
