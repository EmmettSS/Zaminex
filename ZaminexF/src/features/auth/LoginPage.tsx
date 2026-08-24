import React, { useState, useEffect, useCallback, useRef } from "react";
import { cx } from "../../shared/lib/utils";
import { BadgeV } from "../../shared/lib/types";
import { LayoutDashboard, Building2, FileText, CheckSquare, BellRing, Calendar, Users, User, Activity, Settings, LogOut, Zap, Plus, ArrowUpRight, Lock, Mail, Search, Command, Loader2 } from "lucide-react";
import { Badge } from "../../shared/components/ui/Badge";
import { Btn } from "../../shared/components/ui/Btn";
import { Input } from "../../shared/components/ui/Input";
import { Card } from "../../shared/components/ui/Card";
import { ProfileAvatar } from "../../shared/components/ui/ProfileAvatar";
import { PageHeader } from "../../shared/components/ui/PageHeader";
import { EmptyState } from "../../shared/components/ui/EmptyState";
import { ConfirmModal } from "../../shared/components/ConfirmModal";
import { toast } from "../../shared/lib/utils";
import { PasswordResetModal } from "../../shared/components/PasswordResetModal";
import { Page } from "../../shared/lib/types";
import { getCsrfToken } from "../../shared/lib/apiClient";
function LoginPage({ 
    initialData, 
    navigate 
  }: { 
    initialData: any; 
    navigate: () => void 
  }) {
    const [email, setEmail] = useState(""); 
    const [pw, setPw] = useState("");
    const [loading, setLoading] = useState(false);
    const [showPasswordReset, setShowPasswordReset] = useState(false);

    const [errors, setErrors] = useState<Record<string, string[]>>({});

    // Live counters for the intro panel (real business stats, not placeholders).
    const [stats, setStats] = useState<{ totalProperties: number; activeConsultants: number; soldProperties: number; activeListings: number } | null>(null);

    useEffect(() => {
      let cancelled = false;
      (async () => {
        try {
          const res = await fetch("/common/api/login-stats/", { headers: { Accept: "application/json" } });
          if (!res.ok) return;
          const data = await res.json();
          if (!cancelled) setStats(data);
        } catch {
          // Non-fatal: the panel just shows placeholders until the next load.
        }
      })();
      return () => { cancelled = true; };
    }, []);

    useEffect(() => {
      const errorElement = document.getElementById("login-errors");
      if (!errorElement?.textContent) return;

      try {
        const parsed = JSON.parse(errorElement.textContent);
        setErrors(parsed || {});
      } catch (err) {
        console.error("Failed to parse login errors:", err);
      }
    }, []);
  
    const handleFormSubmit = () => {
      if (!email || !pw) return;
      setLoading(true);

      const formElement = document.getElementById("django-login-form") as HTMLFormElement;
      if (formElement) {
        formElement.submit();
      }
    };
  return (
    <div className="min-h-screen flex bg-background">
      <div className="hidden lg:flex lg:w-1/2 bg-[#0D1829] relative overflow-hidden flex-col justify-between p-12">
        <div className="absolute inset-0 opacity-5" style={{ backgroundImage: "radial-gradient(circle at 20% 50%, #0BB68A 0%, transparent 60%), radial-gradient(circle at 80% 20%, #3B82F6 0%, transparent 50%)" }} />
        <div className="relative z-10">
          <div className="flex items-center gap-2.5 mb-16">
            <div className="w-9 h-9 bg-primary rounded-xl flex items-center justify-center">
              <Zap size={18} className="text-white" />
            </div>
            <div>
              <span className="text-white font-bold text-lg tracking-tight">Zaminex</span>
              <p className="text-white/40 text-xs">سیستم‌عامل املاک</p>
            </div>
          </div>
          <h1 className="text-5xl font-bold text-white leading-tight mb-4">سیستم<br />مدیریت املاک<br /><span className="text-primary">حرفه‌ای</span><br />و یکپارچه</h1>
          <p className="text-white/60 text-base max-w-xs leading-relaxed mb-10">کل کسب‌وکار ملکی خود را از یک مرکز هوشمند مدیریت کنید.</p>
          <div className="grid grid-cols-2 gap-3 mb-10">
            {[
              [stats ? stats.totalProperties.toLocaleString("fa-IR") : "—", "ملک مدیریت‌شده"],
              [stats ? stats.activeConsultants.toLocaleString("fa-IR") : "—", "مشاور فعال"],
              [stats ? stats.soldProperties.toLocaleString("fa-IR") : "—", "املاک فروخته‌شده"],
              [stats ? stats.activeListings.toLocaleString("fa-IR") : "—", "آگهی فعال"],
            ].map(([v, l]) => (
              <div key={l} className="bg-white/5 border border-white/10 rounded-xl p-4">
                <div className="text-2xl font-bold text-white mb-0.5">{v}</div>
                <div className="text-white/50 text-xs">{l}</div>
              </div>
            ))}
          </div>
        </div>
        <p className="relative z-10 text-white/25 text-xs">© Designed and Developed by Emmett Group 2026</p>
      </div>

      <div className="flex-1 flex items-center justify-center p-8 bg-white">
        <div className="w-full max-w-sm">
          <div className="flex items-center gap-2.5 mb-8 lg:hidden">
            <div className="w-8 h-8 bg-primary rounded-xl flex items-center justify-center">
              <Zap size={16} className="text-white" />
            </div>
            <span className="font-bold text-base">Zaminex</span>
          </div>

          <h2 className="text-2xl font-bold mb-1">خوش آمدید</h2>
          <p className="text-sm text-muted-foreground mb-7">برای ورود به داشبورد سازمانی، اطلاعات حساب خود را وارد کنید</p>

          <form id="django-login-form" method="post" action={initialData.loginUrl} className="hidden">
            <input type="hidden" name="csrfmiddlewaretoken" value={initialData.csrfToken} />
            <input type="hidden" name="next" value={initialData.next || "/"} />
            <input type="text" name="username" value={email} readOnly />
            <input type="password" name="password" value={pw} readOnly />
          </form>

          <div className="space-y-4">
            {errors.__all__ && errors.__all__.length > 0 && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
                {errors.__all__[0]}
              </div>
            )}

            <div>
              <Input
                label="نام کاربری یا ایمیل"
                type="text"
                placeholder="admin@zaminex.ir"
                value={email}
                onChange={setEmail}
                icon={<Mail size={14} />}
              />
              {errors.username && errors.username.length > 0 && (
                <p className="mt-1 text-xs text-red-600">{errors.username[0]}</p>
              )}
            </div>

            <div>
              <Input
                label="رمز عبور"
                type="password"
                placeholder="••••••••"
                value={pw}
                onChange={setPw}
                icon={<Lock size={14} />}
              />
              {errors.password && errors.password.length > 0 && (
                <p className="mt-1 text-xs text-red-600">{errors.password[0]}</p>
              )}

              <div className="flex justify-end mt-1.5">
                <button
                  type="button"
                  onClick={() => setShowPasswordReset(true)}
                  className="text-xs text-primary hover:underline"
                >
                  رمز عبور را فراموش کرده‌اید؟
                </button>
              </div>
            </div>

            <Btn
              variant="primary"
              size="lg"
              onClick={handleFormSubmit}
              disabled={loading || !email || !pw}
              fullWidth
            >
              {loading ? (
                <><Loader2 size={14} className="animate-spin" />در حال ورود…</>
              ) : (
                <>ورود به داشبورد <ArrowUpRight size={14} /></>
              )}
            </Btn>
          </div>
        </div>
      </div>

      <PasswordResetModal 
        open={showPasswordReset} 
        onClose={() => setShowPasswordReset(false)}
        csrfToken={initialData.csrfToken}
      />
    </div>
  );
}

// =============================================================================
//  Sidebar
// =============================================================================


export { LoginPage };
