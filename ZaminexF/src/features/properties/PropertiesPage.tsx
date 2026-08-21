import React, { useState, useEffect, useCallback, useMemo } from "react";
import { cx } from "../../shared/lib/utils";
import { Page, Role, Property, PropertiesPageProps } from "../../shared/lib/types";
import { toPersianType, toPersianDeal, toPersianPropertyStatus } from "../../shared/lib/utils";
import { Badge } from "../../shared/components/ui/Badge";
import { Btn } from "../../shared/components/ui/Btn";
import { Card } from "../../shared/components/ui/Card";
import { SelectField } from "../../shared/components/ui/SelectField";
import { ProfileAvatar } from "../../shared/components/ui/ProfileAvatar";
import { EmptyState } from "../../shared/components/ui/EmptyState";
import { PageHeader } from "../../shared/components/ui/PageHeader";
import { ConfirmModal } from "../../shared/components/ConfirmModal";
import { ActionMenu } from "../../shared/components/ActionMenu";
import { Pagination } from "../../shared/components/Pagination";
import { BulkActionBar } from "../../shared/components/BulkActionBar";
import { ConsultantCombobox } from "../../shared/components/ui/ConsultantCombobox";
import { DistrictCombobox } from "../../shared/components/ui/DistrictCombobox";
import { CityCombobox } from "../../shared/components/ui/CityCombobox";
import { useLocationTree } from "../../shared/components/ui/LocationSelect";
import { apiFetch } from "../../shared/lib/apiClient";
import { consultantLabel } from "../../shared/lib/utils";
import { Building2, Eye, Edit2, Trash2, Archive, MapPin, Search, SlidersHorizontal, LayoutGrid, List, Plus, User, Users } from "lucide-react";
import { TRANSACTION_TYPES, PROPERTY_STATUSES } from "../../shared/lib/constants";
import { DynamicSearchFilters, useSearchSchema, buildAttributeParams } from "../../shared/components/ui/DynamicSearchFilters";
import { useBasicsCatalog } from "../../shared/lib/useAttributeSchema";
import { statusBadge } from "../../shared/components/ui/StatusBadge";

