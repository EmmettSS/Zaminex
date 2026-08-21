// =============================================================================
//  Types (extracted exactly from App.tsx)
// =============================================================================

import type React from "react";

type Role = "admin" | "consultant";
type Page =
  | "login" | "forgot"
  | "admin-dashboard" | "properties" | "property-detail" | "add-property" | "edit-property"
  | "listings" | "create-listing" | "listing-detail" | "edit-listing"
  | "tasks-kanban" | "tasks-calendar" | "create-task"
  | "consultants" | "add-consultant" | "edit-consultant"
  | "follow-ups" | "create-followup" | "edit-followup"
  | "property-reports"
  | "activity"
  | "settings-workspace" | "settings-users" | "settings-permissions" | "manage-districts" | "districts" | "manage-attributes"
  | "consultant-dashboard" | "my-properties" | "my-listings" | "my-tasks" | "my-followups"
  | "my-profile" | "my-profile-edit" | "my-profile-security";

interface TaskHistoryEntry { id: string; action: string; from?: string; to?: string; note?: string; user: string; time: string; }

type ConsultantItem = {
  id: string | number;
  full_name: string;
  email?: string;
  phone?: string;
  mobile?: string;
  role?: string;
  branch?: string;
  is_active?: boolean;
  profile_image?: string | null;
  user?: {
    id: string | number;
    username: string;
    first_name: string;
    last_name: string;
    email: string;
    role: string;
  };
};

type FollowUpType = "Call" | "Meeting" | "Email" | "Site Visit";
type FollowUpStatus = "scheduled" | "completed" | "cancelled";

type FollowUp = {
  id: string;
  type: FollowUpType;
  title: string;
  contact: string;
  date: string;
  consultant: string;
  consultantId: string;
  propertyId: string | null;
  outcome: string | null;
  status: FollowUpStatus;
  probability: number;
  notes?: string | null;
  is_archived?: boolean;
  isOverdue?: boolean;
  createdAt?: string;
  updatedAt?: string;
};

type FollowUpCreatePayload = {
  title: string;
  type: FollowUpType;
  contact: string;
  date: string;
  propertyId: string | null;
  consultantId: string | null;
  notes: string;
};

type PropertyReportPayload = {
  property: { id: number; title: string; internalCode: string; neighborhood: string; status: string; consultantId: number };
  kpis: Record<string, any>;
  charts: Record<string, any>;
  warnings: string[];
  meta: Record<string, any>;
};

type Property = {
  id: string | number;
  internalCode?: string;
  title: string;
  type?: string;
  transactionType?: string;
  floor?: number;
  constructionYear?: number;
  fullAddress?: string;
  propertyStatus?: string;
  archived?: boolean;
  price?: number;
  area?: number;
  beds?: number;
  district?: string;
  districtId?: number | null;
  cityId?: number | null;
  cityName?: string | null;
  provinceId?: number | null;
  provinceName?: string | null;
  locationPath?: string | null;
  consultant?: string | number;
  consultantName?: string;
  consultantId?: string | number;
  consultantRole?: string | null;
  isShared?: boolean;
  date?: string;
  views?: number;
  listed?: boolean;
  roi?: number;
  gradient?: string;
  description?: string;
  images?: { id: string | number; url: string; alt?: string }[];
  pricePerSqm?: number | null;
  imagesCount?: number;
  daysOnMarket?: number | null;
  spatialDensityRatio?: number | null;
  priceDeviationIndex?: number | null;
  geoPrecisionFlag?: boolean;
  engagementHeatScore?: number;
  latitude?: number | null;
  longitude?: number | null;
};

type BadgeV = "default" | "success" | "warning" | "danger" | "info" | "purple" | "muted" | "teal";

