import React from "react";
import { cx } from "../../lib/utils";
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, MessageSquare, Sparkles, GripVertical, MoreVertical, Building, History, Flame, Image } from "lucide-react";
import { BadgeV } from "../../lib/types";

function Card({ children, className, onClick, hover }: { children: React.ReactNode; className?: string; onClick?: (e: React.MouseEvent<HTMLDivElement>) => void; hover?: boolean }) {
  return (
    <div onClick={onClick} className={cx("bg-card rounded-2xl border border-border", hover && "cursor-pointer hover:shadow-md transition-shadow duration-200", className)} style={{ boxShadow: "var(--shadow-md)" }}>
      {children}
    </div>
  );
}

export { Card };
