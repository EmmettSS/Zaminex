import React from "react";
import { cx } from "../../lib/utils";
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, MessageSquare, Sparkles, GripVertical, MoreVertical, Building, History, Flame, Image } from "lucide-react";
import { BadgeV } from "../../lib/types";
import { Card } from "./Card";

function KpiCard({ label, value, sub, icon, trend, trendUp, color }: {
  label: string; value: string; sub?: string; icon: React.ReactNode; trend?: string; trendUp?: boolean; color?: string;
}) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between mb-3">
        <div className={cx("w-10 h-10 rounded-xl flex items-center justify-center", color || "bg-primary/10 text-primary")}>{icon}</div>
        {trend && <span className={cx("flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-full", trendUp ? "bg-emerald-50 text-emerald-600" : "bg-red-50 text-red-500")}>{trendUp ? <ChevronUp size={11} /> : <ChevronDown size={11} />}{trend}</span>}
      </div>
      <div className="text-2xl font-bold text-foreground tracking-tight">{value}</div>
      <div className="text-sm text-muted-foreground mt-0.5 font-medium">{label}</div>
      {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
    </Card>
  );
}

// =============================================================================
//  Consultant Combobox
// =============================================================================

export { KpiCard };
