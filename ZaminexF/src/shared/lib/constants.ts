// =============================================================================
//  Constants (extracted exactly from App.tsx)
// =============================================================================

const PAGE_SIZE = 20;
const TRANSACTION_TYPES = ["Sale", "Rent", "Off-Plan"];
const PROPERTY_STATUSES = ["Available", "Reserved", "Sold", "Inactive"];

const PROPERTY_STATUS_TO_BACKEND: Record<string, string> = {
  Available: "AVAILABLE",
  Reserved: "RESERVED",
  Sold: "SOLD",
  Inactive: "INACTIVE",
};

const LISTING_STATUSES = ["Draft", "Pending Approval", "Published", "Expired", "Inactive"];
const TASK_TYPES = ["Viewing", "Document", "Negotiation", "Follow-Up", "Administrative", "Site Visit", "Contract", "Inspection"];
const TASK_STATUSES = ["PENDING", "IN_PROGRESS", "COMPLETED", "CANCELLED"];
const TASK_PRIORITIES = ["Low", "Medium", "High", "Urgent"];

const DASH_AREA = [
  { month: "تیر", revenue: 4.2, forecast: 4.8 }, { month: "مرداد", revenue: 5.1, forecast: 5.0 },
  { month: "شهریور", revenue: 3.8, forecast: 5.2 }, { month: "مهر", revenue: 6.9, forecast: 6.0 },
  { month: "آبان", revenue: 8.2, forecast: 7.5 }, { month: "آذر", revenue: 11.4, forecast: 10.0 },
];
const CHANNEL_PIE = [{ name: "پرتال Property Finder", value: 48 }, { name: "پرتال Bayut", value: 35 }, { name: "پرتال Dubizzle", value: 17 }];
const PIE_COLORS = ["#0BB68A", "#3B82F6", "#F59E0B"];
const CHART_COLORS = ["#0BB68A", "#3B82F6", "#F59E0B", "#8B5CF6", "#EF4444", "#EC4899", "#14B8A6", "#F97316"];
const DELEGATION_COLORS = { selfManaged: "#0BB68A", delegated: "#3B82F6", unassigned: "#94A3B8" };

const SKILL_RADAR = [
  { skill: "مذاکره و نشست", value: 88 }, { skill: "پیگیری مستمر", value: 72 }, { skill: "فایل‌یابی و آگهی", value: 91 },
  { skill: "مدیریت کاریز", value: 65 }, { skill: "ارتباط با مشتری", value: 84 }, { skill: "بستن معامله", value: 79 },
];

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

const PERSIAN_MONTHS = [
  "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
];

const WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"];

const FOLLOWUP_TYPE_LABELS: Record<string, string> = {
  Call: "تماس تلفنی",
  Meeting: "جلسه حضوری",
  Email: "ارسال پیام/ایمیل",
  "Site Visit": "بازدید میدانی ملک",
};

export {
  PAGE_SIZE,
  TRANSACTION_TYPES,
  PROPERTY_STATUSES,
  PROPERTY_STATUS_TO_BACKEND,
  LISTING_STATUSES,
  TASK_TYPES,
  TASK_STATUSES,
  TASK_PRIORITIES,
  DASH_AREA,
  CHANNEL_PIE,
  PIE_COLORS,
  SKILL_RADAR,
  CHART_COLORS,
  DELEGATION_COLORS,
  PAGE_SIZE_OPTIONS,
  PERSIAN_MONTHS,
  WEEKDAYS,
  FOLLOWUP_TYPE_LABELS,
};
