import React, { useRef, useState } from "react";
import { cx, toast } from "../../../shared/lib/utils";
import type { AppraisalReport } from "../../../shared/lib/types";
import { Btn } from "../../../shared/components/ui/Btn";
import { Card } from "../../../shared/components/ui/Card";
import { EmptyState } from "../../../shared/components/ui/EmptyState";
import { ConfirmModal } from "../../../shared/components/ConfirmModal";
import { formatJalali } from "../../../shared/lib/jdate";
import {
  Download,
  Eye,
  FileText,
  Loader2,
  Trash2,
  Upload,
} from "lucide-react";

// Mirrors MAX_APPRAISAL_SIZE in apps/properties/validators.py. Enforced here
// for instant feedback; the server re-validates regardless.
const MAX_APPRAISAL_BYTES = 10 * 1024 * 1024;

function formatFileSize(bytes: number): string {
  if (!bytes || bytes <= 0) return "—";
  if (bytes < 1024) return `${bytes.toLocaleString("fa-IR")} بایت`;
  if (bytes < 1024 * 1024)
    return `${(bytes / 1024).toLocaleString("fa-IR", { maximumFractionDigits: 1 })} کیلوبایت`;
  return `${(bytes / (1024 * 1024)).toLocaleString("fa-IR", { maximumFractionDigits: 1 })} مگابایت`;
}

/**
 * The «گزارش کارشناسی» tab of the property detail page.
 *
 * Holds exactly one PDF per property: uploading a new file replaces the
 * previous one on the server. Upload/delete are limited to the assigned
 * consultant (کارشناس ثبت‌کننده / واگذارشده) and admins — `canManage` —
 * while the download follows the gallery-image read access (`canDownload`).
 */
function AppraisalReportTab({
  propertyId,
  report,
  canManage,
  canDownload,
  onUpload,
  onDelete,
}: {
  propertyId: string;
  report?: AppraisalReport | null;
  canManage: boolean;
  canDownload: boolean;
  onUpload?: (propertyId: string, file: File) => Promise<any>;
  onDelete?: (propertyId: string) => Promise<void>;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const validateLocal = (file: File): string | null => {
    const isPdf =
      file.type === "application/pdf" || /\.pdf$/i.test(file.name);
    if (!isPdf) return "فقط فایل PDF برای گزارش کارشناسی مجاز است.";
    if (file.size > MAX_APPRAISAL_BYTES)
      return "حجم گزارش کارشناسی نباید بیشتر از ۱۰ مگابایت باشد.";
    return null;
  };

  const handlePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-picking the same file after an error
    if (!file || !onUpload) return;

    const localError = validateLocal(file);
    if (localError) {
      toast({ type: "error", message: localError });
      return;
    }

    setUploading(true);
    onUpload(propertyId, file)
      .then(() => {
        toast({
          type: "success",
          message: report
            ? "گزارش کارشناسی جدید جایگزین فایل قبلی شد."
            : "گزارش کارشناسی با موفقیت بارگذاری شد.",
        });
      })
      .catch((err: any) => {
        toast({
          type: "error",
          message: err?.message || "خطا در بارگذاری گزارش کارشناسی",
        });
      })
      .finally(() => setUploading(false));
  };

  const handleDelete = async () => {
    if (!onDelete) return;
    setDeleting(true);
    try {
      await onDelete(propertyId);
      toast({ type: "success", message: "گزارش کارشناسی حذف شد." });
    } catch (err: any) {
      toast({
        type: "error",
        message: err?.message || "خطا در حذف گزارش کارشناسی",
      });
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  const openInNewTab = (url: string) => {
    // Same-origin navigation carries the session cookie; the endpoint
    // answers with Content-Disposition so the browser saves the file.
    window.open(url, "_blank", "noopener");
  };

  const uploadedAtJalali = report?.uploadedAt
    ? formatJalali(String(report.uploadedAt).slice(0, 10))
    : null;

  return (
    <div className="max-w-3xl space-y-4">
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="hidden"
        onChange={handlePick}
      />

      {report ? (
        <Card className="p-5">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-red-50 text-red-600 flex items-center justify-center flex-shrink-0">
              <FileText size={22} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold truncate" title={report.fileName}>
                {report.fileName}
              </p>
              <div className="flex items-center gap-3 mt-1.5 flex-wrap text-xs text-muted-foreground">
                <span>{formatFileSize(report.fileSize)}</span>
                {uploadedAtJalali && (
                  <span className="flex items-center gap-1">
                    • {uploadedAtJalali}
                  </span>
                )}
                {report.uploadedBy && (
                  <span className="flex items-center gap-1">
                    • بارگذاری توسط {report.uploadedBy}
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2 mt-4 flex-wrap">
                {canDownload ? (
                  <>
                    <Btn
                      variant="primary"
                      size="sm"
                      disabled={deleting}
                      onClick={() => openInNewTab(report.url)}
                    >
                      <Download size={13} />دانلود
                    </Btn>
                    <Btn
                      variant="secondary"
                      size="sm"
                      disabled={deleting}
                      onClick={() => openInNewTab(`${report.url}${report.url.includes("?") ? "&" : "?"}inline=1`)}
                    >
                      <Eye size={13} />پیش‌نمایش
                    </Btn>
                  </>
                ) : (
                  <span className="text-xs text-muted-foreground bg-secondary px-3 py-1.5 rounded-lg">
                    دانلود این فایل فقط برای کارشناس واگذارشده و مدیر ممکن است.
                  </span>
                )}
                {canManage && onDelete && (
                  <Btn
                    variant="danger"
                    size="sm"
                    disabled={deleting || uploading}
                    onClick={() => setConfirmDelete(true)}
                  >
                    {deleting ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : (
                      <Trash2 size={13} />
                    )}
                    {deleting ? "در حال حذف…" : "حذف"}
                  </Btn>
                )}
              </div>
            </div>
          </div>
        </Card>
      ) : (
        !canManage && (
          <EmptyState
            icon={<FileText size={28} />}
            title="گزارشی ثبت نشده است"
            description="برای این ملک هنوز گزارش کارشناسی‌ای بارگذاری نشده است."
          />
        )
      )}

      {canManage && onUpload && (
        <div
          onClick={() => !uploading && fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click();
          }}
          className={cx(
            "rounded-xl border-2 border-dashed border-border flex flex-col items-center justify-center gap-2 py-10 cursor-pointer hover:border-primary hover:bg-primary/5 transition-colors text-center px-4",
            uploading && "opacity-60 pointer-events-none"
          )}
        >
          {uploading ? (
            <>
              <Loader2 size={22} className="text-primary animate-spin" />
              <span className="text-xs text-muted-foreground">
                در حال بارگذاری…
              </span>
            </>
          ) : (
            <>
              <Upload size={22} className="text-muted-foreground" />
              <span className="text-sm font-medium">
                {report ? "جایگزینی فایل گزارش کارشناسی" : "آپلود گزارش کارشناسی"}
              </span>
              {report && (
                <span className="text-xs text-muted-foreground">
                  فایل جدید جایگزین فایل فعلی می‌شود.
                </span>
              )}
              <span className="text-[11px] text-muted-foreground">
                فقط فایل PDF · حداکثر ۱۰ مگابایت
              </span>
            </>
          )}
        </div>
      )}

      <ConfirmModal
        open={confirmDelete}
        danger
        title="حذف گزارش کارشناسی؟"
        message="فایل گزارش کارشناسی این ملک برای همیشه حذف خواهد شد. این عملیات غیرقابل بازگشت است."
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  );
}

export { AppraisalReportTab };
