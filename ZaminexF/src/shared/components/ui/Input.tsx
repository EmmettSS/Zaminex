import React from "react";
import { cx } from "../../lib/utils";
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, MessageSquare, Sparkles, GripVertical, MoreVertical, Building, History, Flame, Image } from "lucide-react";
import { BadgeV } from "../../lib/types";

function Input({ label, type = "text", placeholder, value, onChange, icon, error, required, textarea, rows, readOnly }: {
  label?: string; type?: string; placeholder?: string; value: string;
  onChange: (v: string) => void; icon?: React.ReactNode; error?: string;
  required?: boolean; textarea?: boolean; rows?: number; readOnly?: boolean;
}) {
  const cls = "w-full rounded-xl border border-border bg-input-background px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground outline-none transition-all focus:ring-2 focus:ring-ring focus:border-primary";
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-sm font-medium text-foreground">{label}{required && <span className="text-primary mr-1">*</span>}</label>}
      <div className="relative">
        {icon && <span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground">{icon}</span>}
        {textarea
          ? <textarea value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} rows={rows ?? 4} className={cx(cls, "resize-none")} readOnly={readOnly} />
          : <input type={type} placeholder={placeholder} value={value} onChange={(e) => onChange(e.target.value)} className={cx(cls, icon && "pr-10")} readOnly={readOnly} />}
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

export { Input };
