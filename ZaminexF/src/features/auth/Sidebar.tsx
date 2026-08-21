import React, { useState, useEffect, useCallback, useRef } from "react";
import { cx } from "../../shared/lib/utils";
import { BadgeV } from "../../shared/lib/types";
import { LayoutDashboard, MapPin, SlidersHorizontal, Building2, FileText, CheckSquare, BellRing, Calendar, Users, User, Activity, Settings, LogOut, Zap, Plus, ArrowUpRight, Lock, Mail, Search, Command, ChevronLeft, ChevronRight, ChevronDown } from "lucide-react";
import { Badge } from "../../shared/components/ui/Badge";
import { Btn } from "../../shared/components/ui/Btn";
import { Input } from "../../shared/components/ui/Input";
import { Card } from "../../shared/components/ui/Card";
import { ProfileAvatar } from "../../shared/components/ui/ProfileAvatar";
import { PageHeader } from "../../shared/components/ui/PageHeader";
import { EmptyState } from "../../shared/components/ui/EmptyState";
import { ConfirmModal } from "../../shared/components/ConfirmModal";
import { toast } from "../../shared/lib/utils";
import { PasswordResetModal } from "../../shared/components/PasswordResetModal";
import { Page, Role, NavSection } from "../../shared/lib/types";
function Sidebar({ role, page, navigate, collapsed, setCollapsed, userName, userImageUrl, onLogout }: {
  role: Role; page: Page; navigate: (p: Page) => void; collapsed: boolean; setCollapsed: (v: boolean) => void; userName: string; userImageUrl?: string | null; onLogout: () => void;
}) {
  const adminSections: NavSection[] = [
    { items: [{ label: "داشبورد", icon: <LayoutDashboard size={16} />, page: "admin-dashboard" }, { label: "املاک", icon: <Building2 size={16} />, children: [{ label: "همه املاک", page: "properties" }, { label: "افزودن ملک", page: "add-property" }] }, { label: "آگهی‌ها", icon: <FileText size={16} />, children: [{ label: "همه آگهی‌ها", page: "listings" }, { label: "ساخت آگهی", page: "create-listing" }] }] },
    { heading: "عملیات", items: [{ label: "وظایف", icon: <CheckSquare size={16} />, children: [{ label: "تخته کانبان", page: "tasks-kanban" }, { label: "افزودن وظیفه", page: "create-task" }] }, { label: "پیگیری‌ها", icon: <BellRing size={16} />, children: [{ label: "فهرست", page: "follow-ups" }, { label: "ایجاد", page: "create-followup" }] }, { label: "تقویم", icon: <Calendar size={16} />, page: "tasks-calendar" }] },
    { heading: "افراد", items: [{ label: "مشاوران", icon: <Users size={16} />, children: [{ label: "فهرست", page: "consultants" }, { label: "افزودن مشاور", page: "add-consultant" }] }] },
    { heading: "هوش کسب‌وکار", items: [{ label: "گزارش فعالیت", icon: <Activity size={16} />, page: "activity" }] },
    { heading: "اطلاعات پایه", items: [{ label: "مدیریت مناطق", icon: <MapPin size={16} />, page: "manage-districts" }, { label: "مدیریت ویژگی‌ها", icon: <SlidersHorizontal size={16} />, page: "manage-attributes" }] },
    { heading: "پروفایل", items: [{ label: "پروفایل من", icon: <User size={16} />, children: [{ label: "نمای کلی", page: "my-profile" }, { label: "ویرایش پروفایل", page: "my-profile-edit" }, { label: "امنیت", page: "my-profile-security" }] }] },
  ];
  const consultantSections: NavSection[] = [
    { items: [{ label: "داشبورد", icon: <LayoutDashboard size={16} />, page: "consultant-dashboard" }, { label: "املاک من", icon: <Building2 size={16} />, children: [{ label: "همه املاک", page: "my-properties" }, { label: "افزودن", page: "add-property" }] }, { label: "آگهی‌های من", icon: <FileText size={16} />, page: "my-listings" }] },
    { heading: "عملیات", items: [{ label: "وظایف من", icon: <CheckSquare size={16} />, page: "my-tasks" }, { label: "پیگیری‌های من", icon: <BellRing size={16} />, children: [{ label: "فهرست", page: "my-followups" }, { label: "ایجاد", page: "create-followup" }] }] },
    { heading: "پروفایل", items: [{ label: "پروفایل من", icon: <User size={16} />, children: [{ label: "نمای کلی", page: "my-profile" }, { label: "ویرایش پروفایل", page: "my-profile-edit" }, { label: "امنیت", page: "my-profile-security" }] }] },
  ];
  const sections = role === "admin" ? adminSections : consultantSections;
  const [expanded, setExpanded] = useState<string[]>(["املاک", "وظایف", "گزارش‌ها"]);
  const toggle = (l: string) => setExpanded((p) => p.includes(l) ? p.filter((x) => x !== l) : [...p, l]);
  const isActive = (p: Page) => page === p;
  const hasActive = (item: { children?: { page: Page }[] }) => item.children?.some((c) => isActive(c.page));

  return (
    <aside className={cx("flex flex-col h-full bg-sidebar transition-all duration-200 flex-shrink-0", collapsed ? "w-16" : "w-56")}>
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-sidebar-border h-14">
        <div className="w-7 h-7 bg-primary rounded-lg flex items-center justify-center flex-shrink-0"><Zap size={14} className="text-white" /></div>
        {!collapsed && <div className="flex-1 min-w-0"><span className="text-white font-bold text-sm tracking-tight">Zaminex</span><p className="text-white/35 text-xs leading-none">سیستم‌عامل املاک</p></div>}
        <button onClick={() => setCollapsed(!collapsed)} className="mr-auto text-white/30 hover:text-white transition-colors">{collapsed ? <ChevronLeft size={13} /> : <ChevronRight size={13} />}</button>
      </div>
      <nav className="flex-1 overflow-y-auto py-3 px-2 flex flex-col gap-0.5" style={{ scrollbarWidth: "none" }}>
        {sections.map((section) => (
          <div key={section.heading || "main"} className="mb-1">
            {!collapsed && section.heading && <p className="text-white/25 text-xs font-semibold tracking-widest px-2.5 py-2 mt-1">{section.heading}</p>}
            {section.items.map((item) => {
              const active = item.page ? isActive(item.page) : hasActive(item);
              const open = expanded.includes(item.label);
              return (
                <div key={item.label}>
                  <button onClick={() => item.page ? navigate(item.page) : toggle(item.label)}
                    className={cx("w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-right transition-all text-sm", active ? "bg-white/10 text-white" : "text-white/55 hover:bg-white/5 hover:text-white/90")}
                    title={collapsed ? item.label : undefined}>
                    <span className="flex-shrink-0">{item.icon}</span>
                    {!collapsed && (<><span className="flex-1 font-medium text-right">{item.label}</span>{item.badge && !open && <span className="text-xs bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded-full">{item.badge}</span>}{item.children && <span className="text-white/30">{open ? <ChevronDown size={12} /> : <ChevronLeft size={12} />}</span>}</>)}
                  </button>
                  {!collapsed && item.children && open && (
                    <div className="ml-5 mt-0.5 flex flex-col gap-0.5 border-l border-white/10 pl-3">
                      {item.children.map((c) => <button key={c.page + c.label} onClick={() => navigate(c.page)} className={cx("text-right px-2 py-1.5 rounded-lg text-xs font-medium transition-colors", isActive(c.page) ? "text-white bg-white/10" : "text-white/45 hover:text-white hover:bg-white/5")}>{c.label}</button>)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="p-3 border-t border-sidebar-border space-y-1">
        <button onClick={() => navigate("settings-workspace")} className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-white/55 hover:bg-white/5 hover:text-white/90 transition-colors text-sm"><Settings size={15} />{!collapsed && <span className="font-medium">تنظیمات</span>}</button>
        <button onClick={onLogout} className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-white/55 hover:bg-white/5 hover:text-white/90 transition-colors text-sm"><LogOut size={15} />{!collapsed && <span className="font-medium">خروج</span>}</button>
        {!collapsed && (
          <div className="flex items-center gap-2.5 px-2.5 pt-2 mt-1 border-t border-sidebar-border">
            <ProfileAvatar imageUrl={userImageUrl} initials={userName.split(" ").map((w) => w[0]).join("").slice(0, 2)} size="sm" />
            <div className="flex-1 min-w-0"><p className="text-xs font-semibold text-white truncate">{userName}</p><p className="text-xs text-white/35">{role === "admin" ? "مدیر ارشد" : "مشاور"}</p></div>
          </div>
        )}
      </div>
    </aside>
  );
}

// =============================================================================
//  Top Bar
// =============================================================================

export { Sidebar };
