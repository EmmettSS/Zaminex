// =============================================================================
//  Utility helpers (extracted exactly from App.tsx)
// =============================================================================

const fmtShort = (n: number) =>
  n >= 1_000_000_000
    ? `${(n / 1_000_000_000).toLocaleString("fa-IR", { maximumFractionDigits: 1 })} میلیارد تومان`
    : n >= 1_000_000
      ? `${(n / 1_000_000).toLocaleString("fa-IR", { maximumFractionDigits: 0 })} میلیون تومان`
      : `${n.toLocaleString("fa-IR")} تومان`;

const cx = (...args: (string | undefined | false | null)[]) => args.filter(Boolean).join(" ");

const requiredFieldMsg = (label: string) => `فیلد «${label}» نمی تواند خالی بماند.`;

const propertyStatusToUI = (status?: string | null): string => {
  const upper = String(status || "").toUpperCase();
  const found = Object.keys({
    Available: "AVAILABLE",
    Reserved: "RESERVED",
    Sold: "SOLD",
    Inactive: "INACTIVE",
  }).find(
    (k: string) => (k === "Available" ? "AVAILABLE" : k === "Reserved" ? "RESERVED" : k === "Sold" ? "SOLD" : k === "Inactive" ? "INACTIVE" : "") === upper
  );
  return found || "Available";
};

// Standard Persian real estate CRM translators
const toPersianType = (type?: string | null): string => {
  const map: Record<string, string> = {
    "Apartment": "آپارتمان", "APARTMENT": "آپارتمان", "apartment": "آپارتمان",
    "Villa": "ویلا", "VILLA": "ویلا", "villa": "ویلا",
    "Townhouse": "خانه ویلایی", "TOWNHOUSE": "خانه ویلایی", "townhouse": "خانه ویلایی",
    "Studio": "استودیو", "STUDIO": "استودیو", "studio": "استودیو",
    "Penthouse": "پنت‌هاوس", "PENTHOUSE": "پنت‌هاوس", "penthouse": "پنت‌هاوس",
    "Commercial": "تجاری/اداری", "COMMERCIAL": "تجاری/اداری", "commercial": "تجاری/اداری",
    "Office": "دفتر کار", "OFFICE": "دفتر کار", "office": "دفتر کار",
    "Shop": "مغازه", "SHOP": "مغازه", "shop": "مغازه",
    "Land": "زمین", "LAND": "زمین", "land": "زمین",
    "Other": "سایر", "OTHER": "سایر", "other": "سایر",
  };
  return map[String(type || "").trim()] || type || "—";
};

const toPersianDeal = (deal?: string | null): string => {
  const map: Record<string, string> = {
    "Sale": "فروش", "SALE": "فروش", "sale": "فروش",
    "Rent": "اجاره", "RENT": "اجاره", "rent": "اجاره",
    "Off-Plan": "پیش‌فروش", "OFF_PLAN": "پیش‌فروش", "OFF-PLAN": "پیش‌فروش", "off-plan": "پیش‌فروش",
  };
  return map[String(deal || "").trim()] || deal || "—";
};

const toPersianPropertyStatus = (st?: string | null): string => {
  const map: Record<string, string> = {
    "Available": "آماده واگذاری", "AVAILABLE": "آماده واگذاری", "available": "آماده واگذاری",
    "Reserved": "رزرو شده", "RESERVED": "رزرو شده", "reserved": "رزرو شده",
    "Sold": "فروخته‌/واگذارشده", "SOLD": "فروخته‌/واگذارشده", "sold": "فروخته‌/واگذارشده",
    "Rented": "اجاره‌داده‌شده", "RENTED": "اجاره‌داده‌شده", "rented": "اجاره‌داده‌شده",
    "Inactive": "بایگانی‌شده", "INACTIVE": "بایگانی‌شده", "inactive": "بایگانی‌شده",
  };
  return map[String(st || "").trim()] || st || "آماده واگذاری";
};

