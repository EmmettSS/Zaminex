import React from "react";
import { Badge } from "./Badge";
import { BadgeV } from "../../lib/types";

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

export { statusBadge };
