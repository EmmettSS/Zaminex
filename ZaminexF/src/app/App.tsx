// =============================================================================
//  App Router — complete stateful controller & orchestrator for the Zaminex frontend
//  This preserves 100% of the state management, API integration, side effects,
//  and callback handlers from App-old.tsx while utilizing the clean modular
//  features/ and shared/ components.
// =============================================================================

import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { createPortal } from "react-dom";

// ── Icons ──────────────────────────────────────────────────────────────
import { Layers } from "lucide-react";

// ── Shared layout primitives ───────────────────────────────────────────
import { Sidebar } from "../features/auth/Sidebar";
import { TopBar } from "../features/auth/TopBar";

// ── Page components (extracted from the original App.tsx) ───────────────
import { LoginPage } from "../features/auth/LoginPage";
import { AdminDashboard } from "../features/dashboard/AdminDashboard";
import { ConsultantDashboard } from "../features/dashboard/pages/ConsultantDashboard";
import { PropertiesPage } from "../features/properties/PropertiesPage";
import { PropertyDetail } from "../features/properties/pages/PropertyDetail";
import { PropertyReportsPage } from "../features/properties/pages/PropertyReportsPage";
import { AddPropertyWizard } from "../features/properties/components/AddPropertyWizard";
import { EditPropertyWizard } from "../features/properties/components/EditPropertyWizard";
import { ListingsPage } from "../features/listings/pages/ListingsPage";
import { ListingDetailPage } from "../features/listings/pages/ListingDetailPage";
import { CreateListingWizard } from "../features/listings/components/CreateListingWizard";
import { StatusChangeModal } from "../features/listings/components/StatusChangeModal";
import { TasksKanban } from "../features/tasks/pages/TasksKanban";
import { TasksCalendar } from "../features/tasks/pages/TasksCalendar";
import { ConsultantsPage } from "../features/consultants/pages/ConsultantsPage";
import { ConsultantAnalyticsSection } from "../features/consultants/components/ConsultantAnalyticsSection";
import { AddConsultantPage } from "../features/consultants/components/AddConsultantPage";
import { EditConsultantPage } from "../features/consultants/components/EditConsultantPage";
import { FollowUpsPage } from "../features/followups/pages/FollowUpsPage";
import { CreateFollowUp } from "../features/followups/components/CreateFollowUp";
import { MyProfilePage } from "../features/profile/pages/MyProfilePage";
import { MyPropertiesPage } from "../features/properties/pages/MyPropertiesPage";
import { MyTasksPage } from "../features/tasks/pages/MyTasksPage";
import { DistrictsPage } from "../features/districts/pages/DistrictsPage";
import { AttributesPage } from "../features/attributes/pages/AttributesPage";
import { ActivityLogPage } from "../features/activity/pages/ActivityLogPage";
import { SettingsPage } from "../features/settings/pages/SettingsPage";

// ── Shared components ──────────────────────────────────────────────────
import { ToastContainer } from "../shared/components/ui/ToastContainer";
import { ConfirmModal } from "../shared/components/ConfirmModal";
import { CommandPalette } from "../shared/components/CommandPalette";
import { NotifDrawer } from "../shared/components/NotifDrawer";
import { EmptyState } from "../shared/components/ui/EmptyState";

// ── Shared types & helpers ─────────────────────────────────────────────
import type { Page, Role, Property, PropertyReportPayload, BadgeV, TaskHistoryEntry, ConsultantItem, FollowUp, FollowUpCreatePayload, Listing } from "../shared/lib/types";
import { PAGE_SIZE, TRANSACTION_TYPES, PROPERTY_STATUSES, PROPERTY_STATUS_TO_BACKEND, LISTING_STATUSES, TASK_TYPES, TASK_STATUSES, TASK_PRIORITIES, DASH_AREA, CHANNEL_PIE, PIE_COLORS, SKILL_RADAR, CHART_COLORS, DELEGATION_COLORS } from "../shared/lib/constants";
import { fmtShort, cx, requiredFieldMsg, propertyStatusToUI, toPersianType, toPersianDeal, toPersianPropertyStatus, toPersianListingStatus, toPersianTaskType, toPersianTaskStatus, toPersianPriority, toPersianFollowupType, toPersianChannel, formatPriceDeviation, delegationLabel, toast, isFollowUpOverdue } from "../shared/lib/utils";
import { apiFetch, readJson, apiErrorMessage, onSessionExpired, beginIntentionalLogout, SESSION_EXPIRED_MESSAGE } from "../shared/lib/apiClient";

export type { Page, Role, Property, PropertyReportPayload, BadgeV };

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