const toPersianListingStatus = (st?: string | null): string => {
  const map: Record<string, string> = {
    "Draft": "پیش‌نویس", "DRAFT": "پیش‌نویس", "draft": "پیش‌نویس",
    "Pending Approval": "در انتظار تایید", "PENDING_APPROVAL": "در انتظار تایید", "PENDING APPROVAL": "در انتظار تایید",
    "Published": "منتشرشده (فعال)", "PUBLISHED": "منتشرشده (فعال)", "ACTIVE": "منتشرشده (فعال)", "active": "منتشرشده (فعال)",
    "Paused": "متوقف‌شده", "PAUSED": "متوقف‌شده", "paused": "متوقف‌شده",
    "Sold": "فروخته‌شده", "SOLD": "فروخته‌شده", "sold": "فروخته‌شده",
    "Expired": "منقضی‌شده", "EXPIRED": "منقضی‌شده", "expired": "منقضی‌شده",
    "Inactive": "بایگانی‌شده", "INACTIVE": "بایگانی‌شده", "ARCHIVED": "بایگانی‌شده", "Archived": "بایگانی‌شده",
  };
  return map[String(st || "").trim()] || st || "—";
};

const toPersianTaskType = (type?: string | null): string => {
  const map: Record<string, string> = {
    "Viewing": "بازدید ملک", "VIEWING": "بازدید ملک", "viewing": "بازدید ملک",
    "Document": "بررسی مدارک", "DOCUMENT": "بررسی مدارک", "document": "بررسی مدارک",
    "Negotiation": "مذاکره و نشست", "NEGOTIATION": "مذاکره و نشست", "negotiation": "مذاکره و نشست",
    "Follow-Up": "پیگیری مستمر", "FOLLOW_UP": "پیگیری مستمر", "Follow-up": "پیگیری مستمر", "follow_up": "پیگیری مستمر",
    "Administrative": "امور اداری و دفتری", "ADMINISTRATIVE": "امور اداری و دفتری", "administrative": "امور اداری و دفتری",
    "Site Visit": "کارشناسی میدانی", "SITE_VISIT": "کارشناسی میدانی", "site_visit": "کارشناسی میدانی", "Site visit": "کارشناسی میدانی",
    "Contract": "عقد قرارداد", "CONTRACT": "عقد قرارداد", "contract": "عقد قرارداد",
    "Inspection": "بازرسی فنی", "INSPECTION": "بازرسی فنی", "inspection": "بازرسی فنی",
  };
  return map[String(type || "").trim()] || type || "—";
};

const toPersianTaskStatus = (st?: string | null): string => {
  const map: Record<string, string> = {
    "Pending": "در انتظار انجام", "PENDING": "در انتظار انجام", "pending": "در انتظار انجام",
    "In Progress": "در حال انجام", "IN_PROGRESS": "در حال انجام", "IN PROGRESS": "در حال انجام", "in_progress": "در حال انجام",
    "Completed": "تکمیل‌شده", "COMPLETED": "تکمیل‌شده", "completed": "تکمیل‌شده",
    "Cancelled": "لغوشده", "CANCELLED": "لغوشده", "cancelled": "لغوشده",
  };
  return map[String(st || "").trim()] || st || "—";
};

const toPersianPriority = (p?: string | null): string => {
  const map: Record<string, string> = {
    "Low": "اولویت کم", "LOW": "اولویت کم", "low": "اولویت کم", "1": "اولویت کم",
    "Medium": "اولویت عادی", "MEDIUM": "اولویت عادی", "medium": "اولویت عادی", "2": "اولویت عادی",
    "High": "اولویت بالا", "HIGH": "اولویت بالا", "high": "اولویت بالا", "3": "اولویت بالا",
    "Urgent": "اولویت فوری", "URGENT": "اولویت فوری", "urgent": "اولویت فوری", "4": "اولویت فوری",
  };
  return map[String(p || "").trim()] || p || "عادی";
};

const toPersianFollowupType = (type?: string | null): string => {
  const map: Record<string, string> = {
    "Call": "تماس تلفنی", "CALL": "تماس تلفنی", "call": "تماس تلفنی",
    "Meeting": "جلسه حضوری", "MEETING": "جلسه حضوری", "meeting": "جلسه حضوری",
    "Email": "ارسال پیام/ایمیل", "EMAIL": "ارسال پیام/ایمیل", "email": "ارسال پیام/ایمیل",
    "Site Visit": "بازدید میدانی ملک", "SITE VISIT": "بازدید میدانی ملک", "SITE_VISIT": "بازدید میدانی ملک", "site_visit": "بازدید میدانی ملک",
  };
  return map[String(type || "").trim()] || type || "—";
};

