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
import { PAGE_SIZE_OPTIONS } from "../lib/constants";
function Pagination({ page, total, pageSize, onPageChange, onPageSizeChange }: {
  page: number; total: number; pageSize: number;
  onPageChange: (p: number) => void; onPageSizeChange?: (s: number) => void;
}) {
  const totalPages = Math.ceil(total / pageSize) || 1;
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  const [jumpVal, setJumpVal] = useState("");

  const pages = (() => {
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
    if (page <= 4) return [1, 2, 3, 4, 5, -1, totalPages];
    if (page >= totalPages - 3) return [1, -1, totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
    return [1, -1, page - 1, page, page + 1, -2, totalPages];
  })();

  const handleJump = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      const n = parseInt(jumpVal);
      if (!isNaN(n) && n >= 1 && n <= totalPages) onPageChange(n);
      setJumpVal("");
    }
  };

  return (
    <div className="flex items-center justify-between gap-4 flex-wrap">
      <div className="flex items-center gap-3">
        <p className="text-xs text-muted-foreground">
          {total === 0 ? "بدون نتیجه" : <>نمایش <strong className="text-foreground">{start}–{end}</strong> از <strong className="text-foreground">{total}</strong></>}
        </p>
        {onPageSizeChange && (
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground">تعداد:</span>
            <select value={pageSize} onChange={(e) => { onPageSizeChange(Number(e.target.value)); onPageChange(1); }}
              className="text-xs rounded-lg border border-border bg-input-background px-2 py-1 outline-none focus:ring-1 focus:ring-ring">
              {PAGE_SIZE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        )}
      </div>
      <div className="flex items-center gap-1">
        <button onClick={() => onPageChange(1)} disabled={page === 1} title="صفحه اول"
          className="p-1.5 rounded-lg hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-muted-foreground"><ChevronRight size={12} className="inline" /><ChevronRight size={12} className="inline -ml-1.5" /></button>
        <button onClick={() => onPageChange(page - 1)} disabled={page === 1}
          className="p-1.5 rounded-lg hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"><ChevronRight size={14} /></button>
        {pages.map((p, i) =>
          p < 0 ? (
            <span key={p + "_" + i} className="px-1 text-xs text-muted-foreground select-none">…</span>
          ) : (
            <button key={p} onClick={() => onPageChange(p)}
              className={cx("w-8 h-8 rounded-lg text-xs font-semibold transition-colors", p === page ? "bg-primary text-white shadow-sm" : "hover:bg-secondary text-foreground")}>
              {p}
            </button>
          )
        )}
        <button onClick={() => onPageChange(page + 1)} disabled={page === totalPages}
          className="p-1.5 rounded-lg hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"><ChevronLeft size={14} /></button>
        <button onClick={() => onPageChange(totalPages)} disabled={page === totalPages} title="صفحه آخر"
          className="p-1.5 rounded-lg hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-muted-foreground"><ChevronLeft size={12} className="inline" /><ChevronLeft size={12} className="inline -ml-1.5" /></button>
        <div className="flex items-center gap-1.5 mr-2 pr-2 border-r border-border">
          <span className="text-xs text-muted-foreground">برو به</span>
          <input type="number" min={1} max={totalPages} value={jumpVal} onChange={(e) => setJumpVal(e.target.value)} onKeyDown={handleJump} placeholder="—"
            className="w-12 text-xs rounded-lg border border-border bg-input-background px-2 py-1 text-center outline-none focus:ring-1 focus:ring-ring" />
        </div>
      </div>
    </div>
  );
}

export { Pagination };