export default function AppRouter({ initialData }: { initialData: InitialData }) {

  // ── Page routing state ───────────────────────────────────────────────
  const [page, setPage] = useState<Page>(() => {
    if (initialData.initialPage && initialData.initialPage !== "login") {
      if (initialData.initialPage === "dashboard") {
        return initialData.role === "admin" ? "admin-dashboard" : "consultant-dashboard";
      }
      return initialData.initialPage as Page;
    }
    if (initialData.isAuthenticated) {
      return initialData.role === "admin" ? "admin-dashboard" : "consultant-dashboard";
    }
    return "login";
  });

  // ── Identity / session state ─────────────────────────────────────────
  const [currentConsultantId, setCurrentConsultantId] = useState<string | null>(
    initialData.currentConsultantId || null);

  const [role, setRole] = useState<"admin" | "consultant">(
    initialData.role ?? "consultant"
  );
  const [userName, setUserName] = useState(initialData.userName || "کاربر");

  // ── Consultant form state ────────────────────────────────────────────
  const [consultantFormSubmitting, setConsultantFormSubmitting] = useState(false);
  const [consultantFormError, setConsultantFormError] = useState<string | null>(null);
  const [selectedConsultantId, setSelectedConsultantId] = useState<string | null>(null);

  // ── Properties state ─────────────────────────────────────────────────
  const [properties, setProperties] = useState<Property[]>(
    initialData.pageProps?.properties || initialData.pageProps?.items || []);
  const [propertiesLoading, setPropertiesLoading] = useState(false);
  const [propertiesError, setPropertiesError] = useState<string | null>(null);
  const [selectedPropertyId, setSelectedPropertyId] = useState<string | null>(null);
  const [selectedProperty, setSelectedProperty] = useState<Property | undefined>(
    initialData.pageProps?.property
  );
  const [selectedPropertyIdForReport, setSelectedPropertyIdForReport] = useState<string | null>(null);
  const [propertyFormSubmitting, setPropertyFormSubmitting] = useState(false);
  const [propertyFormError, setPropertyFormError] = useState<string | null>(null);
  const [editingPropertyId, setEditingPropertyId] = useState<string | null>(null);

  // ── Listings state ───────────────────────────────────────────────────
  const [listings, setListings] = useState<Listing[]>([]);
  const [listingsLoading, setListingsLoading] = useState(false);
  const [listingsError, setListingsError] = useState<string | null>(null);
  const [selectedListingId, setSelectedListingId] = useState<string | null>(null);
  const [selectedListing, setSelectedListing] = useState<Listing | undefined>(undefined);
  const [listingFormSubmitting, setListingFormSubmitting] = useState(false);
  const [listingFormError, setListingFormError] = useState<string | null>(null);

  // ── Consultants state ────────────────────────────────────────────────
  const [consultants, setConsultants] = useState<ConsultantItem[]>(
    initialData.pageProps?.consultants || []);

  const [consultantsLoading, setConsultantsLoading] = useState(false);
  const [consultantsError, setConsultantsError] = useState<string | null>(null);

  // ── Admin "My Profile" state (avatar + display name in the shell) ────
  const [adminProfile, setAdminProfile] = useState<any | null>(null);

  // ── Follow-ups state ─────────────────────────────────────────────────
  const [followups, setFollowups] = useState<FollowUp[]>([]);
  const [followupsLoading, setFollowupsLoading] = useState(false);
  const [followupsError, setFollowupsError] = useState<string | null>(null);
  const [selectedFollowupId, setSelectedFollowupId] = useState<string | null>(null);
  const [selectedFollowup, setSelectedFollowup] = useState<FollowUp | undefined>(undefined);

  // ── Tasks state ──────────────────────────────────────────────────────
  const [tasks, setTasks] = useState<any[]>([]);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [tasksError, setTasksError] = useState<string | null>(null);
  const [taskSummary, setTaskSummary] = useState<{ total: number; pending: number; in_progress: number; completed: number; cancelled: number; overdue: number } | null>(null);
  const [taskTypesList, setTaskTypesList] = useState<Array<{ value: string; label: string }>>([]);

  // ── Dashboard summary state ──────────────────────────────────────────
  const [dashboardKpis, setDashboardKpis] = useState({
    totalProperties: 0,
    activeListings: 0,
    openTasks: 0,
    followUpsDue: 0,
    consultants: 0,
    consultantsActive: 0,
  });
  const [topConsultants, setTopConsultants] = useState<any[]>([]);
  const [revenueMonthly, setRevenueMonthly] = useState<any[]>([]);
  const [revenueDealTypes, setRevenueDealTypes] = useState<Array<{ name: string; label: string }>>([]);
  const [propertyComposition, setPropertyComposition] = useState<any[]>([]);
  const [hotProperties, setHotProperties] = useState<any[]>([]);
  const [myReport, setMyReport] = useState<any | null>(null);
  const [districtsList, setDistrictsList] = useState<string[]>([]);
  const [recentActivities, setRecentActivities] = useState<any[]>([]);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  // ── UI state ─────────────────────────────────────────────────────────
  const [collapsed, setCollapsed] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [logoutConfirm, setLogoutConfirm] = useState(false);

  // ── Navigation helper ────────────────────────────────────────────────
  const navigate = useCallback(
    (p: Page, paramId?: string | number) => {
      if (p === "create-listing") {
        if (paramId) {
          setSelectedPropertyId(String(paramId));
        } else {
          setSelectedPropertyId(null);
        }
      } else if (p === "edit-listing" || p === "listing-detail") {
        if (paramId) {
          setSelectedListingId(String(paramId));
        }
      } else if (p === "property-detail" || p === "edit-property") {
        if (paramId) {
          setSelectedPropertyId(String(paramId));
          if (p === "edit-property") setEditingPropertyId(String(paramId));
        }
      } else if (p === "edit-followup") {
        if (paramId) {
          setSelectedFollowupId(String(paramId));
        }
      } else if (p === "consultants") {
        setSelectedConsultantId(paramId ? String(paramId) : null);
      } else if (p === "edit-consultant") {
        if (paramId) {
          setSelectedConsultantId(String(paramId));
        }
      }
      setPage(p);
      setNotifOpen(false);
      setCmdOpen(false);
    },
    []
  );

  // ── Expired session → warn, then return to the login page ────────────
  // A tab left open past the idle timeout (or a logout performed in another
  // tab) leaves the SPA authenticated on screen while every request fails.
  // apiClient detects that centrally and calls back here, so the user gets one
  // clear Persian message instead of a puzzling per-screen error, and a moment
  // to read it before being sent to the login page.
  //
  // The handler is only installed for a signed-in page. On the login screen
  // there is no session to expire, so redirecting there would just reload the
  // page the user is already on.
  useEffect(() => {
    if (!initialData.isAuthenticated) return;
    onSessionExpired(() => {
      toast({ type: "error", message: SESSION_EXPIRED_MESSAGE });
      window.setTimeout(() => {
        window.location.assign(initialData.loginUrl || "/accounts/login/");
      }, 2000);
    });
    return () => onSessionExpired(null);
  }, [initialData.isAuthenticated, initialData.loginUrl]);

  // ── Clear form errors when a create/edit form is closed ──────────────
  // A submit error lives in App state (passed down as `submitError`), so it
  // survives navigating away and would still be shown the next time the form
  // opens. Drop it the moment we leave a form. The form's field data is local
  // state and resets on unmount, so create forms open completely fresh while
  // edit forms re-load their record from the backend.
  const prevPageRef = useRef<Page>(page);
  useEffect(() => {
    const prev = prevPageRef.current;
    prevPageRef.current = page;

    if (prev === "add-property" || prev === "edit-property") {
      setPropertyFormError(null);
    }
    if (prev === "create-listing" || prev === "edit-listing") {
      setListingFormError(null);
    }
    if (prev === "add-consultant" || prev === "edit-consultant") {
      setConsultantFormError(null);
    }
    if (prev === "create-followup" || prev === "edit-followup") {
      setFollowupsError(null);
    }
  }, [page]);

  // ── Authenticated-only data loading ──────────────────────────────────
  // React runs every hook in this component before the `isAuthenticated`
  // check further down decides to render the login screen instead of the
  // shell. Any unguarded fetch therefore also fires on the login page, where
  // it can only come back as 403 — so each loader below is gated on the
  // session the server rendered the page with.
  const isAuthenticated = initialData.isAuthenticated;

  // ── Fetch Task Types from Backend ──────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated) return;
    const fetchTaskTypes = async () => {
      try {
        const res = await apiFetch("/tasks/api/tasks/types/", { method: "GET" }, initialData.csrfToken);
        if (res.ok) {
          const data = await res.json();
          setTaskTypesList(data);
        }
      } catch (err) {
        console.error("Error fetching task types:", err);
      }
    };
    fetchTaskTypes();
  }, [isAuthenticated, initialData.csrfToken]);

  // ── Fetch Districts from Backend ───────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated) return;
    const fetchDistricts = async () => {
      try {
        const res = await apiFetch("/common/api/districts/", { method: "GET" }, initialData.csrfToken);
        if (res.ok) {
          const data = await res.json();
          setDistrictsList(data);
        }
      } catch (err) {
        console.error("Error fetching districts:", err);
      }
    };
    fetchDistricts();
  }, [isAuthenticated, initialData.csrfToken]);

  // ── Fetch Notifications from Backend ───────────────────────────────────
  const fetchNotifications = useCallback(async () => {
    try {
      const res = await apiFetch("/common/api/notifications/", { method: "GET" }, initialData.csrfToken);
      if (res.ok) {
        const data = await res.json();
        setNotifications(data.notifications || []);
        setUnreadCount(data.unreadCount || 0);
      }
    } catch (err) {
      console.error("Error fetching notifications:", err);
    }
  }, [initialData.csrfToken]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchNotifications();
      // Refresh every 30 seconds
      const interval = setInterval(fetchNotifications, 30000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, fetchNotifications]);

  // ── Listings API integration ────────────────────────────────────────
  const fetchListings = useCallback(async () => {
    setListingsLoading(true);
    setListingsError(null);
    try {
      const res = await apiFetch("/listings/api/listings/?page_size=1000", { method: "GET" }, initialData.csrfToken);
      if (!res.ok) throw new Error("خطا در دریافت لیست آگهی‌ها!");
      const data = await res.json();
      const items = Array.isArray(data) ? data : (data.results ?? []);
      setListings(items);
    } catch (error: any) {
      setListingsError(error.message || "خطا در بارگذاری");
    } finally {
      setListingsLoading(false);
    }
  }, [initialData.csrfToken]);

  useEffect(() => {
    if (page !== "listings" && page !== "my-listings") return;
    fetchListings();
  }, [page, fetchListings]);

  useEffect(() => {
    if (page !== "listing-detail" || !selectedListingId) return;

    setSelectedListing((prev) =>
      prev && String(prev.id) === String(selectedListingId) ? prev : undefined
    );

    const controller = new AbortController();
    async function loadListingDetail() {
      try {
        const res = await apiFetch(`/listings/api/listings/${selectedListingId}/`, { method: "GET", signal: controller.signal }, initialData.csrfToken);
        if (res.ok) {
          const data = await res.json();
          setSelectedListing(data);
        }
      } catch (err) {
        console.error("Error fetching listing detail:", err);
      }
    }

    loadListingDetail();
    return () => controller.abort();
  }, [page, selectedListingId, initialData.csrfToken]);

  const submitListing = useCallback(
    async (payload: Record<string, any>, listingId?: string | null) => {
      try {
        setListingFormSubmitting(true);
        setListingFormError(null);

        const isEdit = Boolean(listingId);
        const url = isEdit
          ? `/listings/api/listings/${listingId}/`
          : "/listings/api/listings/";
        const method = isEdit ? "PATCH" : "POST";

        const res = await apiFetch(url, { method, body: JSON.stringify(payload) }, initialData.csrfToken);

        const data = await readJson(res);

        if (!res.ok) {
          throw new Error(apiErrorMessage(data, "خطا در ثبت آگهی"));
        }

        setSelectedListing(data);
        setSelectedListingId(String(data.id));

        setListings((prev) => {
          const exists = prev.some((l) => String(l.id) === String(data.id));
          if (exists) {
            return prev.map((l) => (String(l.id) === String(data.id) ? data : l));
          }
          return [data, ...prev];
        });

        return { ok: true, data };
      } catch (error: any) {
        const message = error?.message || "خطا در ثبت اطلاعات آگهی";
        setListingFormError(message);
        return { ok: false, error: message };
      } finally {
        setListingFormSubmitting(false);
      }
    },
    [initialData.csrfToken]
  );

  const refreshDashboard = useCallback(async () => {
    try {
      const [props, lres, fres, cres, tres, dashRes, actRes] = await Promise.allSettled([
        apiFetch("/properties/api/properties/?page_size=1000", { method: "GET" }, initialData.csrfToken),
        apiFetch("/listings/api/listings/?page_size=1000", { method: "GET" }, initialData.csrfToken),
        apiFetch("/followupa/api/followups/", { method: "GET" }, initialData.csrfToken),
        apiFetch("/accounts/consultants/", { method: "GET" }, initialData.csrfToken),
        apiFetch("/tasks/api/tasks/summary/", { method: "GET" }, initialData.csrfToken),
        apiFetch("/common/api/analytics/dashboard/", { method: "GET" }, initialData.csrfToken),
        apiFetch("/common/api/activity-log/?page_size=6&days=30", { method: "GET" }, initialData.csrfToken),
      ]);

      let totalProps = 0;
      let activeListings = 0;
      let openTasks = 0;
      let followUpsDue = 0;
      let consultantCount = 0;
      let activeConsultantCount = 0;

      if (props.status === "fulfilled" && props.value.ok) {
        const data = await props.value.json();
        const items = Array.isArray(data) ? data : (data.results ?? []);
        // Use count if paginated, otherwise length
        totalProps = Array.isArray(data) ? data.length : (data.count ?? items.length);
        setProperties(items);
      }

      if (lres.status === "fulfilled" && lres.value.ok) {
        const data = await lres.value.json();
        const items = Array.isArray(data) ? data : (data.results ?? []);
        // For active listings, if paginated, count may need separate logic, but use filtered length of fetched page + total count awareness
        activeListings = items.filter((l: any) => l.status === "ACTIVE").length;
        // If API returns count, and we fetched with large page_size, active count from items is okay for dashboard; for precise total active, backend could provide filtered count, but we keep simple
        setListings(items);
      }

      if (fres.status === "fulfilled" && fres.value.ok) {
        const data = await fres.value.json();
        const items = Array.isArray(data) ? data : (data.results ?? []);
        followUpsDue = items.filter((f: any) => f.status === "scheduled").length;
        setFollowups(items);
      }

      if (cres.status === "fulfilled" && cres.value.ok) {
        const data = await cres.value.json();
        const items = Array.isArray(data) ? data : (data.results ?? []);
        consultantCount = items.length;
        activeConsultantCount = items.filter((c: any) => c.is_active).length;
        setConsultants(items);
      }

      if (tres.status === "fulfilled" && tres.value.ok) {
        const data = await tres.value.json();
        setTaskSummary(data);
        openTasks = (data?.pending || 0) + (data?.in_progress || 0);
      }

      if (dashRes.status === "fulfilled" && dashRes.value.ok) {
        const dash = await dashRes.value.json();
        setTopConsultants(dash.topConsultants || []);
        setRevenueMonthly(dash.revenueMonthly || []);
        setRevenueDealTypes(dash.revenueDealTypes || []);
        setPropertyComposition(dash.propertyComposition || []);
        setHotProperties(dash.hotProperties || []);
        setMyReport(dash.myReport || null);
        if (dash.kpis) {
          totalProps = dash.kpis.totalProperties ?? totalProps;
          activeListings = dash.kpis.activeListings ?? activeListings;
          openTasks = dash.kpis.openTasks ?? openTasks;
          followUpsDue = dash.kpis.followUpsDue ?? followUpsDue;
          consultantCount = dash.kpis.consultants ?? consultantCount;
          activeConsultantCount = dash.kpis.consultantsActive ?? activeConsultantCount;
        }
      }

      if (actRes.status === "fulfilled" && actRes.value.ok) {
        const actData = await actRes.value.json();
        setRecentActivities(actData.results || []);
      }

      setDashboardKpis({
        totalProperties: totalProps,
        activeListings,
        openTasks,
        followUpsDue,
        consultants: consultantCount,
        consultantsActive: activeConsultantCount,
      });
    } catch (err) {
      console.error("Failed to refresh dashboard:", err);
    }
  }, [initialData.csrfToken]);

  const handleListingAction = useCallback(
    async (actionName: "approve" | "reject" | "pause" | "archive" | "unarchive" | "delete" | "sold" | "set_status", listingId: string | number, status?: string) => {
      try {
        const isDelete = actionName === "delete";
        const url = `/listings/api/listings/${listingId}/${isDelete ? "" : actionName + "/"}`;
        const method = isDelete ? "DELETE" : "POST";
        const body = actionName === "set_status" && status ? JSON.stringify({ status }) : undefined;

        const res = await apiFetch(url, { method, ...(body ? { body } : {}) }, initialData.csrfToken);

        if (!res.ok) throw new Error(`عملیات ${actionName} با خطا مواجه شد.`);

        if (isDelete) {
          setListings((prev) => prev.filter((l) => String(l.id) !== String(listingId)));
          if (selectedListingId === String(listingId)) {
            setSelectedListing(undefined);
            setSelectedListingId(null);
          }
          toast({ type: "success", message: "آگهی با موفقیت حذف شد." });
          setPage("listings");
        } else {
          const updated = await res.json();
          setListings((prev) => prev.map((l) => (String(l.id) === String(listingId) ? updated : l)));
          if (selectedListingId === String(listingId)) {
            setSelectedListing(updated);
          }
          toast({ type: "success", message: "وضعیت آگهی با موفقیت تغییر کرد." });
          refreshDashboard();
        }
      } catch (err: any) {
        toast({ type: "error", message: err.message || "خطایی رخ داد" });
      }
    },
    [initialData.csrfToken, selectedListingId, refreshDashboard]
  );

  // ── Follow-ups API integration ───────────────────────────────────────
  const fetchFollowups = useCallback(async () => {
    setFollowupsLoading(true);
    setFollowupsError(null);

    try {
      const res = await apiFetch("/followupa/api/followups/", { method: "GET" }, initialData.csrfToken);

      if (!res.ok) throw new Error("خطا در دریافت پیگیری‌ها");

      const data = await res.json();
      const items = Array.isArray(data) ? data : (data.results ?? []);
      setFollowups(items);
    } catch (err) {
      setFollowupsError(
        err instanceof Error ? err.message : "خطای ناشناخته در بارگذاری پیگیری‌ها"
      );
    } finally {
      setFollowupsLoading(false);
    }
  }, [initialData.csrfToken]);

  const createFollowup = useCallback(async (payload: FollowUpCreatePayload) => {
    setFollowupsLoading(true);
    setFollowupsError(null);

    try {
      const res = await apiFetch("/followupa/api/followups/", { method: "POST", body: JSON.stringify(payload) }, initialData.csrfToken);

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const message = data && typeof data === "object" ? Object.values(data).flat().join(" / ") : "خطا در ثبت پیگیری";
        throw new Error(message);
      }
      await fetchFollowups();
    } catch (err) {
      setFollowupsError(
        err instanceof Error ? err.message : "خطا در ثبت پیگیری"
      );
      throw err;
    } finally {
      setFollowupsLoading(false);
    }
  }, [initialData.csrfToken, fetchFollowups]);

  const archiveFollowup = useCallback(async (id: string) => {
    try {
      const res = await apiFetch(`/followupa/api/followups/${id}/archive/`, { method: "POST" }, initialData.csrfToken);
      if (!res.ok) throw new Error("خطا در بایگانی پیگیری");
      toast({ type: "success", message: "پیگیری بایگانی شد." });
      await fetchFollowups();
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطای ناشناخته" });
    }
  }, [initialData.csrfToken, fetchFollowups]);

  const deleteFollowup = useCallback(async (id: string) => {
    try {
      const res = await apiFetch(`/followupa/api/followups/${id}/`, { method: "DELETE" }, initialData.csrfToken);
      if (!res.ok) throw new Error("خطا در حذف پیگیری");
      toast({ type: "success", message: "پیگیری حذف شد." });
      await fetchFollowups();
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطای ناشناخته" });
    }
  }, [initialData.csrfToken, fetchFollowups]);

  const completeFollowup = useCallback(async (id: string, outcome: string, probability: number) => {
    try {
      const res = await apiFetch(`/followupa/api/followups/${id}/`, {
        method: "PATCH",
        body: JSON.stringify({ status: "completed", outcome, probability }),
      }, initialData.csrfToken);
      if (!res.ok) throw new Error("خطا در تکمیل پیگیری");
      toast({ type: "success", message: "پیگیری تکمیل شد." });
      await fetchFollowups();
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطای ناشناخته" });
    }
  }, [initialData.csrfToken, fetchFollowups]);

  const updateFollowup = useCallback(async (id: string, payload: FollowUpCreatePayload) => {
    setFollowupsLoading(true);
    setFollowupsError(null);
    try {
      const res = await apiFetch(`/followupa/api/followups/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }, initialData.csrfToken);
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const message = data && typeof data === "object" ? Object.values(data).flat().join(" / ") : "خطا در ویرایش پیگیری";
        throw new Error(message);
      }
      const updated = await res.json().catch(() => null);
      if (updated) {
        setFollowups((prev) => prev.map((f) => String(f.id) === String(id) ? updated : f));
        setSelectedFollowup(updated);
      }
      await fetchFollowups();
    } catch (err) {
      setFollowupsError(
        err instanceof Error ? err.message : "خطا در ویرایش پیگیری"
      );
      throw err;
    } finally {
      setFollowupsLoading(false);
    }
  }, [initialData.csrfToken, fetchFollowups]);

  const submitFollowup = useCallback(async (payload: FollowUpCreatePayload, followupId?: string | null) => {
    if (followupId) {
      await updateFollowup(followupId, payload);
      return;
    }
    await createFollowup(payload);
  }, [createFollowup, updateFollowup]);

  const editFollowup = useCallback((id: string) => {
    setSelectedFollowupId(id);
    const existing = followups.find((f) => String(f.id) === String(id));
    setSelectedFollowup(existing);
    setPage("edit-followup");
    setNotifOpen(false);
    setCmdOpen(false);
  }, [followups]);

  useEffect(() => {
    if (page !== "follow-ups" && page !== "my-followups") return;
    fetchFollowups();
  }, [page, fetchFollowups]);

  useEffect(() => {
    if (page !== "edit-followup" || !selectedFollowupId) return;
    const existing = followups.find((f) => String(f.id) === String(selectedFollowupId));
    if (existing && (!selectedFollowup || String(selectedFollowup.id) !== String(selectedFollowupId))) {
      setSelectedFollowup(existing);
    }
    if (selectedFollowup && String(selectedFollowup.id) === String(selectedFollowupId)) return;
    const controller = new AbortController();
    (async () => {
      try {
        const res = await apiFetch(`/followupa/api/followups/${selectedFollowupId}/`, { method: "GET", signal: controller.signal }, initialData.csrfToken);
        if (res.ok) {
          const data = await res.json();
          setSelectedFollowup(data);
        }
      } catch (err) {
        console.error("Error fetching follow-up detail:", err);
      }
    })();
    return () => controller.abort();
  }, [page, selectedFollowupId, followups, selectedFollowup, initialData.csrfToken]);

  // ── Consultants API integration ──────────────────────────────────────
  const fetchConsultants = useCallback(async () => {
    setConsultantsLoading(true);
    setConsultantsError(null);
    try {
      const res = await apiFetch("/accounts/consultants/", { method: "GET" }, initialData.csrfToken);
      if (!res.ok) throw new Error("خطا در دریافت لیست مشاوران");
      const data = await res.json();
      const items = Array.isArray(data) ? data : (data.results ?? []);
      setConsultants(items);
    } catch (error: any) {
      setConsultantsError(error.message || "خطا در بارگذاری");
    } finally {
      setConsultantsLoading(false);
    }
  }, [initialData.csrfToken]);

  useEffect(() => {
    if (!isAuthenticated) return;
    fetchConsultants();
  }, [isAuthenticated, fetchConsultants]);

  // Load the admin's own profile so the sidebar/topbar avatar and the
  // "My Profile" screen reflect the admin account (admins are intentionally
  // absent from the consultants list).
  const fetchAdminProfile = useCallback(async () => {
    try {
      const res = await apiFetch("/accounts/admins/me/", { method: "GET" }, initialData.csrfToken);
      if (res.ok) {
        const data = await res.json();
        setAdminProfile(data);
      }
    } catch {
      // non-fatal: the shell falls back to the initials avatar
    }
  }, [initialData.csrfToken]);

  useEffect(() => {
    if (isAuthenticated && role === "admin") {
      fetchAdminProfile();
    }
  }, [isAuthenticated, role, fetchAdminProfile]);

  const toggleConsultantActive = useCallback(async (id: string, isActive: boolean) => {
    try {
      const res = await apiFetch(`/accounts/consultants/${id}/`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: isActive }),
      }, initialData.csrfToken);
      if (!res.ok) throw new Error(isActive ? "خطا در فعال‌سازی مجدد مشاور" : "خطا در بایگانی مشاور");
      toast({ type: "success", message: isActive ? "مشاور دوباره فعال شد." : "مشاور بایگانی شد." });
      await fetchConsultants();
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطای ناشناخته" });
    }
  }, [initialData.csrfToken, fetchConsultants]);

  const deleteConsultant = useCallback(async (id: string) => {
    try {
      const res = await apiFetch(`/accounts/consultants/${id}/`, { method: "DELETE" }, initialData.csrfToken);
      if (!res.ok) throw new Error("خطا در حذف مشاور");
      toast({ type: "success", message: "مشاور حذف شد." });
      await fetchConsultants();
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطای ناشناخته" });
    }
  }, [initialData.csrfToken, fetchConsultants]);

  const editConsultant = useCallback((id: string) => {
    setSelectedConsultantId(id);
    setPage("edit-consultant");
    setNotifOpen(false);
    setCmdOpen(false);
  }, []);

  const submitConsultantUpdate = useCallback(
    async (id: string, payload: Record<string, any>) => {
      setConsultantFormSubmitting(true);
      setConsultantFormError(null);
      try {
        const hasImage = payload.profile_image instanceof File;
        let data: any;

        if (hasImage) {
          // Use FormData for file upload
          const formData = new FormData();
          if (payload.first_name) formData.append("first_name", payload.first_name);
          if (payload.last_name) formData.append("last_name", payload.last_name);
          if (payload.full_name) formData.append("full_name", payload.full_name);
          if (payload.email) formData.append("email", payload.email);
          if (payload.mobile) formData.append("mobile", payload.mobile);
          if (payload.branch) formData.append("branch", payload.branch);
          if (payload.notes !== undefined) formData.append("notes", payload.notes);
          formData.append("profile_image", payload.profile_image);

          // apiFetch leaves the Content-Type to the browser for a FormData
          // body, so the upload keeps its multipart boundary while still
          // getting the shared CSRF retry and error translation.
          const res = await apiFetch(
            `/accounts/consultants/${id}/`,
            { method: "PATCH", body: formData },
            initialData.csrfToken
          );

          data = await readJson(res).catch(() => null);
          if (!res.ok) {
            throw new Error(apiErrorMessage(data, "خطا در ویرایش مشاور"));
          }
        } else {
          // Use JSON for normal update
          const res = await apiFetch(
            `/accounts/consultants/${id}/`,
            { method: "PATCH", body: JSON.stringify(payload) },
            initialData.csrfToken
          );
          data = await res.json().catch(() => null);
          if (!res.ok) {
            const message = data && typeof data === "object"
              ? Object.values(data).flat().join(" / ")
              : "خطا در ویرایش مشاور";
            throw new Error(message);
          }
        }

        setConsultants((prev) => prev.map((c) => String(c.id) === String(data.id) ? data : c));
        await fetchConsultants();
        toast({ type: "success", message: "مشاور با موفقیت ویرایش شد." });
        return { ok: true, data };
      } catch (error: any) {
        const message = error?.message || "خطا در ویرایش مشاور";
        setConsultantFormError(message);
        return { ok: false, error: message };
      } finally {
        setConsultantFormSubmitting(false);
      }
    },
    [initialData.csrfToken, fetchConsultants]
  );

  // ── Properties API integration ───────────────────────────────────────
  const openPropertyDetail = useCallback((id: string) => {
    setSelectedPropertyId(id);
    setPage("property-detail");
    setNotifOpen(false);
    setCmdOpen(false);
  }, []);

  const openPropertyEdit = useCallback((id: string) => {
    setEditingPropertyId(id);
    setSelectedPropertyId(id);
    setPage("edit-property");
    setNotifOpen(false);
    setCmdOpen(false);
  }, []);

  const fetchProperties = useCallback(async () => {
    setPropertiesLoading(true);
    setPropertiesError(null);
    try {
      // Use large page_size to get all for dashboard/KPIs; pagination-enabled endpoint returns count
      const res = await apiFetch("/properties/api/properties/?page_size=1000", { method: "GET" }, initialData.csrfToken);
      if (!res.ok) throw new Error("خطا در دریافت لیست املاک");
      const data = await res.json();
      const items = Array.isArray(data) ? data : (data.results ?? []);
      setProperties(items);
      return items;
    } catch (error: any) {
      setPropertiesError(error.message || "خطا در بارگذاری");
      return [];
    } finally {
      setPropertiesLoading(false);
    }
  }, [initialData.csrfToken]);

  useEffect(() => {
    if (page !== "properties" && page !== "my-properties" && page !== "add-property" && page !== "edit-property" && page !== "create-followup" && page !== "edit-followup" && page !== "follow-ups") return;
    fetchProperties();
  }, [page, fetchProperties]);
  
  useEffect(() => {
    const wantedId = page === "edit-property"
      ? (editingPropertyId || selectedPropertyId)
      : selectedPropertyId;
    if ((page !== "property-detail" && page !== "edit-property") || !wantedId) return;

    if (selectedProperty && String(selectedProperty.id) === String(wantedId)) return;

    const controller = new AbortController();
    async function loadDetail() {
      try {
        const res = await apiFetch(`/properties/api/properties/${wantedId}/`, { method: "GET", signal: controller.signal }, initialData.csrfToken);
        if (res.ok) {
          const data = await res.json();
          setSelectedProperty(data);
        }
      } catch (err) {
        console.error("Error fetching property detail:", err);
      }
    }

    loadDetail();
    return () => controller.abort();
  }, [page, selectedPropertyId, editingPropertyId, selectedProperty, initialData.csrfToken]);

  const submitProperty = useCallback(
    async (payload: Record<string, any>, propertyId?: string | null) => {
      try {
        setPropertyFormSubmitting(true);
        setPropertyFormError(null);

        const isEdit = Boolean(propertyId);
        const url = isEdit
          ? `/properties/api/properties/${propertyId}/`
          : "/properties/api/properties/";
        const method = isEdit ? "PATCH" : "POST";

        const res = await apiFetch(url, { method, body: JSON.stringify(payload) }, initialData.csrfToken);

        const data = await readJson(res);

        if (!res.ok) {
          throw new Error(apiErrorMessage(data, "خطا در ثبت ملک"));
        }

        setSelectedProperty(data);
        setSelectedPropertyId(String(data.id));
        setEditingPropertyId(String(data.id));

        setProperties((prev) => {
          const exists = prev.some((p) => String(p.id) === String(data.id));
          if (exists) {
            return prev.map((p) => (String(p.id) === String(data.id) ? data : p));
          }
          return [data, ...prev];
        });

        return { ok: true, data };
      } catch (error: any) {
        const message = error?.message || "خطا در ثبت اطلاعات ملک";
        setPropertyFormError(message);
        return { ok: false, error: message };
      } finally {
        setPropertyFormSubmitting(false);
      }
    },
    [initialData.csrfToken]
  );

  const uploadPropertyImages = useCallback(
    async (propertyId: string, files: File[]) => {
      if (!files.length) {
        return { ok: true };
      }

      const formData = new FormData();
      files.forEach((file) => {
        formData.append("images", file);
      });

      const res = await apiFetch(
        `/properties/api/properties/${propertyId}/images/`,
        { method: "POST", body: formData },
        initialData.csrfToken
      );

      const data = await readJson(res);

      if (!res.ok) {
        throw new Error(apiErrorMessage(data, "خطا در آپلود تصاویر"));
      }

      return { ok: true, data };
    },
    [initialData.csrfToken]
  );

  const deletePropertyImage = useCallback(
    async (propertyId: string, imageId: string) => {
      const res = await apiFetch(
        `/properties/api/properties/${propertyId}/images/${imageId}/`,
        { method: "DELETE" },
        initialData.csrfToken
      );
      if (!res.ok && res.status !== 204) {
        const data = await readJson(res);
        throw new Error(apiErrorMessage(data, "خطا در حذف تصویر"));
      }
      setSelectedProperty((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          images: (prev.images || []).filter((img: any) => String(img.id) !== String(imageId)),
        };
      });
    },
    [initialData.csrfToken]
  );

  const reorderPropertyImages = useCallback(
    async (propertyId: string, order: { id: string | number; sort_order: number }[]) => {
      const res = await apiFetch(
        `/properties/api/properties/${propertyId}/images-reorder/`,
        { method: "PATCH", body: JSON.stringify(order) },
        initialData.csrfToken
      );
      const data = await readJson(res);
      if (!res.ok) {
        throw new Error(apiErrorMessage(data, "خطا در تغییر ترتیب تصاویر"));
      }
      if (Array.isArray(data)) {
        setSelectedProperty((prev) => {
          if (!prev) return prev;
          return { ...prev, images: data };
        });
      }
    },
    [initialData.csrfToken]
  );

  const archiveProperty = useCallback(async (id: string) => {
    try {
      const res = await apiFetch(`/properties/api/properties/${id}/`, {
        method: "PATCH",
        body: JSON.stringify({ status: "INACTIVE" }),
      }, initialData.csrfToken);
      if (!res.ok) throw new Error("خطا در بایگانی ملک");
      toast({ type: "success", message: "ملک بایگانی شد." });
      await fetchProperties();
      setPage("properties");
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطای ناشناخته" });
    }
  }, [initialData.csrfToken, fetchProperties]);

  const deleteProperty = useCallback(async (id: string) => {
    try {
      const res = await apiFetch(`/properties/api/properties/${id}/`, { method: "DELETE" }, initialData.csrfToken);
      if (!res.ok) throw new Error("خطا در حذف ملک");
      toast({ type: "success", message: "ملک حذف شد." });
      await fetchProperties();
      setPage("properties");
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطای ناشناخته" });
    }
  }, [initialData.csrfToken, fetchProperties]);

  const updatePropertyStatus = useCallback(async (id: string, status: string): Promise<boolean> => {
    try {
      const res = await apiFetch(`/properties/api/properties/${id}/`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }, initialData.csrfToken);
      const data = await readJson(res);
      if (!res.ok) throw new Error(apiErrorMessage(data, "خطا در تغییر وضعیت ملک"));

      setSelectedProperty(data);
      setProperties((prev) => prev.map((p) => (String(p.id) === String(id) ? data : p)));
      toast({ type: "success", message: "وضعیت ملک بروزرسانی شد." });
      return true;
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطا در تغییر وضعیت ملک" });
      return false;
    }
  }, [initialData.csrfToken]);

  const togglePropertyShared = useCallback(async (id: string): Promise<boolean> => {
    try {
      const res = await apiFetch(`/properties/api/properties/${id}/toggle-shared/`, {
        method: "POST",
      }, initialData.csrfToken);
      const data = await readJson(res);
      if (!res.ok) throw new Error(apiErrorMessage(data, "خطا در تغییر وضعیت اشتراک‌گذاری"));
      setSelectedProperty(data);
      setProperties((prev) => prev.map((p) => (String(p.id) === String(id) ? data : p)));
      toast({ type: "success", message: data.isShared ? "ملک برای همه مشاوران قابل مشاهده شد." : "ملک فقط برای مشاور مربوطه قابل مشاهده شد." });
      return true;
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطای ناشناخته" });
      return false;
    }
  }, [initialData.csrfToken]);

  // ── Consultant (account) creation ────────────────────────────────────
  const submitConsultant = useCallback(
    async (payload: Record<string, any>) => {
      try {
        setConsultantFormSubmitting(true);
        setConsultantFormError(null);

        const hasImage = payload.profile_image instanceof File;

        if (hasImage) {
          // Use FormData for file upload
          const formData = new FormData();
          formData.append("first_name", payload.first_name || "");
          formData.append("last_name", payload.last_name || "");
          formData.append("username", payload.username || payload.email || "");
          formData.append("email", payload.email || "");
          formData.append("password", payload.password || "");
          formData.append("mobile", payload.mobile || "");
          formData.append("branch", payload.branch || "");
          formData.append("full_name", `${payload.first_name || ""} ${payload.last_name || ""}`.trim());
          formData.append("is_active", "true");
          formData.append("profile_image", payload.profile_image);

          const res = await apiFetch(
            "/accounts/consultants/",
            { method: "POST", body: formData },
            initialData.csrfToken
          );

          const data = await readJson(res).catch(() => null);

          if (!res.ok) {
            throw new Error(apiErrorMessage(data, "خطا در ثبت مشاور"));
          }

          setConsultants((prev) => [data, ...prev]);
          await fetchConsultants();
          toast({ type: "success", message: "مشاور با موفقیت ایجاد شد." });

          return { ok: true, data };
        } else {
          // Use JSON for normal submission
          const normalizedPayload = {
            first_name: payload.first_name,
            last_name: payload.last_name,
            username: payload.username || payload.email || "",
            email: payload.email,
            password: payload.password,
            mobile: payload.mobile,
            branch: payload.branch,
            full_name: `${payload.first_name || ""} ${payload.last_name || ""}`.trim(),
            is_active: true,
          };

          const res = await apiFetch("/accounts/consultants/", {
            method: "POST",
            body: JSON.stringify(normalizedPayload),
          }, initialData.csrfToken);

          const data = await res.json().catch(() => null);

          if (!res.ok) {
            const message = data && typeof data === "object"
              ? Object.values(data).flat().join(" / ")
              : "خطا در ثبت مشاور";
            throw new Error(message);
          }

          setConsultants((prev) => [data, ...prev]);
          await fetchConsultants();
          toast({ type: "success", message: "مشاور با موفقیت ایجاد شد." });

          return { ok: true, data };
        }
      } catch (error: any) {
        const message = error?.message || "خطا در ثبت مشاور";
        setConsultantFormError(message);
        return { ok: false, error: message };
      } finally {
        setConsultantFormSubmitting(false);
      }
    },
    [initialData.csrfToken, fetchConsultants]
  );

  // ── Tasks API integration ────────────────────────────────────────────
  const fetchTasks = useCallback(async () => {
    setTasksLoading(true);
    setTasksError(null);
    try {
      const res = await apiFetch("/tasks/api/tasks/", { method: "GET" }, initialData.csrfToken);
      if (!res.ok) throw new Error("خطا در دریافت وظایف");
      const data = await res.json();
      const items = Array.isArray(data) ? data : (data.results ?? []);
      setTasks(items);
      return items;
    } catch (err: any) {
      setTasksError(err?.message || "خطا در بارگذاری وظایف");
      return [];
    } finally {
      setTasksLoading(false);
    }
  }, [initialData.csrfToken]);

  const fetchTaskSummary = useCallback(async () => {
    try {
      const res = await apiFetch("/tasks/api/tasks/summary/", { method: "GET" }, initialData.csrfToken);
      if (res.ok) {
        const data = await res.json();
        setTaskSummary(data);
      }
    } catch (err) {
      console.error("Error fetching task summary:", err);
    }
  }, [initialData.csrfToken]);

  useEffect(() => {
    if (page !== "tasks-kanban" && page !== "create-task" && page !== "tasks-calendar" && page !== "my-tasks" && page !== "consultant-dashboard" && page !== "admin-dashboard") return;
    fetchTasks();
  }, [page, fetchTasks]);

  const createTask = useCallback(async (payload: Record<string, any>) => {
    const res = await apiFetch("/tasks/api/tasks/", { method: "POST", body: JSON.stringify(payload) }, initialData.csrfToken);
    const data = await readJson(res);
    if (!res.ok) {
      throw new Error(apiErrorMessage(data, "خطا در ایجاد وظیفه"));
    }
    setTasks((prev) => [data, ...prev]);
    fetchTaskSummary();
    return data;
  }, [initialData.csrfToken, fetchTaskSummary]);

  const updateTaskStatus = useCallback(async (id: string, status: string) => {
    const res = await apiFetch(`/tasks/api/tasks/${id}/`, { method: "PATCH", body: JSON.stringify({ status }) }, initialData.csrfToken);
    const data = await readJson(res);
    if (!res.ok) {
      throw new Error(apiErrorMessage(data, "خطا در تغییر وضعیت وظیفه"));
    }
    setTasks((prev) => prev.map((t) => String(t.id) === String(id) ? data : t));
    fetchTaskSummary();
    return data;
  }, [initialData.csrfToken, fetchTaskSummary]);

  const saveTask = useCallback(async (id: string, patch: Record<string, any>) => {
    const res = await apiFetch(`/tasks/api/tasks/${id}/`, { method: "PATCH", body: JSON.stringify(patch) }, initialData.csrfToken);
    const data = await readJson(res);
    if (!res.ok) {
      throw new Error(apiErrorMessage(data, "خطا در ذخیره وظیفه"));
    }
    setTasks((prev) => prev.map((t) => String(t.id) === String(id) ? data : t));
    return data;
  }, [initialData.csrfToken]);
  
  const deleteTask = useCallback(async (id: string) => {
    const res = await apiFetch(`/tasks/api/tasks/${id}/`, { method: "DELETE" }, initialData.csrfToken);
    if (!res.ok) {
      const data = await readJson(res);
      throw new Error(apiErrorMessage(data, "خطا در حذف وظیفه"));
    }
    setTasks((prev) => prev.filter((t) => String(t.id) !== String(id)));
    fetchTaskSummary();
  }, [initialData.csrfToken, fetchTaskSummary]);

  useEffect(() => {
    if (page === "admin-dashboard" || page === "consultant-dashboard") {
      refreshDashboard();
    }
  }, [page, refreshDashboard]);

  // ── Page renderer ────────────────────────────────────────────────────

  // The dashboard "پیگیری‌های پیش‌رو" widget shows five scheduled follow-ups:
  // overdue ones first, then the newest activity (created or edited) — the
  // same recency rule the follow-ups list page applies.
  //
  // The whole order is decided here, in one pass, for two reasons:
  //
  //  * Grouping has to happen BEFORE the list is cut to five. Slicing first
  //    and grouping afterwards only reorders whichever five were touched most
  //    recently, so a backlog of older overdue follow-ups never surfaced at
  //    all — exactly the rows the widget exists to highlight.
  //
  //  * Equal timestamps need a deterministic tie-breaker. Records created or
  //    edited in the same instant (a seeded database, a bulk import, quick
  //    successive edits) compare equal on `updatedAt`, and the API is then
  //    free to return them in any order. Without the `id` fallback the widget
  //    reshuffled those rows on every refresh, which is the jumbled ordering
  //    reported against this panel. The list page already breaks ties this
  //    way; matching it keeps the two screens consistent.
  const upcomingFollowups = useMemo(() => {
    const activity = (f: FollowUp) =>
      new Date(f.updatedAt || f.createdAt || f.date || 0).getTime();

    return followups
      .filter((f) => f.status === "scheduled")
      .slice()
      .sort((a, b) => {
        const overdue = Number(isFollowUpOverdue(b)) - Number(isFollowUpOverdue(a));
        if (overdue !== 0) return overdue;

        const recency = activity(b) - activity(a);
        if (recency !== 0) return recency;

        return String(b.id).localeCompare(String(a.id));
      })
      .slice(0, 5);
  }, [followups]);

  const renderPage = () => {
    switch (page) {
      case "admin-dashboard":
        return <AdminDashboard kpis={dashboardKpis} navigate={navigate} onRefresh={refreshDashboard} topConsultants={topConsultants} recentActivities={recentActivities} tasks={tasks} upcomingFollowups={upcomingFollowups} revenueMonthly={revenueMonthly} revenueDealTypes={revenueDealTypes} propertyComposition={propertyComposition} hotProperties={hotProperties} properties={properties} onSaveTask={saveTask} onDeleteTask={deleteTask} />;
      case "properties":
        return (
          <PropertiesPage
            navigate={navigate}
            role={role}
            properties={properties}
            loading={propertiesLoading}
            openPropertyDetail={openPropertyDetail}
            openPropertyEdit={openPropertyEdit}
            onArchive={archiveProperty}
            onDelete={deleteProperty}
            onToggleShared={togglePropertyShared}
            consultants={consultants}
            districtsList={districtsList}
            csrfToken={initialData.csrfToken}
          />
        );

      case "property-detail":
        return (
          <PropertyDetail
            navigate={navigate}
            role={role}
            property={selectedProperty}
            onArchive={archiveProperty}
            onDelete={deleteProperty}
            onUpdateStatus={updatePropertyStatus}
            onToggleShared={togglePropertyShared}
            openPropertyEdit={openPropertyEdit}
            openPropertyReport={(id) => { setSelectedPropertyIdForReport(id); setPage("property-reports"); }}
            onDeleteImage={deletePropertyImage}
            onUploadImages={uploadPropertyImages}
            onReorderImages={reorderPropertyImages}
          />
        );
      case "property-reports": {
        const pid = selectedPropertyIdForReport || selectedPropertyId;
        const prop = (properties || []).find((p) => String(p.id) === String(pid)) || selectedProperty;
        return (
          <PropertyReportsPage
            csrfToken={initialData.csrfToken}
            propertyId={pid ? String(pid) : null}
            propertyPreview={prop}
            onBack={() => {
              if (pid) { setSelectedPropertyId(pid); setPage("property-detail"); } else { setPage("properties"); }
            }}
          />
        );
      }
      case "add-property":
        return (
          <AddPropertyWizard
            navigate={navigate}
            role={role}
            onSubmit={submitProperty}
            onUploadImages={uploadPropertyImages}
            isSubmitting={propertyFormSubmitting}
            submitError={propertyFormError}
            consultants={consultants}
            districtsList={districtsList}
            properties={properties}
            csrfToken={initialData.csrfToken}
          />
        );
      case "edit-property": {
        const editTargetId = editingPropertyId || selectedPropertyId;
        return (
          <EditPropertyWizard
            navigate={navigate}
            role={role}
            property={selectedProperty && String(selectedProperty.id) === String(editTargetId) ? selectedProperty : undefined}
            propertyId={editTargetId}
            onSubmit={submitProperty}
            isSubmitting={propertyFormSubmitting}
            submitError={propertyFormError}
            consultants={consultants}
            districtsList={districtsList}
            properties={properties}
            csrfToken={initialData.csrfToken}
          />
        );
      }
      case "listings":
        return (
          <ListingsPage
            navigate={(p, id) => {
              if (id) {
                if (p === "listing-detail") setSelectedListingId(String(id));
                if (p === "edit-listing") setSelectedListingId(String(id));
              }
              navigate(p as Page);
            }}
            role={role}
            currentConsultantId={currentConsultantId}
            consultants={consultants}
            properties={properties}
            listings={listings}
            onAction={handleListingAction}
            loading={listingsLoading}
          />
        );
      case "my-listings":
        return (
          <ListingsPage
            navigate={(p, id) => {
              if (id) {
                if (p === "listing-detail") setSelectedListingId(String(id));
                if (p === "edit-listing") setSelectedListingId(String(id));
              }
              navigate(p as Page);
            }}
            role={role}
            currentConsultantId={currentConsultantId}
            consultants={consultants}
            properties={properties}
            listings={listings}
            onAction={handleListingAction}
            loading={listingsLoading}
          />
        );
      case "create-listing":
        return (
          <CreateListingWizard
            navigate={navigate}
            role={role}
            preselectedPropertyId={selectedPropertyId || undefined}
            currentConsultantId={currentConsultantId}
            currentConsultant={consultants.find(c => String(c.user?.id || c.id) === String(currentConsultantId))}
            consultants={consultants}
            properties={properties}
            onSubmit={submitListing}
            isSubmitting={listingFormSubmitting}
            submitError={listingFormError}
            csrfToken={initialData.csrfToken}
          />
        );
      case "edit-listing":
        return (
          <CreateListingWizard
            navigate={navigate}
            role={role}
            editingListing={selectedListing}
            currentConsultantId={currentConsultantId}
            currentConsultant={consultants.find(c => String(c.user?.id || c.id) === String(currentConsultantId))}
            consultants={consultants}
            properties={properties}
            onSubmit={submitListing}
            isSubmitting={listingFormSubmitting}
            submitError={listingFormError}
            csrfToken={initialData.csrfToken}
          />
        );
      case "listing-detail":
        return (
          <ListingDetailPage
            navigate={(p, id) => {
              if (id) {
                if (p === "edit-listing" || p === "listing-detail") {
                  setSelectedListingId(String(id));
                }
                if (p === "property-detail" || p === "edit-property") {
                  setSelectedPropertyId(String(id));
                  if (p === "edit-property") {
                    setEditingPropertyId(String(id));
                  }
                }
              }
              navigate(p as Page);
            }}
            role={role}
            listing={selectedListing}
            onAction={handleListingAction}
          />
        );
      case "tasks-kanban":
      case "create-task":
        return (
          <TasksKanban
            key={page}
            tasks={tasks} 
            loading={tasksLoading} 
            consultants={consultants} 
            properties={properties} 
            onCreate={createTask}
            onStatusChange={updateTaskStatus}
            onSave={saveTask}
            onDelete={deleteTask}
            currentUserId={currentConsultantId}
            role={role}
            taskTypesList={taskTypesList}
            initialCreateOpen={page === "create-task"}
            onCreateDismiss={page === "create-task" ? () => navigate("tasks-kanban") : undefined}
          />
        );
      case "tasks-calendar": 
        return <TasksCalendar tasks={tasks} />;
      case "consultants":
        return (
          <ConsultantsPage
            navigate={navigate}
            consultants={consultants}
            loading={consultantsLoading}
            error={consultantsError}
            onToggleActive={toggleConsultantActive}
            onDelete={deleteConsultant}
            onEdit={editConsultant}
            csrfToken={initialData.csrfToken}
            initialConsultantId={selectedConsultantId}
          />
        );
      case "add-consultant":
        return (
          <AddConsultantPage
            navigate={navigate}
            onSubmit={submitConsultant}
            isSubmitting={consultantFormSubmitting}
            submitError={consultantFormError}
            districtsList={districtsList}
          />
        );
      case "edit-consultant":
        return (
          <EditConsultantPage
            navigate={navigate}
            consultant={consultants.find((c) => String(c.id) === String(selectedConsultantId))}
            onSubmit={submitConsultantUpdate}
            isSubmitting={consultantFormSubmitting}
            submitError={consultantFormError}
            districtsList={districtsList}
          />
        );
      case "follow-ups":
      case "my-followups":
        return (
          <FollowUpsPage
            navigate={navigate}
            followups={followups}
            loading={followupsLoading}
            error={followupsError}
            onArchive={archiveFollowup}
            onDelete={deleteFollowup}
            onComplete={completeFollowup}
            onEdit={editFollowup}
            currentUserId={currentConsultantId}
            page={page}
            role={role}
            consultants={consultants}
            properties={properties}
          />
        );
      case "create-followup":
        return (
          <CreateFollowUp
            navigate={navigate}
            role={role}
            onSubmit={submitFollowup}
            isSubmitting={followupsLoading}
            submitError={followupsError}
            currentUserId={currentConsultantId}
            consultants={consultants}
            properties={properties}
            userName={userName}
          />
        );
      case "edit-followup": {
        const editing = selectedFollowup && String(selectedFollowup.id) === String(selectedFollowupId)
          ? selectedFollowup
          : undefined;
        if (!editing) {
          return <div className="p-6 text-sm text-muted-foreground">در حال بارگذاری پیگیری…</div>;
        }
        return (
          <CreateFollowUp
            navigate={navigate}
            role={role}
            onSubmit={submitFollowup}
            isSubmitting={followupsLoading}
            submitError={followupsError}
            currentUserId={currentConsultantId}
            consultants={consultants}
            properties={properties}
            userName={userName}
            editingFollowup={editing}
          />
        );
      }
      case "activity": return <ActivityLogPage csrfToken={initialData.csrfToken} />;
      case "manage-attributes": return <AttributesPage csrfToken={initialData.csrfToken} />;
      case "manage-districts": return <DistrictsPage csrfToken={initialData.csrfToken} onDistrictsChanged={() => {
        apiFetch("/common/api/districts/", { method: "GET" }, initialData.csrfToken)
          .then(res => res.ok ? res.json() : [])
          .then(data => setDistrictsList(data))
          .catch(() => {});
      }} />;
      case "settings-workspace": case "settings-users": case "settings-permissions": return <SettingsPage page={page} navigate={navigate} role={role} csrfToken={initialData.csrfToken} />;
      case "consultant-dashboard":
        return (
          <ConsultantDashboard
            navigate={navigate}
            tasks={tasks}
            followups={followups}
            userName={userName}
            consultantId={currentConsultantId}
            recentActivities={recentActivities}
            onSaveTask={saveTask}
            onDeleteTask={deleteTask}
            myReport={myReport}
            propertyComposition={propertyComposition}
            kpis={{
              properties: properties.filter(p => String(p.consultantId ?? p.consultant ?? "") === String(currentConsultantId)).length,
              listings: listings.filter(l => l.status === "ACTIVE" && (String(l.assigned_to) === String(currentConsultantId) || String((l as any).created_by) === String(currentConsultantId))).length,
              openTasks: tasks.filter(t => String(t.assigneeId) === String(currentConsultantId) && t.status !== "COMPLETED" && t.status !== "CANCELLED").length,
            }}
          />
        );
      case "my-properties":
        return (
          <MyPropertiesPage
            navigate={navigate}
            properties={properties}
            consultantId={currentConsultantId}
            openPropertyDetail={openPropertyDetail}
            openPropertyEdit={openPropertyEdit}
            onArchive={archiveProperty}
            csrfToken={initialData.csrfToken}
            userName={userName}
          />
        );
      case "my-tasks":
        return (
          <MyTasksPage
            tasks={tasks}
            consultantId={currentConsultantId}
            onSave={saveTask}
            onStatusChange={updateTaskStatus}
            onDelete={deleteTask}
          />
        );
      case "my-profile": case "my-profile-edit": case "my-profile-security":
        return <MyProfilePage page={page} navigate={navigate} userName={userName} role={role} csrfToken={initialData.csrfToken} onProfileUpdated={(newName) => { setUserName(newName); if (role === "admin") { fetchAdminProfile(); } }} districtsList={districtsList} />;
      default: return <div className="p-6"><EmptyState icon={<Layers size={28} />} title="به‌زودی" description="این بخش در حال توسعه است." /></div>;
    }
  };

  // Logout is the app's only POST that navigates the browser, so it must be
  // CSRF-proof in every browser state. The previous raw-form submit read the
  // token from `document.cookie` and fell back to the page-rendered token;
  // Django rotates the CSRF secret on every login, so a missing or stale
  // cookie made the POST fail with a raw 403 page and no recovery path.
  //
  // The flow below:
  //   1. refreshes the csrftoken cookie by hitting a CSRF-issuing page
  //      (Django re-issues the cookie there), so the token we send and the
  //      cookie the browser sends can never disagree;
  //   2. logs out through the shared API client (X-CSRFToken header) — the
  //      same mechanism every other write in the app uses. The server
  //      answers with the redirect to the login page, which fetch follows;
  //   3. navigates to the login page once the server-side session is gone.
  const handleLogout = () => {
    setLogoutConfirm(false);

    // Tell the API client a logout is intentionally in progress so any
    // background request that returns a 403 once the session is destroyed is
    // not misread as an idle-timeout expiry (which would schedule a second
    // redirect and make the login page appear to keep reloading).
    beginIntentionalLogout();

    void (async () => {
      const logoutUrl = initialData.logoutUrl || "/accounts/logout/";
      const loginUrl = initialData.loginUrl || "/accounts/login/";

      try {
        // Step 1 — refresh the CSRF cookie. Non-fatal by design: the POST
        // below has its own error handling if this call cannot complete.
        try {
          await fetch(loginUrl, {
            method: "GET",
            credentials: "include",
            cache: "no-store",
          });
        } catch {
          // Proceed with the current token state.
        }

        // Step 2 — log out exactly like any other API call in the app.
        const res = await apiFetch(logoutUrl, { method: "POST" });

        if (!res.ok) {
          toast({
            type: "error",
            message: "خروج از حساب ممکن نشد. صفحه برای به‌روزرسانی نشست بازنشانی می‌شود.",
          });
          window.location.reload();
          return;
        }

        // Step 3 — the server-side session is already destroyed; land on the
        // login page.
        window.location.assign(loginUrl);
      } catch {
        window.location.reload();
      }
    })();
  };

  // Avatar of the currently logged-in user: admins come from their own
  // profile endpoint, consultants from the consultants list.
  const currentUserImageUrl = role === "admin"
    ? (adminProfile?.profile_image ?? null)
    : consultants.find((c) => String(c.user?.id || c.id) === String(currentConsultantId))?.profile_image;

  if (!initialData.isAuthenticated) {
    return (
      <>
        <LoginPage initialData={initialData} navigate={navigate} />
        <ToastContainer />
      </>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar role={role} page={page} navigate={navigate} collapsed={collapsed} setCollapsed={setCollapsed} userName={userName} userImageUrl={currentUserImageUrl} onLogout={() => setLogoutConfirm(true)} />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <TopBar userName={userName} userImageUrl={currentUserImageUrl} role={role} onCmd={() => setCmdOpen(true)} onNotif={() => setNotifOpen((p) => !p)} notifOpen={notifOpen} unreadCount={unreadCount} />
        <main className="flex-1 overflow-y-auto" style={{ scrollbarWidth: "none" }}>{renderPage()}</main>
      </div>
      <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} navigate={navigate} role={role} />
      <NotifDrawer open={notifOpen} onClose={() => setNotifOpen(false)} notifications={notifications} csrfToken={initialData.csrfToken} />
      <ConfirmModal open={logoutConfirm} title="خروج از حساب؟" message="به صفحه ورود بازگردانده می‌شوید." onConfirm={handleLogout} onCancel={() => setLogoutConfirm(false)} />
      <ToastContainer />
    </div>
  );
}