const formatPriceDeviation = (idx?: number | null) => {
  if (idx == null || Number.isNaN(idx)) return "—";
  const pct = idx * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}٪ نسبت به میانگین محله`;
};

const delegationLabel = (code?: string | null) => {
  const map: Record<string, string> = {
    DELEGATED: "تفویض‌شده (تیمی)",
    SELF_MANAGED: "مدیریت شخصی",
    UNASSIGNED: "هنوز واگذار نشده",
  };
  return map[code || ""] || "—";
};

const toPersianChannel = (ch?: string | null): string => {
  const map: Record<string, string> = {
    "WEBSITE": "پرتال رسمی زمینکس", "Website": "پرتال رسمی زمینکس", "وب‌سایت": "پرتال رسمی زمینکس",
    "INSTAGRAM": "صفحه اینستاگرام", "Instagram": "صفحه اینستاگرام", "اینستاگرام": "صفحه اینستاگرام",
    "TELEGRAM": "کانال تلگرام", "Telegram": "کانال تلگرام", "تلگرام": "کانال تلگرام",
    "OTHER": "سایر کانال‌های بازاریابی", "Other": "سایر کانال‌های بازاریابی", "سایر": "سایر کانال‌های بازاریابی",
  };
  return map[String(ch || "").trim()] || ch || "—";
};

const consultantLabel = (p: { consultantName?: string; consultant?: string | number }): string => {
  const name = p.consultantName || (typeof p.consultant === "string" ? p.consultant : "");
  return name || "نامشخص";
};

const isPastDue = (value?: string | null): boolean => {
  if (!value) return false;
  const raw = String(value).trim();
  if (!raw) return false;
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    const today = new Date();
    const ymd = [
      today.getFullYear(),
      String(today.getMonth() + 1).padStart(2, "0"),
      String(today.getDate()).padStart(2, "0"),
    ].join("-");
    return raw < ymd;
  }
  const ts = new Date(raw).getTime();
  return Number.isFinite(ts) && ts < Date.now();
};

const isTaskOverdue = (task: { isOverdue?: boolean; status?: string; due?: string; due_date?: string }): boolean => {
  if (task.isOverdue === true) return true;
  if (task.isOverdue === false) return false;
  const status = String(task.status || "").toUpperCase();
  if (status === "COMPLETED" || status === "CANCELLED") return false;
  return isPastDue(task.due || task.due_date);
};

const isFollowUpOverdue = (followup: { isOverdue?: boolean; status?: string; date?: string; is_archived?: boolean }): boolean => {
  if (followup.isOverdue === true) return true;
  if (followup.isOverdue === false) return false;
  if (followup.is_archived) return false;
  if (String(followup.status || "").toLowerCase() !== "scheduled") return false;
  return isPastDue(followup.date);
};

export {
  fmtShort,
  cx,
  consultantLabel,
  isPastDue,
  isTaskOverdue,
  isFollowUpOverdue,
  requiredFieldMsg,
  propertyStatusToUI,
  toPersianType,
  toPersianDeal,
  toPersianPropertyStatus,
  toPersianListingStatus,
  toPersianTaskType,
  toPersianTaskStatus,
  toPersianPriority,
  toPersianFollowupType,
  toPersianChannel,
  formatPriceDeviation,
  delegationLabel,
};

export { fuzzyMatch, fuzzyFilter } from "./fuzzySearch";

export interface ToastItem {
  id: string;
  message: string;
  type: "success" | "error" | "info" | "warning";
}

type ToastListener = (toast: Omit<ToastItem, "id">) => void;
let toastListener: ToastListener | null = null;

export function subscribeToToasts(listener: ToastListener) {
  toastListener = listener;
  return () => {
    if (toastListener === listener) toastListener = null;
  };
}

export function toast(item: Omit<ToastItem, "id">) {
  toastListener?.(item);
}
