import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { cx } from "../../../shared/lib/utils";
import { Page, Role, Property, Listing, FollowUp, ConsultantItem, BadgeV } from "../../../shared/lib/types";
import { fmtShort, toPersianType, toPersianDeal, toPersianPropertyStatus, toPersianTaskStatus, toPersianTaskType, toPersianPriority, toPersianChannel, propertyStatusToUI, toPersianFollowupType } from "../../../shared/lib/utils";
import { Badge } from "../../../shared/components/ui/Badge";
import { Btn } from "../../../shared/components/ui/Btn";
import { Input } from "../../../shared/components/ui/Input";
import { Card } from "../../../shared/components/ui/Card";
import { SelectField } from "../../../shared/components/ui/SelectField";
import { ProfileAvatar } from "../../../shared/components/ui/ProfileAvatar";
import { KpiCard } from "../../../shared/components/ui/KpiCard";
import { EmptyState } from "../../../shared/components/ui/EmptyState";
import { PageHeader } from "../../../shared/components/ui/PageHeader";
import { ConfirmModal } from "../../../shared/components/ConfirmModal";
import { ActionMenu } from "../../../shared/components/ActionMenu";
import { Pagination } from "../../../shared/components/Pagination";
import { BulkActionBar } from "../../../shared/components/BulkActionBar";
import { PropertyCombobox } from "../../../shared/components/ui/PropertyCombobox";
import { ConsultantCombobox } from "../../../shared/components/ui/ConsultantCombobox";
import { DistrictCombobox } from "../../../shared/components/ui/DistrictCombobox";
import { apiFetch, readJson, apiErrorMessage, getCsrfToken } from "../../../shared/lib/apiClient";
import { toast } from "../../../shared/lib/utils";
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, ReferenceLine, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis } from "recharts";
import { Building2, FileText, CheckSquare, BellRing, Users, Activity, Settings, Plus, RefreshCw, Eye, Edit2, Trash2, Archive, Clock, MapPin, Check, X, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, SlidersHorizontal, ArrowUpRight, LayoutGrid, List, Download, Search, MoreVertical, Phone, Mail, Calendar, TrendingUp, Star, Shield, Lock, Key, Send, Loader2, AlertTriangle, Info, XCircle, CheckCircle2, TriangleAlert, Columns, MessageSquare, Sparkles, GripVertical, Building, History, Flame, Image, Zap, LayoutDashboard, Command, Filter, Award, BarChart3, Layers, Upload } from "lucide-react";
function GalleryTab({
  propertyId,
  gallery,
  setGallery,
  onDeleteImage,
  onUploadImages,
  onReorderImages,
}: {
  propertyId: string;
  gallery: any[];
  setGallery: React.Dispatch<React.SetStateAction<any[]>>;
  onDeleteImage?: (propertyId: string, imageId: string) => Promise<void>;
  onUploadImages?: (propertyId: string, files: File[]) => Promise<any>;
  onReorderImages?: (propertyId: string, order: { id: string | number; sort_order: number }[]) => Promise<void>;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);
  const [confirmDeleteImg, setConfirmDeleteImg] = useState<any | null>(null);

  const handleDelete = async (img: any) => {
    const imgId = String(img.id);
    if (!imgId || !onDeleteImage) return;
    setDeletingId(imgId);
    try {
      await onDeleteImage(propertyId, imgId);
      setGallery((g) => g.filter((x) => String(x.id) !== imgId));
      toast({ type: "success", message: "تصویر با موفقیت حذف شد." });
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطا در حذف تصویر" });
    } finally {
      setDeletingId(null);
      setConfirmDeleteImg(null);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (!files.length || !onUploadImages) return;
    setUploading(true);
    try {
      const result = await onUploadImages(propertyId, files);
      if (result?.data) {
        const newImages = Array.isArray(result.data) ? result.data : [result.data];
        setGallery((g) => [...g, ...newImages]);
      }
      toast({ type: "success", message: `${files.length} تصویر با موفقیت آپلود شد.` });
    } catch (err: any) {
      toast({ type: "error", message: err?.message || "خطا در آپلود تصاویر" });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDragStart = (e: React.DragEvent, idx: number) => {
    setDragIdx(idx);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverIdx(idx);
  };

  const handleDragLeave = () => {
    setDragOverIdx(null);
  };

  const handleDrop = async (e: React.DragEvent, dropIdx: number) => {
    e.preventDefault();
    setDragOverIdx(null);
    if (dragIdx === null || dragIdx === dropIdx) {
      setDragIdx(null);
      return;
    }
    const reordered = [...gallery];
    const [moved] = reordered.splice(dragIdx, 1);
    reordered.splice(dropIdx, 0, moved);
    setGallery(reordered);
    setDragIdx(null);

    if (onReorderImages) {
      const order = reordered.map((img, i) => ({ id: img.id, sort_order: i }));
      try {
        await onReorderImages(propertyId, order);
        toast({ type: "success", message: "ترتیب تصاویر بروزرسانی شد." });
      } catch (err: any) {
        toast({ type: "error", message: err?.message || "خطا در تغییر ترتیب" });
        setGallery(gallery);
      }
    }
  };

  const handleDragEnd = () => {
    setDragIdx(null);
    setDragOverIdx(null);
  };

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-semibold">{gallery.length.toLocaleString("fa-IR")} تصویر</p>
        {gallery.length > 0 && (
          <p className="text-xs text-muted-foreground">برای حذف، روی تصویر هاور کنید · برای تغییر ترتیب بکشید</p>
        )}
      </div>
      {gallery.length === 0 && (
        <div className="mb-4 py-12 text-center flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-secondary flex items-center justify-center">
            <Image size={20} className="text-muted-foreground" />
          </div>
          <p className="text-sm font-medium">هنوز تصویری برای این ملک ثبت نشده است</p>
        </div>
      )}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={handleUpload}
      />
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mb-4">
        {gallery.map((img, i) => {
          const imgUrl = img.url || `https://images.unsplash.com/photo-${img.id || img}?w=300&h=300&fit=crop&auto=format`;
          const imgKey = img.id || `gallery-img-${i}`;
          const isDragging = dragIdx === i;
          const isDragOver = dragOverIdx === i && dragIdx !== i;
          const isDeleting = deletingId === String(img.id);
          return (
            <div
              key={imgKey}
              draggable
              onDragStart={(e) => handleDragStart(e, i)}
              onDragOver={(e) => handleDragOver(e, i)}
              onDragLeave={handleDragLeave}
              onDrop={(e) => handleDrop(e, i)}
              onDragEnd={handleDragEnd}
              className={cx(
                "aspect-square rounded-xl overflow-hidden bg-secondary group cursor-pointer relative transition-all duration-150",
                isDragging && "opacity-40 scale-95",
                isDragOver && "ring-2 ring-primary ring-offset-2"
              )}
            >
              <img
                src={imgUrl}
                alt={`تصویر ${i + 1}`}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300 pointer-events-none"
              />
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors" />
              <button
                onClick={(e) => { e.stopPropagation(); setConfirmDeleteImg(img); }}
                disabled={isDeleting}
                className="absolute top-2 right-2 w-6 h-6 bg-white/90 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-50"
              >
                {isDeleting ? <Loader2 size={11} className="text-red-600 animate-spin" /> : <X size={11} className="text-red-600" />}
              </button>
              <div className="absolute top-2 left-2 w-6 h-6 bg-white/90 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-grab active:cursor-grabbing">
                <GripVertical size={11} className="text-muted-foreground" />
              </div>
              <div className="absolute bottom-1.5 left-1.5 bg-black/50 text-white text-[10px] px-1.5 py-0.5 rounded font-mono">{i + 1}</div>
            </div>
          );
        })}
        <div
          onClick={() => fileInputRef.current?.click()}
          className={cx(
            "aspect-square rounded-xl border-2 border-dashed border-border flex flex-col items-center justify-center cursor-pointer hover:border-primary hover:bg-primary/5 transition-colors",
            uploading && "opacity-60 pointer-events-none"
          )}
        >
          {uploading ? (
            <><Loader2 size={20} className="text-primary animate-spin mb-2" /><span className="text-xs text-muted-foreground">در حال آپلود…</span></>
          ) : (
            <><Upload size={20} className="text-muted-foreground mb-2" /><span className="text-xs text-muted-foreground">آپلود</span></>
          )}
        </div>
      </div>
      <ConfirmModal
        open={!!confirmDeleteImg}
        title="حذف تصویر؟"
        danger
        message="این تصویر برای همیشه حذف خواهد شد. این عملیات غیرقابل بازگشت است."
        onConfirm={() => { if (confirmDeleteImg) handleDelete(confirmDeleteImg); }}
        onCancel={() => setConfirmDeleteImg(null)}
      />
    </div>
  );
}

export { GalleryTab };
