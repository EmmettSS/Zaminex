import type { Page, Role } from "./types";

/** A destination the top-bar page search can open. Mirrors the sidebar + settings tabs. */
export type NavPageItem = {
  page: Page;
  label: string;
  section: string;
  keywords?: string;
};

const ADMIN_PAGES: NavPageItem[] = [
  { page: "admin-dashboard", label: "داشبورد", section: "ناوبری" },
  { page: "properties", label: "همه املاک", section: "املاک", keywords: "املاک" },
  { page: "add-property", label: "افزودن ملک", section: "املاک" },
  { page: "listings", label: "همه آگهی‌ها", section: "آگهی‌ها", keywords: "آگهی" },
  { page: "create-listing", label: "ساخت آگهی", section: "آگهی‌ها" },
  { page: "tasks-kanban", label: "تخته کانبان", section: "وظایف", keywords: "وظایف کانبان" },
  { page: "create-task", label: "افزودن وظیفه", section: "وظایف" },
  { page: "follow-ups", label: "فهرست پیگیری‌ها", section: "پیگیری‌ها", keywords: "پیگیری" },
  { page: "create-followup", label: "ایجاد پیگیری", section: "پیگیری‌ها" },
  { page: "tasks-calendar", label: "تقویم", section: "عملیات" },
  { page: "consultants", label: "فهرست مشاوران", section: "مشاوران", keywords: "مشاور" },
  { page: "add-consultant", label: "افزودن مشاور", section: "مشاوران" },
  { page: "activity", label: "گزارش فعالیت", section: "هوش کسب‌وکار" },
  { page: "manage-districts", label: "مدیریت مناطق", section: "اطلاعات پایه", keywords: "محله شهر استان" },
  { page: "manage-attributes", label: "مدیریت ویژگی‌ها", section: "اطلاعات پایه" },
  { page: "my-profile", label: "پروفایل من", section: "پروفایل", keywords: "نمای کلی" },
  { page: "my-profile-edit", label: "ویرایش پروفایل", section: "پروفایل" },
  { page: "my-profile-security", label: "امنیت", section: "پروفایل" },
  { page: "settings-workspace", label: "تنظیمات فضای کاری", section: "سیستم", keywords: "تنظیمات" },
  { page: "settings-permissions", label: "دسترسی‌ها", section: "سیستم", keywords: "تنظیمات" },
];

const CONSULTANT_PAGES: NavPageItem[] = [
  { page: "consultant-dashboard", label: "داشبورد", section: "ناوبری" },
  { page: "my-properties", label: "املاک من", section: "املاک", keywords: "همه املاک" },
  { page: "add-property", label: "افزودن ملک", section: "املاک" },
  { page: "my-listings", label: "آگهی‌های من", section: "آگهی‌ها" },
  { page: "my-tasks", label: "وظایف من", section: "عملیات", keywords: "وظایف" },
  { page: "my-followups", label: "پیگیری‌های من", section: "پیگیری‌ها", keywords: "فهرست پیگیری" },
  { page: "create-followup", label: "ایجاد پیگیری", section: "پیگیری‌ها" },
  { page: "my-profile", label: "پروفایل من", section: "پروفایل", keywords: "نمای کلی" },
  { page: "my-profile-edit", label: "ویرایش پروفایل", section: "پروفایل" },
  { page: "my-profile-security", label: "امنیت", section: "پروفایل" },
  { page: "settings-workspace", label: "تنظیمات فضای کاری", section: "سیستم", keywords: "تنظیمات" },
  { page: "settings-permissions", label: "دسترسی‌ها", section: "سیستم", keywords: "تنظیمات" },
];

/** Pages the current role can open from the top-bar search. */
export function getRoleNavPages(role?: Role): NavPageItem[] {
  return role === "admin" ? ADMIN_PAGES : CONSULTANT_PAGES;
}
