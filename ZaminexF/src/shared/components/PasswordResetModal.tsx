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
import { getCsrfToken, readJson, apiErrorMessage } from "../lib/apiClient";
import { createPortal } from "react-dom";
function PasswordResetModal({ open, onClose, csrfToken }: { open: boolean; onClose: () => void; csrfToken?: string }) {
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!username.trim()) {
      setError("نام کاربری الزامی است");
      return;
    }

    setLoading(true);
    setError("");
    try {
      // Deliberately a plain fetch, not apiFetch: this modal opens from the
      // login screen where there is no session to expire, so the shared
      // "session ended → go to login" handling would be wrong here. Only the
      // error *formatting* is shared.
      const res = await fetch("/common/api/password-reset-request/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(csrfToken),
        },
        credentials: "include",
        body: JSON.stringify({ username: username.trim() }),
      });

      const data = await readJson(res).catch(() => null);
      if (res.ok) {
        setSuccess(true);
        setTimeout(() => {
          onClose();
          setSuccess(false);
          setUsername("");
        }, 2000);
      } else {
        setError(apiErrorMessage(data, "خطا در ارسال درخواست"));
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
            <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center flex-shrink-0">
              <Lock size={18} className="text-amber-600" />
            </div>
            <div>
              <h3 className="text-base font-bold">فراموشی رمز عبور</h3>
              <p className="text-xs text-muted-foreground mt-0.5">درخواست تغییر رمز عبور حساب کاربری</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-secondary rounded-lg transition-colors flex-shrink-0">
            <X size={16} />
          </button>
        </div>

        {success ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-center">
            <CheckCircle2 size={32} className="text-emerald-600 mx-auto mb-2" />
            <p className="text-sm font-semibold text-emerald-700">درخواست شما با موفقیت ثبت شد</p>
            <p className="text-xs text-emerald-600 mt-1">مدیران سیستم به زودی با شما تماس خواهند گرفت</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-foreground mb-2 block">
                نام کاربری خود را وارد کنید <span className="text-primary">*</span>
              </label>
              <div className="relative">
                <User size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => {
                    setUsername(e.target.value);
                    setError("");
                  }}
                  placeholder="مثال: ali_mohammadi"
                  className="w-full rounded-xl border border-border bg-input-background pr-10 pl-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground outline-none transition-all focus:ring-2 focus:ring-ring focus:border-primary"
                />
              </div>
              {error && <p className="mt-1.5 text-xs text-destructive">{error}</p>}
            </div>

            <div className="rounded-xl bg-blue-50 border border-blue-200 p-3">
              <p className="text-xs text-blue-700 leading-relaxed">
                <strong>توجه:</strong> پس از ارسال درخواست، مدیران سیستم رمز عبور جدیدی برای شما تنظیم خواهند کرد.
              </p>
            </div>

            <div className="flex gap-2 justify-end pt-2">
              <Btn variant="secondary" size="sm" onClick={onClose}>انصراف</Btn>
              <Btn variant="primary" size="sm" onClick={handleSubmit} disabled={loading || !username.trim()}>
                {loading ? <><Loader2 size={13} className="animate-spin" />در حال ارسال...</> : <><Send size={13} />ارسال درخواست</>}
              </Btn>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

// =============================================================================
//  Admin Password Change Modal
// =============================================================================

export { PasswordResetModal };
