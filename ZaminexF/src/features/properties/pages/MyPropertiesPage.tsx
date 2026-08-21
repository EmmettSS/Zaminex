import React, { useState, useEffect, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { Page, Role, Property, ConsultantItem, BadgeV } from "../../../shared/lib/types";
import { toPersianType, toPersianPropertyStatus, consultantLabel } from "../../../shared/lib/utils";
import { fuzzyFilter } from "../../../shared/lib/fuzzySearch";
import { Badge } from "../../../shared/components/ui/Badge";
import { Btn } from "../../../shared/components/ui/Btn";
import { Card } from "../../../shared/components/ui/Card";
import { SelectField } from "../../../shared/components/ui/SelectField";
import { ProfileAvatar } from "../../../shared/components/ui/ProfileAvatar";
import { EmptyState } from "../../../shared/components/ui/EmptyState";
import { PageHeader } from "../../../shared/components/ui/PageHeader";
import { ConfirmModal } from "../../../shared/components/ConfirmModal";
import { Pagination } from "../../../shared/components/Pagination";
import { DistrictCombobox } from "../../../shared/components/ui/DistrictCombobox";
import { CityCombobox } from "../../../shared/components/ui/CityCombobox";
import { ConsultantCombobox } from "../../../shared/components/ui/ConsultantCombobox";
import { useLocationTree } from "../../../shared/components/ui/LocationSelect";
import { useBasicsCatalog } from "../../../shared/lib/useAttributeSchema";
import { apiFetch } from "../../../shared/lib/apiClient";
import { toast } from "../../../shared/lib/utils";
import { PROPERTY_STATUSES } from "../../../shared/lib/constants";
import { statusBadge } from "../../../shared/components/ui/StatusBadge";
import { ActionMenu } from "../../../shared/components/ActionMenu";
import {
  Building2, Plus, MapPin, Eye, Edit2, Archive, Search,
  SlidersHorizontal, LayoutGrid, List, Users,
} from "lucide-react";

function MyPropertiesPage({
  navigate,
  properties,
  consultantId,
  openPropertyDetail,
  openPropertyEdit,
  onArchive,
  csrfToken,
  userName,
}: {
  navigate: (p: Page) => void;
  properties: Property[];
  openPropertyDetail: (id: string) => void;
  openPropertyEdit: (id: string) => void;
  consultantId: string | null;
  onArchive: (id: string) => void;
  csrfToken?: string;
  userName?: string;
}) {
  const [confirmArchive, setConfirmArchive] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState("");
  const [view, setView] = useState<"card" | "table">("card");
  const [showFilters, setShowFilters] = useState(false);
  const [propertyTypeRef, setPropertyTypeRef] = useState("");
  const [filters, setFilters] = useState({
    consultant: "",
    city: "",
    district: "",
    propertyStatus: "",
  });

  const { catalog } = useBasicsCatalog(csrfToken);
  const { tree: locationTree } = useLocationTree(csrfToken);

  const allCities = (locationTree || []).flatMap((prov: any) => prov.cities || []);
  const filteredDistricts = (() => {
    if (!filters.city) {
      const fromTree = allCities.flatMap((c: any) => (c.districts || []).map((d: any) => d.displayName));
      if (fromTree.length > 0) return Array.from(new Set(fromTree));
      return [];
    }
    const city = allCities.find((c: any) => c.displayName === filters.city);
    if (!city) return [];
    return (city.districts || []).map((d: any) => d.displayName);
  })();

  // Include the consultant's own properties AND shared properties
  const mine = useMemo(() => {
    return (properties ?? []).filter((p) => {
      const isOwn = String(p.consultantId ?? p.consultant ?? "") === String(consultantId ?? "");
      const isShared = (p as any).isShared === true;
      return isOwn || isShared;
    });
  }, [properties, consultantId]);

  // Check if there are any shared properties to show the consultant filter
  const hasSharedProperties = mine.some((p) => (p as any).isShared);

  // Build the consultant filter options (formatted for ConsultantCombobox): the
  // current consultant themselves (so they can filter to their own properties)
  // plus every consultant who owns a shared property visible here.
  const sharedConsultants = useMemo<ConsultantItem[]>(() => {
    const seen = new Map<string, ConsultantItem>();
    // Always include the current consultant so they can filter to their own properties.
    if (consultantId) {
      const selfProp = mine.find(
        (p) => String(p.consultantId ?? p.consultant ?? "") === String(consultantId)
      );
      const selfName =
        selfProp?.consultantName || consultantLabel(selfProp || {}) || userName || "من";
      seen.set(String(consultantId), {
        id: String(consultantId),
        full_name: selfName,
        user: {
          id: String(consultantId),
          username: selfName,
          role: "AGENT",
          name: selfName,
          email: "",
          mobile: "",
        },
      } as any);
    }
    mine.forEach((p) => {
      if ((p as any).isShared) {
        const id = String(p.consultantId ?? p.consultant ?? "");
        if (id && !seen.has(id)) {
          const name = p.consultantName || consultantLabel(p) || "نامشخص";
          seen.set(id, {
            id: id,
            full_name: name,
            user: { id, username: name, role: "AGENT", name, email: "", mobile: "" },
          } as any);
        }
      }
    });
    return Array.from(seen.values());
  }, [mine, consultantId, userName]);

  // Apply search and filters
  const filtered = useMemo(() => {
    let result = mine;

    // Search — same fuzzy gateway the comboboxes use (similar + typo-tolerant).
    if (search.trim()) {
      result = fuzzyFilter(
        result,
        search,
        (p) =>
          [
            p.title,
            p.internalCode,
            p.district,
            p.neighborhood,
            (p as any).locationPath,
            p.fullAddress,
            p.consultantName,
            (p as any).cityName,
            (p as any).provinceName,
          ]
            .filter(Boolean)
            .join(" ")
      );
    }

    // Consultant filter. `mine` already contains only the current consultant's
    // own properties plus shared properties, so filtering by consultant id is
    // enough: selecting the current consultant shows their own properties, and
    // selecting another consultant shows that consultant's shared properties.
    if (filters.consultant) {
      result = result.filter(
        (p) => String(p.consultantId ?? p.consultant ?? "") === filters.consultant
      );
    }

    // Property type ref
    if (propertyTypeRef) {
      result = result.filter((p) =>
        String((p as any).propertyTypeRefId ?? (p as any).propertyTypeRef ?? "") === String(propertyTypeRef)
      );
    }

    // City
    if (filters.city) {
      result = result.filter((p) => (p as any).cityName === filters.city);
    }

    // District
    if (filters.district) {
      result = result.filter((p) => (p.district || p.neighborhood || "") === filters.district);
    }

    // Property status
    if (filters.propertyStatus) {
      result = result.filter((p) => (p.propertyStatus || "").toUpperCase() === filters.propertyStatus);
    }

    return result;
  }, [mine, search, filters, propertyTypeRef]);

  const totalCount = filtered.length;
  const paginated = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  useEffect(() => {
    setCurrentPage(1);
  }, [consultantId, search, filters]);

  const setFilter = (k: string, v: string) => {
    setFilters((p) => ({ ...p, [k]: v }));
    setCurrentPage(1);
  };

  const activeFilterCount = Object.values(filters).filter(Boolean).length + (propertyTypeRef ? 1 : 0);

  const rowActions = (p: Property) => [
    { label: "مشاهده جزئیات", icon: <Eye size={12} />, onClick: () => openPropertyDetail(String(p.id)) },
    { label: "ویرایش", icon: <Edit2 size={12} />, onClick: () => openPropertyEdit(String(p.id)) },
    { label: "بایگانی", icon: <Archive size={12} />, onClick: () => setConfirmArchive(String(p.id)) },
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <PageHeader
        title="املاک من"
        subtitle={`${totalCount.toLocaleString("fa-IR")} ملک قابل مشاهده`}
        actions={
          <Btn variant="primary" size="sm" onClick={() => navigate("add-property")}>
            <Plus size={13} />
            افزودن ملک
          </Btn>
        }
      />

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <div className="relative flex-1 min-w-48 max-w-72">
          <Search size={13} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
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
              setFilters({ consultant: "", city: "", district: "", propertyStatus: "" });
              setPropertyTypeRef("");
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
            {hasSharedProperties && (
              <ConsultantCombobox
                value={filters.consultant}
                onChange={(v) => setFilter("consultant", v)}
                consultants={sharedConsultants}
              />
            )}
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
          </div>
        </Card>
      )}

      {mine.length === 0 ? (
        <EmptyState
          icon={<Building2 size={28} />}
          title="ملکی وجود ندارد"
          description="املاک واگذارشده به شما و املاک اشتراکی در اینجا نمایش داده می‌شوند."
          action={
            <Btn variant="primary" size="sm" onClick={() => navigate("add-property")}>
              <Plus size={13} />
              اولین ملک را اضافه کنید
            </Btn>
          }
        />
      ) : view === "card" ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {paginated.length === 0 ? (
              <div className="col-span-full py-12 text-center text-sm text-muted-foreground">
                ملکی با فیلترهای فعلی پیدا نشد.
              </div>
            ) : (
              paginated.map((p) => (
                <Card
                  key={p.id}
                  hover
                  onClick={() => openPropertyDetail(String(p.id))}
                  className="overflow-hidden"
                >
                  <div
                    className={cx("h-32 relative flex items-end p-4", !p.images?.length && (p.gradient || "from-emerald-500 to-teal-600"))}
                    style={p.images?.length ? { backgroundImage: `url(${p.images[0].url})`, backgroundSize: "cover", backgroundPosition: "center" } : undefined}
                  >
                    <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/30 to-transparent" />
                    <div
                      className="absolute top-3 right-3 z-10"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <ActionMenu actions={rowActions(p)} />
                    </div>
                    <div className="absolute top-3 left-3 flex gap-1.5 flex-wrap z-10">
                      {(p as any).isShared && <Badge label="همه مشاوران" variant="info" />}
                    </div>
                    <div className="relative z-10">
                      <div className="text-white/90 text-xs flex items-center gap-1">
                        <MapPin size={10} />
                        {p.locationPath || [p.provinceName, p.cityName, p.district].filter(Boolean).join(" / ") || p.district || "—"}
                      </div>
                    </div>
                  </div>

                  <div className="p-4">
                    <p className="text-xs text-muted-foreground font-mono mb-0.5">
                      {p.internalCode || "—"}
                    </p>
                    <h3 className="text-xs font-semibold mb-2 line-clamp-1">
                      {p.title || "بدون عنوان"}
                    </h3>
                    <div className="flex items-center justify-between gap-2">
                      {statusBadge(p.propertyStatus || "available")}
                      {(p as any).isShared && (
                        <div className="flex items-center gap-1.5">
                          <ProfileAvatar
                            initials={(p.consultantName || "??").split(" ").map((w) => w[0]).join("").slice(0, 2)}
                            size="xs"
                          />
                          <span className="text-[10px] text-muted-foreground truncate max-w-24">{p.consultantName || "مشاور"}</span>
                        </div>
                      )}
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
        <>
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border bg-secondary/50 sticky top-0 z-10">
                  <tr>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-muted-foreground whitespace-nowrap">کد</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-muted-foreground whitespace-nowrap">ملک</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-muted-foreground whitespace-nowrap">نوع</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-muted-foreground whitespace-nowrap">محله</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-muted-foreground whitespace-nowrap">وضعیت</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-muted-foreground whitespace-nowrap">مشاور</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-muted-foreground whitespace-nowrap">عملیات</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {paginated.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-12 text-center text-sm text-muted-foreground">
                        ملکی با فیلترهای فعلی پیدا نشد.
                      </td>
                    </tr>
                  ) : (
                    paginated.map((p) => (
                      <tr key={p.id} className="hover:bg-secondary/30 transition-colors">
                        <td className="px-4 py-3 text-xs font-mono text-muted-foreground">{p.internalCode}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            {(p as any).isShared && <Badge label="اشتراکی" variant="info" />}
                            <p className="font-medium text-xs max-w-40 truncate">{p.title}</p>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">{toPersianType(p.type || "")}</td>
                        <td className="px-4 py-3 text-xs">
                          <span className="flex items-center gap-1">
                            <MapPin size={10} className="text-muted-foreground" />
                            {p.district || p.neighborhood || "—"}
                          </span>
                        </td>
                        <td className="px-4 py-3">{statusBadge(p.propertyStatus || "available")}</td>
                        <td className="px-4 py-3">
                          {(p as any).isShared ? (
                            <div className="flex items-center gap-1.5">
                              <ProfileAvatar
                                initials={(p.consultantName || "??").split(" ").map((w) => w[0]).join("").slice(0, 2)}
                                size="xs"
                              />
                              <span className="text-xs">{p.consultantName || "—"}</span>
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground">خودم</span>
                          )}
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
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            {paginated.length > 0 && (
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
            )}
          </Card>
        </>
      )}

      <ConfirmModal
        open={!!confirmArchive}
        title="بایگانی ملک؟"
        message="این ملک بایگانی خواهد شد. مشاوران فقط املاکی را که خودشان ایجاد کرده‌اند می‌توانند بایگانی کنند."
        onConfirm={() => {
          if (confirmArchive) onArchive(confirmArchive);
          setConfirmArchive(null);
        }}
        onCancel={() => setConfirmArchive(null)}
      />
    </div>
  );
}

export { MyPropertiesPage };
