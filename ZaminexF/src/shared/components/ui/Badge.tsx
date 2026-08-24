import React from "react";
import { cx } from "../../lib/utils";
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, MessageSquare, Sparkles, GripVertical, MoreVertical, Building, History, Flame, Image } from "lucide-react";
import { BadgeV } from "../../lib/types";

function Badge({ label, variant = "default", dot }: { label: string; variant?: BadgeV; dot?: boolean }) {
  const s: Record<BadgeV, string> = {
    default: "bg-secondary text-foreground",
    success: "bg-emerald-50 text-emerald-700 border border-emerald-200",
    warning: "bg-amber-50 text-amber-700 border border-amber-200",
    danger: "bg-red-50 text-red-700 border border-red-200",
    info: "bg-blue-50 text-blue-700 border border-blue-200",
    purple: "bg-purple-50 text-purple-700 border border-purple-200",
    muted: "bg-muted text-muted-foreground",
    teal: "bg-emerald-50 text-emerald-600 border border-emerald-200",
  };
  const dc: Record<BadgeV, string> = { default: "bg-foreground", success: "bg-emerald-500", warning: "bg-amber-500", danger: "bg-red-500", info: "bg-blue-500", purple: "bg-purple-500", muted: "bg-muted-foreground", teal: "bg-emerald-500" };
  return (
    <span className={cx("inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium whitespace-nowrap", s[variant])}>
      {dot && <span className={cx("w-1.5 h-1.5 rounded-full flex-shrink-0", dc[variant])} />}
      {label}
    </span>
  );
}

