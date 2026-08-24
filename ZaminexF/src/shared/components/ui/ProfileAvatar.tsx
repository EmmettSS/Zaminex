import React from "react";
import { cx } from "../../lib/utils";
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, MessageSquare, Sparkles, GripVertical, MoreVertical, Building, History, Flame, Image } from "lucide-react";
import { BadgeV } from "../../lib/types";
import { Avatar } from "./Avatar";

function ProfileAvatar({ imageUrl, initials, size = "sm" }: { imageUrl?: string | null; initials: string; size?: "xs" | "sm" | "md" | "lg" }) {
  const sizes = { xs: "w-6 h-6 text-xs", sm: "w-8 h-8 text-xs", md: "w-10 h-10 text-sm", lg: "w-12 h-12 text-base" };
  
  if (imageUrl) {
    return (
      <div className="relative flex-shrink-0">
        <img 
          src={imageUrl} 
          alt={initials}
          className={cx("rounded-full object-cover", sizes[size])}
          onError={(e) => {
            const target = e.target as HTMLImageElement;
            target.style.display = 'none';
            const parent = target.parentElement;
            if (parent) {
              const fallback = parent.querySelector('.avatar-fallback') as HTMLElement;
              if (fallback) fallback.style.display = 'flex';
            }
          }}
        />
        <div className={cx("avatar-fallback rounded-full bg-primary/15 text-primary items-center justify-center font-semibold hidden", sizes[size])}>{initials}</div>
      </div>
    );
  }
  
  return <Avatar initials={initials} size={size} />;
}

export { ProfileAvatar };