function PropertiesPage({
  navigate,
  role,
  properties: initialProperties,
  loading: initialLoading,
  openPropertyDetail,
  openPropertyEdit,
  onArchive,
  onDelete,
  onToggleShared,
  consultants,
  districtsList = [],
  csrfToken,
}: PropertiesPageProps) {
  const [view, setView] = useState<"card" | "table">("card");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState({
    consultant: "",
    type: "",
    city: "",
    district: "",
    propertyStatus: "",
  });

  const { catalog } = useBasicsCatalog(csrfToken);
  const [propertyTypeRef, setPropertyTypeRef] = useState("");
  const { tree: locationTree } = useLocationTree(csrfToken);

  const allCities = (locationTree || []).flatMap((prov: any) => prov.cities || []);
  const filteredDistricts = (() => {
    if (!filters.city) {
      const fromTree = allCities.flatMap((c: any) => (c.districts || []).map((d: any) => d.displayName));
      if (fromTree.length > 0) return Array.from(new Set(fromTree));
      return districtsList || [];
    }
    const city = allCities.find((c: any) => c.displayName === filters.city);
    if (!city) return [];
    return (city.districts || []).map((d: any) => d.displayName);
  })();

  const dynamicFilterDefs = useSearchSchema(propertyTypeRef, csrfToken);
  const [attrValues, setAttrValues] = useState<Record<string, string>>({});

  const setAttrValue = (key: string, value: string) => {
    setAttrValues((p) => ({ ...p, [key]: value }));
    setCurrentPage(1);
  };

  useEffect(() => {
    setAttrValues({});
  }, [propertyTypeRef]);

  const [showFilters, setShowFilters] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmArchive, setConfirmArchive] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  // Server-side pagination state
  const [serverProperties, setServerProperties] = useState<Property[]>([]);
  const [totalCount, setTotalCount] = useState(0);
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

  const toggleSelect = (id: string) =>
    setSelected((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });

  // Server fetch with pagination and filters
  const fetchServerProperties = useCallback(async () => {
    setServerLoading(true);
    try {
      const params = new URLSearchParams();
      params.append("page", String(currentPage));
      params.append("page_size", String(pageSize));
      if (search.trim()) params.append("q", search.trim());
      if (filters.consultant) params.append("consultantId", filters.consultant);
      if (filters.city) params.append("city", filters.city);
      if (filters.district) params.append("district", filters.district);
      if (filters.propertyStatus) params.append("propertyStatus", filters.propertyStatus);
      if (propertyTypeRef) params.append("propertyTypeRef", propertyTypeRef);
      // dynamic attribute filters
      const attrQuery = buildAttributeParams(attrValues);
      if (attrQuery) {
        // attrQuery is like "attr_foo=bar&attr_baz_min=10"
        attrQuery.split("&").forEach((pair) => {
          const [k, v] = pair.split("=");
          if (k && v) params.append(k, decodeURIComponent(v));
        });
      }

      const url = `/properties/api/properties/?${params.toString()}`;
      const res = await apiFetch(url, { method: "GET" }, csrfToken);
      if (!res.ok) throw new Error("خطا در دریافت املاک");
      const data = await res.json();
      if (Array.isArray(data)) {
        // Fallback if pagination not enabled
        setServerProperties(data);
        setTotalCount(data.length);
      } else {
        const results = data.results ?? [];
        const count = data.count ?? results.length;
        setServerProperties(results);
        setTotalCount(count);
      }
    } catch (err) {
      console.error("Error fetching properties:", err);
      // Fallback to initial props on error
      setServerProperties([]);
      setTotalCount(0);
    } finally {
      setServerLoading(false);
    }
  }, [currentPage, pageSize, search, filters, propertyTypeRef, attrValues, csrfToken]);

  // Fetch on mount and when dependencies change
  useEffect(() => {
    fetchServerProperties();
  }, [fetchServerProperties]);

  // When filters change, page already reset to 1 via setFilter
  // Sorting is client-side on current page only for minimal change
  const sorted = useMemo(() => {
    const arr = [...serverProperties];
    if (!sortCol) return arr;
    return arr.sort((a, b) => {
      const av = (a as any)[sortCol];
      const bv = (b as any)[sortCol];
      const an = av == null || av === "" ? null : Number(av);
      const bn = bv == null || bv === "" ? null : Number(bv);
      if (an != null && bn != null && !Number.isNaN(an) && !Number.isNaN(bn)) {
        return sortDir === "asc" ? an - bn : bn - an;
      }
      return sortDir === "asc" ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
  }, [serverProperties, sortCol, sortDir]);

  const paginated = sorted; // Already paginated from server

  const toggleAll = () =>
    setSelected((s) => (s.size === paginated.length ? new Set() : new Set(paginated.map((p) => String(p.id)))));

  const activeFilterCount = Object.values(filters).filter(Boolean).length + (propertyTypeRef ? 1 : 0) + Object.values(attrValues).filter(Boolean).length;

  const rowActions = (p: Property) => [
    {
      label: "مشاهده جزئیات",
      icon: <Eye size={12} />,
      onClick: () => openPropertyDetail(String(p.id)),
    },
    {
      label: "ویرایش ملک",
      icon: <Edit2 size={12} />,
      onClick: () => openPropertyEdit(String(p.id)),
    },
    ...(role === "admin" && onToggleShared
      ? [
          {
            label: (p as any).isShared
              ? `قابل مشاهده فقط برای ${p.consultantName || "مشاور مربوطه"}`
              : "نمایش ملک برای همه مشاوران",
            icon: (p as any).isShared ? <User size={12} /> : <Users size={12} />,
            onClick: () => onToggleShared(String(p.id)),
          },
        ]
      : []),
    { label: "بایگانی", icon: <Archive size={12} />, onClick: () => setConfirmArchive(String(p.id)) },
    { label: "حذف", icon: <Trash2 size={12} />, onClick: () => setConfirmDelete(String(p.id)), danger: true },
  ];

  const isLoading = initialLoading || serverLoading;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <PageHeader
        title="مرکز املاک"
        subtitle={`${totalCount.toLocaleString("fa-IR")} ملک یافت شد`}
        actions={
          <Btn variant="primary" size="sm" onClick={() => navigate("add-property")}>
            <Plus size={13} />
            افزودن ملک
          </Btn>
        }
      />
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <div className="relative flex-1 min-w-48 max-w-72">
          <Search size={13} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setCurrentPage(1);
            }}
            placeholder="جستجوی عنوان، کد یا محله…"
            className="w-full pl-10 pr-3 py-2 text-sm rounded-xl border border-border bg-white outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={cx(
            "flex items-center gap-1.5 px-3 py-2 rounded-xl border text-xs font-medium transition-colors",
            showFilters || activeFilterCount > 0 ? "border-primary bg-primary/5 text-primary" : "border-border bg-white hover:bg-secondary"
          )}
        >
          <SlidersHorizontal size={12} />
          فیلترها
          {activeFilterCount > 0 && (
            <span className="w-4 h-4 rounded-full bg-primary text-white text-xs flex items-center justify-center">{activeFilterCount}</span>
          )}
        </button>
        {activeFilterCount > 0 && (
          <button
            onClick={() => {
              setFilters({ consultant: "", type: "", city: "", district: "", propertyStatus: "" });
              setPropertyTypeRef("");
              setAttrValues({});
              setCurrentPage(1);
            }}
            className="text-xs text-destructive hover:underline"
          >
            پاک کردن فیلترها
          </button>
        )}
        <div className="ml-auto flex items-center border border-border rounded-xl overflow-hidden bg-white">
          <button
            onClick={() => setView("card")}
            className={cx("px-2.5 py-1.5 transition-colors", view === "card" ? "bg-primary text-white" : "hover:bg-secondary text-muted-foreground")}
          >
            <LayoutGrid size={14} />
          </button>
          <button
            onClick={() => setView("table")}
            className={cx("px-2.5 py-1.5 transition-colors", view === "table" ? "bg-primary text-white" : "hover:bg-secondary text-muted-foreground")}
          >
            <List size={14} />
          </button>
        </div>
      </div>

      {showFilters && (
        <Card className="p-4 mb-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 items-end">
            {role === "admin" && <ConsultantCombobox value={filters.consultant} onChange={(v) => setFilter("consultant", v)} consultants={consultants} />}
            <SelectField
              placeholder="همه انواع"
              value={propertyTypeRef}
              onChange={(v) => {
                setPropertyTypeRef(v);
                setCurrentPage(1);
              }}
              options={(catalog?.propertyTypes ?? []).map((t) => ({ label: t.displayName, value: String(t.id) }))}
            />
            <CityCombobox
              value={filters.city}
              onChange={(v) => {
                const selectedCity = allCities.find((c) => c.displayName === v);
                const cityDistricts = selectedCity ? selectedCity.districts.map((d: any) => d.displayName) : [];
                if (filters.district && v && !cityDistricts.includes(filters.district)) {
                  setFilters((prev) => ({ ...prev, city: v, district: "" }));
                  setCurrentPage(1);
                  setSelected(new Set());
                } else {
                  setFilter("city", v);
                }
              }}
              citiesList={allCities.map((c) => c.displayName)}
            />
            <DistrictCombobox value={filters.district} onChange={(v) => setFilter("district", v)} districtsList={filteredDistricts} />
            <SelectField
              placeholder="همه وضعیت‌ها"
              value={filters.propertyStatus}
              onChange={(v) => setFilter("propertyStatus", v)}
              options={PROPERTY_STATUSES.map((s) => ({ label: toPersianPropertyStatus(s), value: s }))}
            />

            <DynamicSearchFilters filters={dynamicFilterDefs} values={attrValues} onChange={setAttrValue} />
          </div>
          {propertyTypeRef && dynamicFilterDefs.length === 0 && (
            <p className="text-xs text-muted-foreground mt-3">برای این نوع ملک فیلتر اختصاصی تعریف نشده است.</p>
          )}
        </Card>
      )}

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-12 bg-muted rounded-xl animate-pulse" />
          ))}
        </div>
      ) : view === "card" ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {paginated.length === 0 ? (
              <EmptyState
                icon={<Building2 size={28} />}
                title="ملکی یافت نشد"
                description="با فیلترهای فعلی هیچ ملکی پیدا نشد. فیلترها را تغییر دهید یا ملک جدیدی اضافه کنید."
              />
            ) : (
              paginated.map((p) => (
                <Card key={p.id} hover onClick={() => openPropertyDetail(String(p.id))} className="overflow-hidden">
                  <div
                    className={cx("h-36 relative flex items-end p-4", !p.images?.length && (p.gradient || "from-emerald-500 to-teal-600"))}
                    style={p.images?.length ? { backgroundImage: `url(${p.images[0].url})`, backgroundSize: "cover", backgroundPosition: "center" } : undefined}
                  >
                    <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/30 to-transparent" />
                    <div className="absolute top-3 left-3 flex gap-1.5 flex-wrap z-10">
                      {statusBadge(p.propertyStatus || "available")}
                      {(p as any).isShared && <Badge label="همه مشاوران" variant="info" />}
                    </div>
                    <div className="absolute top-3 right-3 z-10" onClick={(e) => e.stopPropagation()}>
                      <ActionMenu actions={rowActions(p)} />
                    </div>
                    <div className="relative z-10">
                      <div className="text-white/90 text-xs flex items-center gap-1">
                        <MapPin size={10} />
                        {p.locationPath || [p.provinceName, p.cityName, p.district].filter(Boolean).join(" / ") || p.district || "—"}
                      </div>
                    </div>
                  </div>
                  <div className="p-4">
                    <p className="text-xs text-muted-foreground font-mono mb-0.5">{p.internalCode}</p>
                    <h3 className="text-sm font-semibold mb-2 line-clamp-1">{p.title}</h3>
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <div className="flex items-center gap-3">
                        {(p.beds ?? 0) > 0 && <span>{p.beds} خواب</span>}
                        <span>{p.area ? p.area.toLocaleString("fa-IR") : 0} متر</span>
                        <span>طبقه {p.floor}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border">
                      <ProfileAvatar
                        imageUrl={consultants.find((c) => String(c.user?.id || c.id) === String(p.consultantId ?? p.consultant ?? ""))?.profile_image}
                        initials={consultantLabel(p).split(" ").map((w: string) => w[0]).join("") || "U"}
                        size="xs"
                      />
                      <span className="text-xs text-muted-foreground truncate flex-1">{consultantLabel(p)}</span>
                    </div>
                  </div>
                </Card>
              ))
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
      ) : (
        <div className="flex flex-col">
          {selected.size > 0 && (
            <div className="mb-3">
              <BulkActionBar
                count={selected.size}
                onArchive={() => {
                  selected.forEach((id) => onArchive(id));
                  setSelected(new Set());
                }}
                onDelete={() => {
                  selected.forEach((id) => onDelete(id));
                  setSelected(new Set());
                }}
                onClear={() => setSelected(new Set())}
              />
            </div>
          )}
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border bg-secondary/50 sticky top-0 z-10">
                  <tr>
                    <th className="px-4 py-3 w-10">
                      <input
                        type="checkbox"
                        checked={paginated.length > 0 && paginated.every((p) => selected.has(String(p.id)))}
                        onChange={toggleAll}
                        className="rounded"
                      />
                    </th>
                    {[
                      ["internalCode", "کد"],
                      ["title", "ملک"],
                      ["type", "نوع"],
                      ["district", "محله"],
                      ["floor", "طبقه"],
                      ["constructionYear", "سال ساخت"],
                      ["propertyStatus", "وضعیت"],
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
                    <th className="text-right px-4 py-3 text-xs font-semibold text-muted-foreground">عملیات</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {paginated.length === 0 ? (
                    <tr>
                      <td colSpan={11} className="px-4 py-12 text-center text-sm text-muted-foreground">
                        ملکی با فیلترهای فعلی پیدا نشد.
                      </td>
                    </tr>
                  ) : (
                    paginated.map((p) => (
                      <tr key={p.id} className={cx("hover:bg-secondary/30 transition-colors", selected.has(String(p.id)) && "bg-primary/5")}>
                        <td className="px-4 py-3">
                          <input
                            type="checkbox"
                            checked={selected.has(String(p.id))}
                            onChange={() => toggleSelect(String(p.id))}
                            className="rounded"
                            onClick={(e) => e.stopPropagation()}
                          />
                        </td>
                        <td className="px-4 py-3 text-xs font-mono text-muted-foreground">{p.internalCode}</td>
                        <td className="px-4 py-3">
                          <p className="font-medium text-xs max-w-40 truncate">{p.title}</p>
                        </td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">{toPersianType(p.type)}</td>
                        <td className="px-4 py-3 text-xs">
                          <span className="flex items-center gap-1">
                            <MapPin size={10} className="text-muted-foreground" />
                            {p.district}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">{p.floor}</td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">{p.constructionYear}</td>
                        <td className="px-4 py-3">{statusBadge(p.propertyStatus || "available")}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <ProfileAvatar
                              imageUrl={consultants.find((c) => String(c.user?.id || c.id) === String(p.consultantId ?? p.consultant ?? ""))?.profile_image}
                              initials={consultantLabel(p).split(" ").map((w: string) => w[0]).join("") || "U"}
                              size="xs"
                            />
                            <span className="text-xs">{consultantLabel(p).split(" ")[0] || "—"}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-0.5">
                            <button onClick={() => openPropertyDetail(String(p.id))} className="p-1.5 hover:bg-secondary rounded-lg transition-colors" title="مشاهده">
                              <Eye size={13} className="text-muted-foreground" />
                            </button>
                            <button onClick={() => openPropertyEdit(String(p.id))} className="p-1.5 hover:bg-secondary rounded-lg transition-colors" title="ویرایش">
                              <Edit2 size={13} className="text-muted-foreground" />
                            </button>
                            <button onClick={() => setConfirmArchive(String(p.id))} className="p-1.5 hover:bg-amber-50 rounded-lg transition-colors" title="بایگانی">
                              <Archive size={13} className="text-muted-foreground" />
                            </button>
                            <button onClick={() => setConfirmDelete(String(p.id))} className="p-1.5 hover:bg-red-50 rounded-lg transition-colors" title="حذف">
                              <Trash2 size={13} className="text-muted-foreground" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <div className="px-4 py-3 border-t border-border bg-white sticky bottom-0">
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
        </div>
      )}
      <ConfirmModal
        open={!!confirmArchive}
        title="بایگانی ملک؟"
        message="این ملک بایگانی شده و از آگهی‌های فعال مخفی می‌شود. بعداً توسط مدیر قابل بازیابی است."
        onConfirm={() => {
          if (confirmArchive) onArchive(confirmArchive);
          setConfirmArchive(null);
        }}
        onCancel={() => setConfirmArchive(null)}
      />
      <ConfirmModal
        open={!!confirmDelete}
        title="حذف ملک؟"
        danger
        message="این ملک و تمام داده‌های مرتبط با آن برای همیشه حذف خواهند شد. این عملیات غیرقابل بازگشت است."
        onConfirm={() => {
          if (confirmDelete) onDelete(confirmDelete);
          setConfirmDelete(null);
        }}
        onCancel={() => setConfirmDelete(null)}
      />
    </div>
  );
}

export { PropertiesPage };
