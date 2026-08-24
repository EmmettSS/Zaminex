import React, { useState, useCallback, useEffect, useRef } from "react";
import { cx } from "../lib/utils";
import { BadgeV } from "../lib/types";
import { ChevronLeft, ChevronRight, ChevronDown, Check, X, Archive, Trash2, Download, RefreshCw, Clock, Building2, Eye, Edit2, CheckCircle2, MoreVertical, MapPin, User, Lock, Key, Send, Loader2, Shield, Filter, Plus, CheckSquare, BellRing, LayoutDashboard, FileText, Users, Activity, Settings, LogOut, TriangleAlert } from "lucide-react";
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
function ConfirmModal({ open, title, message, onConfirm, onCancel, danger = false }: {
  open: boolean; title: string; message: string; onConfirm: () => void; onCancel: () => void; danger?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <Card className="w-full max-w-sm p-6 shadow-2xl">
        <div className={cx("w-11 h-11 rounded-xl flex items-center justify-center mb-4", danger ? "bg-red-100" : "bg-amber-50")}><TriangleAlert size={20} className={danger ? "text-red-600" : "text-amber-600"} /></div>
        <h3 className="text-base font-semibold mb-1">{title}</h3>
        <p className="text-sm text-muted-foreground mb-5">{message}</p>
        <div className="flex gap-2 justify-end"><Btn variant="secondary" size="sm" onClick={onCancel}>انصراف</Btn><Btn variant={danger ? "danger" : "primary"} size="sm" onClick={onConfirm}><Check size={13} />تایید</Btn></div>
      </Card>
    </div>
  );
}

// =============================================================================
//  Action Menu
// =============================================================================

export { ConfirmModal };