type Listing = {
  id: string | number;
  title: string;
  description: string;
  status: "DRAFT" | "ACTIVE" | "PAUSED" | "EXPIRED" | "ARCHIVED";
  publish_channel: "WEBSITE" | "INSTAGRAM" | "TELEGRAM" | "OTHER";
  start_date: string | null;
  end_date: string | null;
  assigned_to: string | number | null;
  created_by: string | number;
  priority: number;
  is_featured: boolean;
  created_at: string;
  updated_at: string;
  property: string | number;
  property_detail?: {
    id: number;
    title: string;
    district: string;
    price: number;
    area: number;
    floor: number;
    internal_code: string;
    image_url?: string | null;
  };
  created_by_detail?: { id: number; username: string; name: string; email: string };
  assigned_to_detail?: { id: number; username: string; name: string; email: string };
  channels: string[];
  score: number;
  views: number;
  effectiveExposureDays?: number | null;
  delegationIndicator?: string;
  isBurnedListing?: boolean;
  generatedHighProbLeads?: number;
  contentRichnessScore?: number;
  engagementHeatScore?: number;
  dealType?: number | null;
  dealTypeName?: string | null;
  dealTypeDisplay?: string | null;
  salePrice?: string | number | null;
  deposit?: string | number | null;
  monthlyRent?: string | number | null;
};

interface NavSection {
  heading?: string;
  items: { label: string; icon: React.ReactNode; page?: Page; children?: { label: string; page: Page }[]; badge?: number }[];
}

type ActivityLogItem = {
  id: number;
  userId: number | null;
  userName: string;
  userAvatar: string;
  action: string;
  actionLabel: string;
  targetType: string;
  targetTypeLabel: string;
  targetId: number | null;
  description: string;
  createdAt: string;
};

type ConsultantRole = "AGENT";

type AddConsultantFormState = {
  firstName: string;
  lastName: string;
  username: string;
  email: string;
  phone: string;
  role: ConsultantRole;
  branch: string;
  password: string;
  profile_image: File | null;
};

type ConsultantOption = {
  id: string | number;
  name?: string;
  full_name?: string;
  role?: string;
  branch?: string;
  email?: string;
  phone?: string;
  mobile?: string;
  active?: boolean;
  is_active?: boolean;
  avatar?: string;
  profile_image?: string | null;
  imageUrl?: string | null;
  user?: {
    id?: string | number;
    username?: string;
    first_name?: string;
    last_name?: string;
    email?: string;
    role?: string;
  };
};

type ConsultantAnalyticsPayload = {
  consultant: { id: number; fullName: string; branch: string; userId: number };
  kpis: Record<string, any>;
  charts: {
    monthlyActivity?: { month: string; tasksCompleted: number; followups: number; listings: number }[];
    tasksByStatus?: { status: string; count: number }[];
    followupsByType?: { type: string; count: number; completedCount?: number; completionRate: number | null }[];
    listingsByChannel?: { channel: string; count: number }[];
    performanceProfile?: { metric: string; score: number }[];
    listingsByDealType?: { label: string; count: number }[];
    listingsByStatus?: { status: string; count: number }[];
    tasksByPriority?: { priority: string; count: number }[];
    followupsByStatus?: { status: string; count: number }[];
    propertiesByType?: { type: string; count: number }[];
    propertyLocations?: { id: number; title: string; lat: number; lng: number; status: string; area: number }[];
  };
};

interface PropertiesPageProps {
  navigate: (p: Page, paramId?: string | number) => void;
  role: Role;
  properties: Property[];
  loading: boolean;
  openPropertyDetail: (id: string) => void;
  openPropertyEdit: (id: string) => void;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
  onToggleShared?: (id: string) => Promise<boolean>;
  consultants: any[];
  districtsList?: string[];
  csrfToken?: string;
}

interface PropertyDetailProps {
  navigate: (p: Page, paramId?: string | number) => void;
  role: Role;
  property?: Property;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
  onUpdateStatus?: (id: string, status: string) => Promise<boolean>;
  onToggleShared?: (id: string) => Promise<boolean>;
  openPropertyEdit?: (id: string) => void;
  onDeleteImage?: (propertyId: string, imageId: string) => Promise<void>;
  onUploadImages?: (propertyId: string, files: File[]) => Promise<any>;
  onReorderImages?: (propertyId: string, order: { id: string | number; sort_order: number }[]) => Promise<void>;
}

export type {
  Role, Page, TaskHistoryEntry, ConsultantItem, FollowUpType, FollowUpStatus,
  FollowUp, FollowUpCreatePayload, BadgeV, PropertyReportPayload, Property,
  Listing, NavSection, ActivityLogItem, ConsultantRole, AddConsultantFormState,
  ConsultantOption, ConsultantAnalyticsPayload, PropertiesPageProps, PropertyDetailProps,
};
