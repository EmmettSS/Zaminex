import React from "react";
import { cx } from "../../lib/utils";
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, MessageSquare, Sparkles, GripVertical, MoreVertical, Building, History, Flame, Image } from "lucide-react";
import { BadgeV } from "../../lib/types";

function Btn({ children, variant = "primary", size = "md", onClick, disabled, type = "button", className, fullWidth }: {
  children: React.ReactNode; variant?: "primary" | "secondary" | "ghost" | "danger" | "outline";
  size?: "xs" | "sm" | "md" | "lg"; onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void; disabled?: boolean;
  type?: "button" | "submit"; className?: string; fullWidth?: boolean; title?: string;
}) {
  const v: Record<string, string> = {
    primary: "bg-primary text-white hover:opacity-90 shadow-sm",
    secondary: "bg-white text-foreground hover:bg-secondary border border-border shadow-sm",
    ghost: "bg-transparent text-foreground hover:bg-secondary",
    danger: "bg-destructive text-white hover:opacity-90 shadow-sm",
    outline: "bg-transparent text-primary border border-primary hover:bg-primary/5",
  };
  const s: Record<string, string> = {
    xs: "px-2.5 py-1 text-xs gap-1.5 rounded-lg", sm: "px-3.5 py-1.5 text-xs gap-1.5 rounded-lg",
    md: "px-4 py-2 text-sm gap-2 rounded-xl", lg: "px-5 py-2.5 text-sm gap-2 rounded-xl",
  };
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={cx("inline-flex items-center justify-center font-medium transition-all duration-150 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed", v[variant], s[size], fullWidth && "w-full", className)}>
      {children}
    </button>
  );
}

export { Btn };
