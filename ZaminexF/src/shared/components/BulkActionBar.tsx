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
function BulkActionBar({ count, onArchive, onDelete, onClear }: { count: number; onArchive: () => void; onDelete: () => void; onClear: () => void }) {
  if (count === 0) return null;
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 bg-primary text-white rounded-xl shadow-lg text-sm">
      <span className="font-semibold">{count} مورد انتخاب شد</span>
      <div className="flex items-center gap-2 mr-2">
        <Btn variant="secondary" size="xs" onClick={onArchive} className="!bg-white/15 !text-white !border-white/20 hover:!bg-white/25"><Archive size={12} />بایگانی</Btn>
        <Btn variant="secondary" size="xs" onClick={onDelete} className="!bg-white/15 !text-white !border-white/20 hover:!bg-white/25"><Trash2 size={12} />حذف</Btn>
        <Btn variant="secondary" size="xs" onClick={() => toast({ type: "success", message: "خروجی گرفته شد." })} className="!bg-white/15 !text-white !border-white/20 hover:!bg-white/25"><Download size={12} />خروجی</Btn>
      </div>
      <button onClick={onClear} className="mr-auto text-white/60 hover:text-white"><X size={14} /></button>
    </div>
  );
}

// =============================================================================
//  Confirm Modal
// =============================================================================

export { BulkActionBar };
