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
import { apiFetch, readJson, apiErrorMessage } from "../lib/apiClient";
function AdminPasswordChangeModal({ open, onClose, userId, userName, csrfToken, onSuccess }: { 
  open: boolean; 
  onClose: () => void; 
  userId?: string | number;
  userName?: string;
  csrfToken?: string;
  onSuccess?: () => void;
}) {
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const handleSubmit = async () => {
    if (!newPassword || !confirmPassword) {
      setError("تمام فیلدها الزامی هستند");
      return;
    }

    if (newPassword.length < 8) {
      setError("رمز عبور باید حداقل ۸ کاراکتر باشد");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("رمز عبور و تکرار آن مطابقت ندارند");
      return;
    }

    setLoading(true);
    setError("");
    try {
      // Routed through apiFetch so a stale CSRF token is refreshed and retried
      // once, and an expired session is reported centrally.
      const res = await apiFetch(
        `/common/api/admin-password-change/${userId}/`,
        {
          method: "POST",
          body: JSON.stringify({
            new_password: newPassword,
            confirm_password: confirmPassword,
          }),
        },
        csrfToken
      );

      const data = await readJson(res).catch(() => null);
      if (res.ok) {
        setSuccess(true);
        setTimeout(() => {
          onClose();
          setSuccess(false);
          setNewPassword("");
          setConfirmPassword("");
          if (onSuccess) onSuccess();
        }, 1500);
      } else {
        // This endpoint reports failures under `error`, while DRF's own
        // rejections (CSRF, permission, expired session) use `detail`.
        // apiErrorMessage reads whichever the server sent.
        setError(apiErrorMessage(data, "خطا در تغییر رمز عبور"));
      }
    } catch (err) {
      setError("خطا در ارتباط با سرور");
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <Card className="w-full max-w-md p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-red-100 flex items-center justify-center flex-shrink-0">
              <Key size={18} className="text-red-600" />
            </div>
            <div>
              <h3 className="text-base font-bold">تغییر رمز عبور</h3>
              <p className="text-xs text-muted-foreground mt-0.5">تغییر رمز عبور کاربر {userName || ""}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-secondary rounded-lg transition-colors flex-shrink-0">
            <X size={16} />
          </button>
        </div>

        {success ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-center">
            <CheckCircle2 size={32} className="text-emerald-600 mx-auto mb-2" />
            <p className="text-sm font-semibold text-emerald-700">رمز عبور با موفقیت تغییر کرد</p>
            <p className="text-xs text-emerald-600 mt-1">نوتیفیکیشن برای کاربر ارسال شد</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-foreground mb-2 block">
                رمز عبور جدید <span className="text-primary">*</span>
              </label>
              <div className="relative">
                <Lock size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => {
                    setNewPassword(e.target.value);
                    setError("");
                  }}
                  placeholder="حداقل ۸ کاراکتر"
                  className="w-full rounded-xl border border-border bg-input-background pr-10 pl-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground outline-none transition-all focus:ring-2 focus:ring-ring focus:border-primary"
                />
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-foreground mb-2 block">
                تکرار رمز عبور <span className="text-primary">*</span>
              </label>
              <div className="relative">
                <Lock size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    setError("");
                  }}
                  placeholder="تکرار رمز عبور"
                  className="w-full rounded-xl border border-border bg-input-background pr-10 pl-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground outline-none transition-all focus:ring-2 focus:ring-ring focus:border-primary"
                />
              </div>
              {error && <p className="mt-1.5 text-xs text-destructive">{error}</p>}
            </div>

            <div className="rounded-xl bg-amber-50 border border-amber-200 p-3">
              <p className="text-xs text-amber-700 leading-relaxed">
                <strong>توجه:</strong> پس از تغییر رمز عبور، نوتیفیکیشن برای کاربر و سایر مدیران ارسال خواهد شد.
              </p>
            </div>

            <div className="flex gap-2 justify-end pt-2">
              <Btn variant="secondary" size="sm" onClick={onClose}>انصراف</Btn>
              <Btn variant="danger" size="sm" onClick={handleSubmit} disabled={loading || !newPassword || !confirmPassword}>
                {loading ? <><Loader2 size={13} className="animate-spin" />در حال تغییر...</> : <><Check size={13} />تایید و تغییر</>}
              </Btn>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}


// =============================================================================
//  Task Detail Modal
// =============================================================================

export { AdminPasswordChangeModal };
