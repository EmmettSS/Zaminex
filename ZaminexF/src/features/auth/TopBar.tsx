import React, { useState, useEffect, useCallback, useRef } from "react";
import { cx } from "../../shared/lib/utils";
import { BadgeV } from "../../shared/lib/types";
import { LayoutDashboard, Building2, FileText, CheckSquare, BellRing, Calendar, Users, User, Activity, Settings, LogOut, Zap, Plus, ArrowUpRight, Lock, Mail, Search, Command, Bell } from "lucide-react";
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
import { Page, Role } from "../../shared/lib/types";
function TopBar({ userName, userImageUrl, role, onCmd, onNotif, notifOpen, unreadCount = 0 }: { userName: string; userImageUrl?: string | null; role: Role; onCmd: () => void; onNotif: () => void; notifOpen: boolean; unreadCount?: number }) {
  return (
    <header className="h-14 bg-white border-b border-border flex items-center gap-3 px-5 flex-shrink-0" style={{ boxShadow: "0 1px 0 rgba(0,0,0,0.05)" }}>
      <button onClick={onCmd} className="flex items-center gap-2 flex-1 max-w-xs text-sm text-muted-foreground bg-secondary hover:bg-muted rounded-xl px-3.5 py-2 transition-colors">
        <Search size={13} /><span className="flex-1 text-right">جستجو در صفحات…</span>
        <div className="flex items-center gap-0.5"><kbd className="text-xs bg-white border border-border rounded-md px-1.5 py-0.5"><Command size={9} /></kbd><kbd className="text-xs bg-white border border-border rounded-md px-1.5 py-0.5">K</kbd></div>
      </button>
      <div className="flex items-center gap-2 ml-auto">
        <div className="relative">
          <button onClick={onNotif} className="relative w-9 h-9 rounded-xl hover:bg-secondary flex items-center justify-center text-muted-foreground transition-colors">
            <Bell size={16} />
            {unreadCount > 0 && <span className="absolute top-1.5 left-1.5 w-2 h-2 rounded-full bg-primary" />}
          </button>
        </div>
        <div className="flex items-center gap-2 pr-2 border-r border-border h-9">
          <ProfileAvatar imageUrl={userImageUrl} initials={userName.split(" ").map((w) => w[0]).join("").slice(0, 2)} size="sm" />
          <div className="text-right">
            <p className="text-xs font-semibold leading-tight">{userName}</p>
            <p className="text-xs text-muted-foreground leading-none">{role === "admin" ? "مدیر ارشد" : "مشاور"}</p>
          </div>
        </div>
      </div>
    </header>
  );
}

// =============================================================================
//  Empty State / Page Header
// =============================================================================

export { TopBar };