// -----------------------------------------------------------------------------
//  Standard Persian real estate CRM translators
// -----------------------------------------------------------------------------
export const toPersianType = (type?: string | null): string => {
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

export const toPersianDeal = (deal?: string | null): string => {
  const map: Record<string, string> = {
    "Sale": "فروش", "SALE": "فروش", "sale": "فروش",
    "Rent": "اجاره", "RENT": "اجاره", "rent": "اجاره",
    "Off-Plan": "پیش‌فروش", "OFF_PLAN": "پیش‌فروش", "OFF-PLAN": "پیش‌فروش", "off-plan": "پیش‌فروش",
  };
  return map[String(deal || "").trim()] || deal || "—";
};

export const toPersianPropertyStatus = (st?: string | null): string => {
  const map: Record<string, string> = {
    "Available": "آماده واگذاری", "AVAILABLE": "آماده واگذاری", "available": "آماده واگذاری",
    "Reserved": "رزرو شده", "RESERVED": "رزرو شده", "reserved": "رزرو شده",
    "Sold": "فروخته‌/واگذارشده", "SOLD": "فروخته‌/واگذارشده", "sold": "فروخته‌/واگذارشده",
    "Rented": "اجاره‌داده‌شده", "RENTED": "اجاره‌داده‌شده", "rented": "اجاره‌داده‌شده",
    "Inactive": "بایگانی‌شده", "INACTIVE": "بایگانی‌شده", "inactive": "بایگانی‌شده",
  };
  return map[String(st || "").trim()] || st || "آماده واگذاری";
};

export const toPersianListingStatus = (st?: string | null): string => {
  const map: Record<string, string> = {
    "Draft": "پیش‌نویس", "DRAFT": "پیش‌نویس", "draft": "پیش‌نویس",
    "Pending Approval": "در انتظار تایید", "PENDING_APPROVAL": "در انتظار تایید", "PENDING APPROVAL": "در انتظار تایید",
    "Published": "منتشرشده (فعال)", "PUBLISHED": "منتشرشده (فعال)", "ACTIVE": "منتشرشده (فعال)", "active": "منتشرشده (فعال)",
    "Paused": "متوقف‌شده", "PAUSED": "متوقف‌شده", "paused": "متوقف‌شده",
    "Expired": "منقضی‌شده", "EXPIRED": "منقضی‌شده", "expired": "منقضی‌شده",
    "Inactive": "بایگانی‌شده", "INACTIVE": "بایگانی‌شده", "ARCHIVED": "بایگانی‌شده", "Archived": "بایگانی‌شده",
  };
  return map[String(st || "").trim()] || st || "—";
};

export const toPersianTaskType = (type?: string | null): string => {
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

export const toPersianTaskStatus = (st?: string | null): string => {
  const map: Record<string, string> = {
    "Pending": "در انتظار انجام", "PENDING": "در انتظار انجام", "pending": "در انتظار انجام",
    "In Progress": "در حال انجام", "IN_PROGRESS": "در حال انجام", "IN PROGRESS": "در حال انجام", "in_progress": "در حال انجام",
    "Completed": "تکمیل‌شده", "COMPLETED": "تکمیل‌شده", "completed": "تکمیل‌شده",
    "Cancelled": "لغوشده", "CANCELLED": "لغوشده", "cancelled": "لغوشده",
  };
  return map[String(st || "").trim()] || st || "—";
};

export const toPersianPriority = (p?: string | null): string => {
  const map: Record<string, string> = {
    "Low": "اولویت کم", "LOW": "اولویت کم", "low": "اولویت کم", "1": "اولویت کم",
    "Medium": "اولویت عادی", "MEDIUM": "اولویت عادی", "medium": "اولویت عادی", "2": "اولویت عادی",
    "High": "اولویت بالا", "HIGH": "اولویت بالا", "high": "اولویت بالا", "3": "اولویت بالا",
    "Urgent": "اولویت فوری", "URGENT": "اولویت فوری", "urgent": "اولویت فوری", "4": "اولویت فوری",
  };
  return map[String(p || "").trim()] || p || "عادی";
};

export const toPersianFollowupType = (type?: string | null): string => {
  const map: Record<string, string> = {
    "Call": "تماس تلفنی", "CALL": "تماس تلفنی", "call": "تماس تلفنی",
    "Meeting": "جلسه حضوری", "MEETING": "جلسه حضوری", "meeting": "جلسه حضوری",
    "Email": "ارسال پیام/ایمیل", "EMAIL": "ارسال پیام/ایمیل", "email": "ارسال پیام/ایمیل",
    "Site Visit": "بازدید میدانی ملک", "SITE VISIT": "بازدید میدانی ملک", "SITE_VISIT": "بازدید میدانی ملک", "site_visit": "بازدید میدانی ملک",
  };
  return map[String(type || "").trim()] || type || "—";
};

export const toPersianChannel = (ch?: string | null): string => {
  const map: Record<string, string> = {
    "WEBSITE": "پرتال رسمی زمینکس", "Website": "پرتال رسمی زمینکس", "وب‌سایت": "پرتال رسمی زمینکس",
    "INSTAGRAM": "صفحه اینستاگرام", "Instagram": "صفحه اینستاگرام", "اینستاگرام": "صفحه اینستاگرام",
    "TELEGRAM": "کانال تلگرام", "Telegram": "کانال تلگرام", "تلگرام": "کانال تلگرام",
    "OTHER": "سایر کانال‌های بازاریابی", "Other": "سایر کانال‌های بازاریابی", "سایر": "سایر کانال‌های بازاریابی",
  };
  return map[String(ch || "").trim()] || ch || "—";
};

function statusBadge(status: string) {
  const map: Record<string, { label: string; variant: BadgeV }> = {
    // Property statuses
    "Available": { label: "آماده واگذاری", variant: "success" },
    "AVAILABLE": { label: "آماده واگذاری", variant: "success" },
    "available": { label: "آماده واگذاری", variant: "success" },
    "Reserved": { label: "رزرو شده", variant: "info" },
    "RESERVED": { label: "رزرو شده", variant: "info" },
    "reserved": { label: "رزرو شده", variant: "info" },
    "Sold": { label: "فروخته‌/واگذارشده", variant: "muted" },
    "SOLD": { label: "فروخته‌/واگذارشده", variant: "muted" },
    "sold": { label: "فروخته‌/واگذارشده", variant: "muted" },
    "Rented": { label: "اجاره‌داده‌شده", variant: "purple" },
    "RENTED": { label: "اجاره‌داده‌شده", variant: "purple" },
    "rented": { label: "اجاره‌داده‌شده", variant: "purple" },
    "Inactive": { label: "بایگانی‌شده", variant: "muted" },
    "INACTIVE": { label: "بایگانی‌شده", variant: "muted" },
    "inactive": { label: "بایگانی‌شده", variant: "muted" },

    // Listing statuses
    "Published": { label: "منتشرشده (فعال)", variant: "success" },
    "PUBLISHED": { label: "منتشرشده (فعال)", variant: "success" },
    "ACTIVE": { label: "منتشرشده (فعال)", variant: "success" },
    "active": { label: "منتشرشده (فعال)", variant: "success" },
    "Pending Approval": { label: "در انتظار تایید", variant: "warning" },
    "PENDING APPROVAL": { label: "در انتظار تایید", variant: "warning" },
    "PENDING_APPROVAL": { label: "در انتظار تایید", variant: "warning" },
    "Draft": { label: "پیش‌نویس", variant: "muted" },
    "DRAFT": { label: "پیش‌نویس", variant: "muted" },
    "draft": { label: "پیش‌نویس", variant: "muted" },
    "Paused": { label: "متوقف‌شده", variant: "warning" },
    "PAUSED": { label: "متوقف‌شده", variant: "warning" },
    "paused": { label: "متوقف‌شده", variant: "warning" },
    "Expired": { label: "منقضی‌شده", variant: "danger" },
    "EXPIRED": { label: "منقضی‌شده", variant: "danger" },
    "expired": { label: "منقضی‌شده", variant: "danger" },
    "ARCHIVED": { label: "بایگانی‌شده", variant: "muted" },
    "Archived": { label: "بایگانی‌شده", variant: "muted" },

    // Task statuses
    "Pending": { label: "در انتظار انجام", variant: "muted" },
    "PENDING": { label: "در انتظار انجام", variant: "muted" },
    "In Progress": { label: "در حال انجام", variant: "info" },
    "IN_PROGRESS": { label: "در حال انجام", variant: "info" },
    "IN PROGRESS": { label: "در حال انجام", variant: "info" },
    "in_progress": { label: "در حال انجام", variant: "info" },
    "Completed": { label: "تکمیل‌شده", variant: "success" },
    "COMPLETED": { label: "تکمیل‌شده", variant: "success" },
    "completed": { label: "تکمیل‌شده", variant: "success" },
    "Cancelled": { label: "لغوشده", variant: "danger" },
    "CANCELLED": { label: "لغوشده", variant: "danger" },
    "cancelled": { label: "لغوشده", variant: "danger" },

    // Priorities
    "urgent": { label: "اولویت فوری", variant: "danger" },
    "URGENT": { label: "اولویت فوری", variant: "danger" },
    "high": { label: "اولویت بالا", variant: "warning" },
    "HIGH": { label: "اولویت بالا", variant: "warning" },
    "medium": { label: "اولویت عادی", variant: "info" },
    "MEDIUM": { label: "اولویت عادی", variant: "info" },
    "low": { label: "اولویت کم", variant: "muted" },
    "LOW": { label: "اولویت کم", variant: "muted" },

    // Follow up types & actions
    "Call": { label: "تماس تلفنی", variant: "info" },
    "CALL": { label: "تماس تلفنی", variant: "info" },
    "call": { label: "تماس تلفنی", variant: "info" },
    "Meeting": { label: "جلسه حضوری", variant: "purple" },
    "MEETING": { label: "جلسه حضوری", variant: "purple" },
    "meeting": { label: "جلسه حضوری", variant: "purple" },
    "Email": { label: "ارسال پیام/ایمیل", variant: "muted" },
    "EMAIL": { label: "ارسال پیام/ایمیل", variant: "muted" },
    "email": { label: "ارسال پیام/ایمیل", variant: "muted" },
    "Site Visit": { label: "بازدید میدانی ملک", variant: "teal" },
    "SITE VISIT": { label: "بازدید میدانی ملک", variant: "teal" },
    "SITE_VISIT": { label: "بازدید میدانی ملک", variant: "teal" },
    "scheduled": { label: "برنامه‌ریزی‌شده", variant: "purple" },
    "SCHEDULED": { label: "برنامه‌ریزی‌شده", variant: "purple" },
    "update": { label: "بروزرسانی", variant: "info" },
    "create": { label: "ایجاد", variant: "success" },
    "submit": { label: "ارسال", variant: "purple" },
    "complete": { label: "تکمیل", variant: "success" },
    "export": { label: "خروجی", variant: "muted" },
    "archive": { label: "بایگانی", variant: "warning" },
    "system": { label: "سیستمی", variant: "muted" },
  };
  const normalized = status ? status.charAt(0).toUpperCase() + status.slice(1).toLowerCase() : status;
  const cfg = map[status] ?? map[normalized] ?? { label: status, variant: "default" as BadgeV };
  return <Badge label={cfg.label} variant={cfg.variant} dot />;
}

export { Badge };
