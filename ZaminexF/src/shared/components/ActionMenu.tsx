import React, { useState, useCallback, useEffect, useRef } from "react";
import { cx } from "../lib/utils";
import { BadgeV } from "../lib/types";
import { ChevronLeft, ChevronRight, ChevronDown, Check, X, Archive, Trash2, Download, RefreshCw, Clock, Building2, Eye, Edit2, CheckCircle2, MoreVertical, MapPin, User, Lock, Key, Send, Loader2, Shield, Filter, Plus, CheckSquare, BellRing, LayoutDashboard, FileText, Users, Activity, Settings, LogOut } from "lucide-react";
import { Badge } from "./ui/Badge";
import { Btn } from "./ui/Btn";
import { Card } from "./ui/Card";
import { ProfileAvatar } from "./ui/ProfileAvatar";
import { Input } from "./ui/Input";
import { SelectField } from "./ui/SelectField";
import { KpiCard } from "./ui/KpiCard";
import { PageHeader } from "./ui/PageHeader";
import { EmptyState } from "./ui/EmptyState";
import { toast } from "../lib/utils";
import { createPortal } from "react-dom";
function ActionMenu({ actions }: { actions: { label: string; icon: React.ReactNode; onClick: () => void; danger?: boolean }[] }) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [coords, setCoords] = useState<{ top: number; left: number }>({ top: 0, left: 0 });

  const updatePosition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const menuWidth = 192;
    const menuHeight = actions.length * 38 + 8;

    let top = rect.bottom + 4;
    if (top + menuHeight > window.innerHeight - 8) {
      top = rect.top - menuHeight - 4;
    }

    let left = rect.right - menuWidth;
    if (left < 8) left = 8;

    setCoords({ top, left });
  }, [actions.length]);

  useEffect(() => {
    if (!open) return;
    updatePosition();
    const handleScroll = () => setOpen(false);
    const handleResize = () => setOpen(false);
    window.addEventListener("scroll", handleScroll, true);
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("scroll", handleScroll, true);
      window.removeEventListener("resize", handleResize);
    };
  }, [open, updatePosition]);

  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (
        triggerRef.current && !triggerRef.current.contains(e.target as Node) &&
        menuRef.current && !menuRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <>
      <button
        ref={triggerRef}
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
        className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-secondary transition-colors text-muted-foreground hover:text-foreground"
      >
        <MoreVertical size={14} />
      </button>
      {open && typeof document !== "undefined" && createPortal(
        <div
          ref={menuRef}
          style={{ position: "fixed", top: coords.top, left: coords.left, zIndex: 9999 }}
          className="w-48 bg-card rounded-xl border border-border shadow-lg py-1 overflow-hidden"
        >
          {actions.map((a) => (
            <button
              key={a.label}
              onClick={(e) => { e.stopPropagation(); a.onClick(); setOpen(false); }}
              className={cx(
                "w-full flex items-center gap-2.5 px-3 py-2.5 text-xs font-medium text-right transition-colors",
                a.danger ? "text-destructive hover:bg-red-50" : "text-foreground hover:bg-secondary"
              )}
            >
              <span className="flex-1 text-right">{a.label}</span>{a.icon}
            </button>
          ))}
        </div>,
        document.body
      )}
    </>
  );
}

// =============================================================================
//  Command Palette
// =============================================================================

export { ActionMenu };
