import React, { useState, useEffect, useCallback, useRef } from "react";
import { cx } from "../../shared/lib/utils";
import { BadgeV } from "../../shared/lib/types";
import { LayoutDashboard, Building2, FileText, CheckSquare, BellRing, Calendar, Users, User, Activity, Settings, LogOut, Zap, Plus, ArrowUpRight, Lock, Mail, Search, Command, Loader2, Smartphone, KeyRound, RefreshCw, MessageSquare } from "lucide-react";
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
import { getCsrfToken, apiFetch, readJson, apiErrorMessage } from "../../shared/lib/apiClient";
function LoginPage({ 
    initialData, 
    navigate 
  }: { 
    initialData: any; 
    navigate: () => void 
  }) {
    // Which form the server renders is decided by the admin's global
    // «گزینه‌های ورود» switch, delivered here through initialData.loginMethod.
    const loginMethod = initialData.loginMethod === "sms" ? "sms" : "password";

    const [email, setEmail] = useState(""); 
    const [pw, setPw] = useState("");
    const [loading, setLoading] = useState(false);
    const [showPasswordReset, setShowPasswordReset] = useState(false);

    const [errors, setErrors] = useState<Record<string, string[]>>({});

    // ── SMS OTP state ───────────────────────────────────────────────────
    const [mobile, setMobile] = useState("");
    const [code, setCode] = useState("");
    const [smsStep, setSmsStep] = useState<"mobile" | "code">("mobile");
    const [smsLoading, setSmsLoading] = useState(false);
    const [smsError, setSmsError] = useState<string | null>(null);
    const [resendIn, setResendIn] = useState(0);

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

    // Countdown for the "resend code" link.
    useEffect(() => {
      if (resendIn <= 0) return;
      const timer = setInterval(() => setResendIn((s) => Math.max(0, s - 1)), 1000);
      return () => clearInterval(timer);
    }, [resendIn]);
  
    const handleFormSubmit = () => {
      if (!email || !pw) return;
      setLoading(true);

      const formElement = document.getElementById("django-login-form") as HTMLFormElement;
      if (formElement) {
        formElement.submit();
      }
    };

    const digitsOnly = (v: string) => v.replace(/[^\d]/g, "");

    const handleRequestCode = async () => {
      const m = digitsOnly(mobile);
      if (!/^09\d{9}$/.test(m)) {
        setSmsError("شماره موبایل معتبر نیست. شماره باید با ۰۹ شروع شود و ۱۱ رقم باشد.");
        return;
      }
      setSmsLoading(true);
      setSmsError(null);
      try {
        const res = await apiFetch("/accounts/sms-login/request/", {
          method: "POST",
          body: JSON.stringify({ mobile: m }),
        }, initialData.csrfToken);
        const data = await readJson(res);
        if (!res.ok) {
          setSmsError(apiErrorMessage(data, "خطا در ارسال کد تأیید"));
          return;
        }
        setSmsStep("code");
        setResendIn(60);
        toast({
          type: "success",
          message: typeof data?.detail === "string" ? data.detail : "کد تأیید ارسال شد.",
        });
      } catch {
        setSmsError("خطا در ارتباط با سرور");
      } finally {
        setSmsLoading(false);
      }
    };

    const handleVerifyCode = async () => {
      const m = digitsOnly(mobile);
      const c = digitsOnly(code);
      if (c.length !== 6) return;
      setSmsLoading(true);
      setSmsError(null);
      try {
        const res = await apiFetch("/accounts/sms-login/verify/", {
          method: "POST",
          body: JSON.stringify({ mobile: m, code: c, next: initialData.next || "/" }),
        }, initialData.csrfToken);
        const data = await readJson(res);
        if (!res.ok) {
          setSmsError(apiErrorMessage(data, "کد تأیید واردشده صحیح نیست"));
          return;
        }
        // The server has started an authenticated session; land on the app.
        // `data.next` is validated server-side, so it cannot redirect off-site.
        window.location.assign(data?.next || "/");
      } catch {
        setSmsError("خطا در ارتباط با سرور");
      } finally {
        setSmsLoading(false);
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
          <p className="text-sm text-muted-foreground mb-7">
            {loginMethod === "sms"
              ? "کد تأیید یک‌بارمصرف به شماره موبایل شما پیامک می‌شود."
              : "برای ورود به داشبورد سازمانی، اطلاعات حساب خود را وارد کنید"}
          </p>

          {loginMethod === "sms" ? (
            <div className="space-y-4">
              {smsError && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
                  {smsError}
                </div>
              )}

              {smsStep === "mobile" ? (
                <>
                  <Input
                    label="شماره موبایل"
                    type="tel"
                    inputMode="numeric"
                    placeholder="۰۹۱۲xxxxxxx"
                    value={mobile}
                    onChange={(v) => { setMobile(digitsOnly(v)); setSmsError(null); }}
                    icon={<Smartphone size={14} />}
                  />
                  <Btn
                    variant="primary"
                    size="lg"
                    onClick={handleRequestCode}
                    disabled={smsLoading || !/^09\d{9}$/.test(digitsOnly(mobile))}
                    fullWidth
                  >
                    {smsLoading ? (
                      <><Loader2 size={14} className="animate-spin" />در حال ارسال کد…</>
                    ) : (
                      <><MessageSquare size={14} />دریافت کد تأیید</>
                    )}
                  </Btn>
                </>
              ) : (
                <>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>کد تأیید برای <span dir="ltr" className="font-semibold text-foreground">{digitsOnly(mobile)}</span> پیامک شد.</span>
                    <button
                      type="button"
                      onClick={() => { setSmsStep("mobile"); setCode(""); setSmsError(null); }}
                      className="text-primary hover:underline"
                    >
                      تغییر شماره
                    </button>
                  </div>

                  <Input
                    label="کد تأیید"
                    type="tel"
                    inputMode="numeric"
                    placeholder="کد ۶ رقمی"
                    value={code}
                    onChange={(v) => { setCode(digitsOnly(v).slice(0, 6)); setSmsError(null); }}
                    icon={<KeyRound size={14} />}
                  />

                  <Btn
                    variant="primary"
                    size="lg"
                    onClick={handleVerifyCode}
                    disabled={smsLoading || digitsOnly(code).length !== 6}
                    fullWidth
                  >
                    {smsLoading ? (
                      <><Loader2 size={14} className="animate-spin" />در حال ورود…</>
                    ) : (
                      <>ورود به داشبورد <ArrowUpRight size={14} /></>
                    )}
                  </Btn>

                  <div className="flex justify-center">
                    <button
                      type="button"
                      onClick={() => { if (resendIn === 0) handleRequestCode(); }}
                      disabled={resendIn > 0 || smsLoading}
                      className="text-xs text-muted-foreground hover:text-primary disabled:opacity-50 inline-flex items-center gap-1"
                    >
                      <RefreshCw size={12} />
                      {resendIn > 0 ? `ارسال مجدد تا ${resendIn} ثانیه دیگر` : "ارسال مجدد کد"}
                    </button>
                  </div>
                </>
              )}
            </div>
          ) : (
            <>
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
            </>
          )}
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
