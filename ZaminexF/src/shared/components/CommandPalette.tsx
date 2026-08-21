import React, { useState, useEffect, useRef, useMemo } from "react";
import { fuzzyFilter } from "../lib/fuzzySearch";
import { getRoleNavPages } from "../lib/navPages";
import { Page, Role } from "../lib/types";
import { Building2, FileText, Users, Activity, Settings, Columns, BellRing, LayoutDashboard, Search, User, CheckSquare, Calendar, MapPin, SlidersHorizontal, Plus, Shield } from "lucide-react";
import { Card } from "./ui/Card";

function pageIcon(page: Page) {
  switch (page) {
    case "admin-dashboard":
    case "consultant-dashboard":
      return <LayoutDashboard size={14} />;
    case "properties":
    case "my-properties":
      return <Building2 size={14} />;
    case "add-property":
      return <Plus size={14} />;
    case "listings":
    case "my-listings":
    case "create-listing":
      return <FileText size={14} />;
    case "tasks-kanban":
      return <Columns size={14} />;
    case "create-task":
    case "my-tasks":
      return <CheckSquare size={14} />;
    case "tasks-calendar":
      return <Calendar size={14} />;
    case "follow-ups":
    case "my-followups":
    case "create-followup":
      return <BellRing size={14} />;
    case "consultants":
    case "add-consultant":
      return <Users size={14} />;
    case "activity":
      return <Activity size={14} />;
    case "manage-districts":
      return <MapPin size={14} />;
    case "manage-attributes":
      return <SlidersHorizontal size={14} />;
    case "my-profile":
    case "my-profile-edit":
    case "my-profile-security":
      return <User size={14} />;
    case "settings-permissions":
      return <Shield size={14} />;
    case "settings-workspace":
    default:
      return <Settings size={14} />;
  }
}

function CommandPalette({ open, onClose, navigate, role }: { open: boolean; onClose: () => void; navigate: (p: Page) => void; role?: Role }) {
  const [q, setQ] = useState("");
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQ("");
      setTimeout(() => ref.current?.focus(), 50);
    }
  }, [open]);

  // Handle ESC key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  const navItems = useMemo(() => getRoleNavPages(role), [role]);
  const results = useMemo(
    () => fuzzyFilter(navItems, q, (item) => `${item.label} ${item.section} ${item.keywords || ""}`),
    [navItems, q]
  );

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <Card className="w-full max-w-lg shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-border">
          <Search size={16} className="text-muted-foreground" />
          <input
            ref={ref}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="جستجو در صفحات…"
            className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none"
          />
          <kbd className="text-xs text-muted-foreground bg-secondary px-2 py-1 rounded-lg border border-border">ESC</kbd>
        </div>
        <div className="py-2 max-h-80 overflow-y-auto">
          {results.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">نتیجه‌ای یافت نشد</p>
          ) : (
            results.map((r) => (
              <button
                key={r.page}
                onClick={() => {
                  navigate(r.page);
                  onClose();
                }}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-secondary transition-colors text-right"
              >
                <span className="w-7 h-7 rounded-lg bg-secondary flex items-center justify-center text-muted-foreground flex-shrink-0">
                  {pageIcon(r.page)}
                </span>
                <span className="flex-1 text-right">{r.label}</span>
                <span className="text-xs text-muted-foreground">{r.section}</span>
              </button>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}

export { CommandPalette };
