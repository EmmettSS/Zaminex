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
import { apiFetch } from "../lib/apiClient";
function NotifDrawer({ open, onClose, notifications = [], csrfToken }: { open: boolean; onClose: () => void; notifications?: any[]; csrfToken?: string }) {
  const handleMarkRead = async (notifId: number) => {
    try {
      await apiFetch(`/common/api/notifications/${notifId}/read/`, { method: "POST" }, csrfToken);
    } catch (err) {
      console.error("Error marking notification as read:", err);
    }
  };

  if (!open) return null;
  
  const cm: Record<string, string> = { 
    password_reset_request: "bg-amber-100 text-amber-600", 
    password_changed: "bg-red-100 text-red-600",
    task_assigned: "bg-blue-100 text-blue-600", 
    task_status_changed: "bg-blue-100 text-blue-600",
    followup_created: "bg-emerald-100 text-emerald-600",
    property_assigned: "bg-purple-100 text-purple-600",
    listing_approved: "bg-emerald-100 text-emerald-600",
    listing_rejected: "bg-red-100 text-red-600",
  };
  
  const getIcon = (type: string) => {
    switch(type) {
      case "password_reset_request": return <Settings size={13} />;
      case "password_changed": return <Lock size={13} />;
      case "task_assigned": case "task_status_changed": return <CheckSquare size={13} />;
      case "followup_created": return <BellRing size={13} />;
      case "property_assigned": return <Building2 size={13} />;
      case "listing_approved": case "listing_rejected": return <FileText size={13} />;
      default: return <Settings size={13} />;
    }
  };

  return (
    <div className="fixed inset-0 z-40" onClick={onClose}>
      <div className="absolute top-16 left-4 w-80 bg-card rounded-2xl border border-border overflow-hidden" style={{ boxShadow: "var(--shadow-lg)" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-border">
          <h3 className="text-sm font-semibold">اعلان‌ها</h3>
          {notifications.length > 0 && (
            <span className="text-xs text-muted-foreground">{notifications.length} اعلان</span>
          )}
        </div>
        <div className="max-h-96 overflow-y-auto divide-y divide-border">
          {notifications.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground">اعلانی وجود ندارد</div>
          ) : (
            notifications.map((n) => (
              <div 
                key={n.id} 
                className={cx("flex items-start gap-3 px-4 py-3.5 cursor-pointer hover:bg-secondary/50 transition-colors", !n.isRead && "bg-primary/[0.03]")}
                onClick={() => handleMarkRead(n.id)}
              >
                <div className={cx("w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5", cm[n.type] || "bg-secondary text-muted-foreground")}>
                  {getIcon(n.type)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-1">
                    <p className="text-xs font-semibold text-foreground">{n.title}</p>
                    {!n.isRead && <div className="w-2 h-2 rounded-full bg-primary flex-shrink-0 mt-1" />}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{n.message}</p>
                  <p className="text-xs text-muted-foreground mt-1">{new Date(n.createdAt).toLocaleString("fa-IR")}</p>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
//  Password Reset Request Modal
// =============================================================================

export { NotifDrawer };
