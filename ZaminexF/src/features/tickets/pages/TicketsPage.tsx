import React, { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, Archive, Check, CheckCircle2, ChevronDown, Clock3, Download, FileText, Filter, Loader2, MessageSquare, Paperclip, Plus, RefreshCw, Search, Send, Tag, UserRound, X, XCircle } from "lucide-react";

import type {
  Page,
  Role,
  TicketDetail,
  TicketPriority,
  TicketRow,
  TicketStatus,
  TicketSubjectType,
  TicketType,
  TicketUser,
} from "../../../shared/lib/types";
import { apiErrorMessage, apiFetch, readJson } from "../../../shared/lib/apiClient";
import { formatJalaliDT } from "../../../shared/lib/jdate";
import { toast } from "../../../shared/lib/utils";
import { Badge } from "../../../shared/components/ui/Badge";
import { Btn } from "../../../shared/components/ui/Btn";
import { Card } from "../../../shared/components/ui/Card";
import { EmptyState } from "../../../shared/components/ui/EmptyState";
import { Input } from "../../../shared/components/ui/Input";
import { JalaliDateInput } from "../../../shared/components/ui/JalaliDateInput";
import { PageHeader } from "../../../shared/components/ui/PageHeader";
import { Pagination } from "../../../shared/components/Pagination";
import { SelectField } from "../../../shared/components/ui/SelectField";

const SUBJECT_OPTIONS: Array<{ value: TicketSubjectType; label: string }> = [
  { value: "PROPERTY", label: "املاک موجود" },
  { value: "LISTING", label: "آگهی‌های موجود" },
  { value: "FOLLOWUP", label: "پیگیری‌های موجود" },
  { value: "TASK", label: "وظایف موجود" },
  { value: "TICKET", label: "تیکت‌های موجود" },
];

const TYPE_OPTIONS: Array<{ value: TicketType; label: string }> = [
  { value: "QUESTION", label: "پرسش" },
  { value: "REQUEST", label: "درخواست" },
  { value: "ALERT", label: "هشدار" },
  { value: "ISSUE", label: "گزارش مشکل" },
  { value: "COMPLAINT", label: "شکایت" },
  { value: "ANNOUNCEMENT", label: "اطلاع‌رسانی" },
  { value: "OTHER", label: "سایر" },
];

const PRIORITY_OPTIONS: Array<{ value: TicketPriority; label: string }> = [
  { value: "NORMAL", label: "عادی" },
  { value: "IMPORTANT", label: "مهم" },
  { value: "URGENT", label: "فوری" },
];

const STATUS_OPTIONS: Array<{ value: TicketStatus | "all"; label: string }> = [
  { value: "all", label: "همه وضعیت‌ها" },
  { value: "OPEN", label: "باز" },
  { value: "WAITING_REPLY", label: "در انتظار پاسخ" },
  { value: "ANSWERED", label: "پاسخ‌داده‌شده" },
  { value: "CLOSED", label: "بسته" },
];

const PAGE_SIZE = 20;

const subjectLabel = (type: TicketSubjectType) =>
  SUBJECT_OPTIONS.find((item) => item.value === type)?.label || type;

const typeLabel = (type: TicketType) =>
  TYPE_OPTIONS.find((item) => item.value === type)?.label || type;

const priorityTone = (priority: TicketPriority): "default" | "info" | "warning" | "danger" => {
  if (priority === "URGENT") return "danger";
  if (priority === "IMPORTANT") return "warning";
  if (priority === "NORMAL") return "info";
  return "default";
};

const statusTone = (status: TicketStatus): "default" | "info" | "success" | "warning" => {
  if (status === "CLOSED") return "default";
  if (status === "ANSWERED") return "success";
  if (status === "WAITING_REPLY") return "warning";
  return "info";
};

const displayUser = (user?: TicketUser | null) => user?.name || user?.username || "کاربر";

const formatBytes = (bytes: number) => {
  if (!bytes) return "۰ بایت";
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024).toLocaleString("fa-IR")} کیلوبایت`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", "٫")} مگابایت`;
};

function getFolder(page: Page): "sent" | "received" | "all" {
  if (page === "tickets-sent") return "sent";
  if (page === "tickets-all") return "all";
  return "received";
}

function getPageTitle(page: Page) {
  if (page === "tickets-sent") return "تیکت‌های ارسالی";
  if (page === "tickets-all") return "فهرست همه تیکت‌ها";
  return "تیکت‌های دریافتی";
}

function RemoteSubjectSelect({
  type,
  value,
  onChange,
  csrfToken,
}: {
  type: TicketSubjectType;
  value: string;
  onChange: (value: string) => void;
  csrfToken: string;
}) {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<Array<{ id: string | number; label: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    const timer = window.setTimeout(() => {
      void apiFetch(
        `/tickets/api/subjects/?type=${encodeURIComponent(type)}&q=${encodeURIComponent(query)}&page_size=25`,
        { method: "GET", signal: controller.signal },
        csrfToken,
      )
        .then(async (res) => {
          const data = await res.json().catch(() => null);
          if (!res.ok) throw new Error(apiErrorMessage(data, "خطا در دریافت موضوع‌ها"));
          setOptions(data?.results || []);
        })
        .catch((err: unknown) => {
          if (!controller.signal.aborted) {
            setError(err instanceof Error ? err.message : "خطا در دریافت موضوع‌ها");
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 180);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [type, query, csrfToken]);

  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-foreground">
        رکورد مرتبط <span className="text-primary mr-1">*</span>
      </label>
      <div className="relative">
        <Search size={13} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={`جستجو در ${subjectLabel(type)}…`}
          className="w-full rounded-xl border border-border bg-secondary pr-8 pl-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
      </div>
      <div className="relative">
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full appearance-none rounded-xl border border-border bg-input-background px-3.5 py-2.5 pl-9 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring focus:border-primary"
        >
          <option value="">{loading ? "در حال دریافت…" : "رکورد را انتخاب کنید"}</option>
          {options.map((option) => (
            <option key={String(option.id)} value={String(option.id)}>{option.label}</option>
          ))}
        </select>
        <ChevronDown size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
      </div>
      {error ? <p className="text-xs text-destructive">{error}</p> : (
        <p className="text-[11px] text-muted-foreground">فقط رکوردهایی که به آن‌ها دسترسی دارید نمایش داده می‌شوند.</p>
      )}
    </div>
  );
}

function RemoteRecipientPicker({
  values,
  onChange,
  csrfToken,
}: {
  values: string[];
  onChange: (values: string[]) => void;
  csrfToken: string;
}) {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<TicketUser[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      void apiFetch(
        `/tickets/api/recipients/?q=${encodeURIComponent(query)}&limit=100`,
        { method: "GET", signal: controller.signal },
        csrfToken,
      )
        .then(async (res) => {
          const data = await res.json().catch(() => null);
          if (!res.ok) throw new Error(apiErrorMessage(data, "خطا در دریافت گیرنده‌ها"));
          setOptions(Array.isArray(data) ? data : []);
        })
        .catch(() => {
          if (!controller.signal.aborted) setOptions([]);
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 180);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, csrfToken]);

  const toggle = (id: string) => {
    onChange(values.includes(id) ? values.filter((item) => item !== id) : [...values, id]);
  };

  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-foreground">
        گیرنده <span className="text-primary mr-1">*</span>
      </label>
      <div className="relative">
        <Search size={13} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="جستجوی نام کارشناس یا مدیر…"
          className="w-full rounded-xl border border-border bg-secondary pr-8 pl-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
      </div>
      <div className="rounded-xl border border-border bg-input-background p-1">
        <div className="max-h-48 overflow-y-auto">
          {loading ? <p className="p-3 text-xs text-muted-foreground">در حال دریافت کاربران…</p> : options.length === 0 ? (
            <p className="p-3 text-xs text-muted-foreground">کاربر فعالی یافت نشد.</p>
          ) : options.map((option) => {
            const selected = values.includes(String(option.id));
            return (
              <button
                type="button"
                key={String(option.id)}
                onClick={() => toggle(String(option.id))}
                className="w-full flex items-center gap-2 rounded-lg px-2.5 py-2 text-right hover:bg-secondary transition-colors"
              >
                <span className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${selected ? "bg-primary border-primary text-white" : "border-border"}`}>
                  {selected && <Check size={11} />}
                </span>
                <span className="flex-1 min-w-0">
                  <span className="block text-sm truncate">{displayUser(option)}</span>
                  <span className="block text-[11px] text-muted-foreground">{option.role === "ADMIN" ? "مدیر" : "کارشناس"} · {option.username}</span>
                </span>
              </button>
            );
          })}
        </div>
      </div>
      {values.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {values.map((id) => {
            const option = options.find((item) => String(item.id) === id);
            return (
              <span key={id} className="inline-flex items-center gap-1 rounded-full bg-primary/10 text-primary px-2.5 py-1 text-xs">
                {option ? displayUser(option) : `کاربر ${id}`}
                <button type="button" onClick={() => toggle(id)} aria-label="حذف گیرنده"><X size={11} /></button>
              </span>
            );
          })}
        </div>
      ) : <p className="text-[11px] text-muted-foreground">امکان انتخاب یک یا چند گیرنده وجود دارد.</p>}
    </div>
  );
}

function TicketCreateForm({
  navigate,
  role,
  csrfToken,
}: {
  navigate: (page: Page) => void;
  role: Role;
  csrfToken: string;
}) {
  const [ticketType, setTicketType] = useState<TicketType>("REQUEST");
  const [priority, setPriority] = useState<TicketPriority>("NORMAL");
  const [subjectType, setSubjectType] = useState<TicketSubjectType>("PROPERTY");
  const [subjectId, setSubjectId] = useState("");
  const [recipientIds, setRecipientIds] = useState<string[]>([]);
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [slaDueDate, setSlaDueDate] = useState("");
  const [slaDueTime, setSlaDueTime] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubjectTypeChange = (value: string) => {
    setSubjectType(value as TicketSubjectType);
    setSubjectId("");
  };

  const onFilesChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files || []);
    const allowed = new Set(["pdf", "jpg", "jpeg", "png", "webp"]);
    const valid: File[] = [];
    for (const file of selected) {
      const extension = file.name.split(".").pop()?.toLowerCase() || "";
      if (!allowed.has(extension)) {
        toast({ type: "error", message: `نوع فایل «${file.name}» مجاز نیست.` });
        continue;
      }
      if (file.size > 10 * 1024 * 1024) {
        toast({ type: "error", message: `حجم «${file.name}» بیشتر از ۱۰ مگابایت است.` });
        continue;
      }
      valid.push(file);
    }
    if (valid.length > 5) {
      toast({ type: "error", message: "حداکثر ۵ پیوست برای هر پیام مجاز است." });
    }
    setFiles(valid.slice(0, 5));
  };

  const removeFile = (name: string, index: number) => {
    setFiles((current) => current.filter((file, fileIndex) => fileIndex !== index || file.name !== name));
  };

  const submit = async () => {
    setError(null);
    if (!subjectId) return setError("انتخاب رکورد مرتبط الزامی است.");
    if (recipientIds.length === 0) return setError("حداقل یک گیرنده انتخاب کنید.");
    if (!message.trim()) return setError("متن پیام الزامی است.");

    const formData = new FormData();
    if (title.trim()) formData.append("title", title.trim());
    formData.append("ticketType", ticketType);
    formData.append("priority", priority);
    formData.append("subjectType", subjectType);
    formData.append("subjectId", subjectId);
    formData.append("recipientIds", JSON.stringify(recipientIds));
    formData.append("message", message.trim());
    const tags = tagsInput.split(",").map((item) => item.trim()).filter(Boolean);
    if (tags.length) formData.append("tags", JSON.stringify(tags));
    if (slaDueDate) {
      const timePart = slaDueTime.trim() ? slaDueTime.trim() : "23:59";
      const dt = new Date(`${slaDueDate}T${timePart}`);
      if (!Number.isNaN(dt.getTime())) {
        formData.append("slaDueAt", dt.toISOString());
      }
    }
    files.forEach((file) => formData.append("attachments", file));

    setSubmitting(true);
    try {
      const res = await apiFetch("/tickets/api/tickets/", { method: "POST", body: formData }, csrfToken);
      const data = await readJson(res);
      if (!res.ok) throw new Error(apiErrorMessage(data, "ثبت تیکت انجام نشد."));
      toast({ type: "success", message: "تیکت با موفقیت ثبت و برای گیرنده ارسال شد." });
      navigate("tickets-sent");
    } catch (err: unknown) {
      const messageText = err instanceof Error ? err.message : "ثبت تیکت انجام نشد.";
      setError(messageText);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-1.5 mb-6 text-xs text-muted-foreground">
        <button type="button" onClick={() => navigate("tickets-received")} className="hover:text-foreground">تیکت‌ها</button>
        <span>‹</span>
        <span className="text-foreground font-medium">ثبت تیکت جدید</span>
      </div>
      <PageHeader title="ثبت تیکت جدید" subtitle={role === "admin" ? "ارسال پیام مدیریتی به یک یا چند کاربر فعال" : "ارسال درخواست یا پیام به ادمین یا کارشناسان دیگر"} />
      <Card className="p-6 space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <SelectField label="نوع تیکت" value={ticketType} onChange={(value) => setTicketType(value as TicketType)} options={TYPE_OPTIONS} required />
          <SelectField label="اولویت" value={priority} onChange={(value) => setPriority(value as TicketPriority)} options={PRIORITY_OPTIONS} required />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <SelectField label="موضوع تیکت" value={subjectType} onChange={onSubjectTypeChange} options={SUBJECT_OPTIONS} required />
          <Input label="عنوان تیکت (اختیاری)" value={title} onChange={setTitle} placeholder="مثلاً درخواست بررسی آگهی" />
        </div>
        <RemoteSubjectSelect type={subjectType} value={subjectId} onChange={setSubjectId} csrfToken={csrfToken} />
        <RemoteRecipientPicker values={recipientIds} onChange={setRecipientIds} csrfToken={csrfToken} />
        <Input label="متن پیام" value={message} onChange={setMessage} textarea rows={7} placeholder="متن تیکت را بنویسید…" required />
        <Input label="برچسب‌ها" value={tagsInput} onChange={setTagsInput} placeholder="مثلاً آگهی، فوری (با ویرگول جدا کنید)" />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <JalaliDateInput
            label="مهلت پاسخ سفارشی (تاریخ)"
            value={slaDueDate}
            onChange={setSlaDueDate}
            placeholder="انتخاب تاریخ مهلت پاسخ…"
          />
          <Input
            label="مهلت پاسخ سفارشی (ساعت)"
            type="time"
            value={slaDueTime}
            onChange={setSlaDueTime}
          />
        </div>
        <div className="rounded-xl border border-dashed border-border bg-secondary/40 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Paperclip size={15} className="text-primary" />
            <p className="text-sm font-medium">پیوست‌ها</p>
            <span className="text-[11px] text-muted-foreground">حداکثر ۵ فایل، هر فایل ۱۰ مگابایت</span>
          </div>
          <input type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.webp" onChange={onFilesChange} className="block w-full text-xs text-muted-foreground file:ml-3 file:rounded-lg file:border-0 file:bg-primary file:px-3 file:py-2 file:text-xs file:font-medium file:text-white" />
          {files.length > 0 && <div className="mt-3 space-y-1.5">
            {files.map((file, index) => <div key={`${file.name}-${index}`} className="flex items-center gap-2 text-xs bg-card rounded-lg px-2.5 py-2 border border-border"><FileText size={13} className="text-muted-foreground" /><span className="flex-1 truncate">{file.name}</span><span className="text-muted-foreground">{formatBytes(file.size)}</span><button type="button" onClick={() => removeFile(file.name, index)} className="text-destructive"><X size={13} /></button></div>)}
          </div>}
        </div>
        <div className="rounded-xl bg-primary/5 border border-primary/10 p-3 text-xs text-muted-foreground leading-6">
          مهلت پاسخ در صورت خالی‌بودن به‌صورت خودکار بر اساس اولویت تعیین می‌شود: عادی ۴۸ ساعت، مهم ۲۴ ساعت و فوری ۴ ساعت.
        </div>
        {error && <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">{error}</div>}
        <div className="flex justify-end gap-2 pt-1">
          <Btn variant="secondary" onClick={() => navigate("tickets-received")}>انصراف</Btn>
          <Btn variant="primary" onClick={submit} disabled={submitting}>{submitting ? "در حال ارسال…" : "ارسال تیکت"}</Btn>
        </div>
      </Card>
    </div>
  );
}

function TicketFilters({
  role,
  filters,
  setFilter,
  clear,
  userOptions,
  userLoading,
}: {
  role: Role;
  filters: Record<string, string>;
  setFilter: (key: string, value: string) => void;
  clear: () => void;
  userOptions: TicketUser[];
  userLoading: boolean;
}) {
  const hasFilters = Object.values(filters).some(Boolean);
  return (
    <Card className="p-4 mb-5">
      <div className="flex items-center gap-2 mb-3 text-sm font-semibold"><Filter size={15} className="text-primary" />فیلتر و جستجو</div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 items-end">
        <Input label="جستجو" value={filters.q} onChange={(value) => setFilter("q", value)} placeholder="شماره، عنوان، پیام یا کاربر…" />
        <SelectField label="وضعیت" value={filters.status || "all"} onChange={(value) => setFilter("status", value === "all" ? "" : value)} options={STATUS_OPTIONS} />
        <SelectField label="وضعیت پاسخ" value={filters.response || "all"} onChange={(value) => setFilter("response", value === "all" ? "" : value)} options={[{ value: "all", label: "همه" }, { value: "no_reply", label: "بدون هیچ پاسخ" }, { value: "answered", label: "پاسخ‌داده‌شده" }, { value: "waiting_for_me", label: "در انتظار پاسخ من" }]} />
        <SelectField label="خوانده‌شدن" value={filters.read || "all"} onChange={(value) => setFilter("read", value === "all" ? "" : value)} options={[{ value: "all", label: "همه" }, { value: "unread", label: "خوانده‌نشده" }, { value: "read", label: "خوانده‌شده" }]} />
        <SelectField label="نوع تیکت" value={filters.ticketType || "all"} onChange={(value) => setFilter("ticketType", value === "all" ? "" : value)} options={[{ value: "all", label: "همه انواع" }, ...TYPE_OPTIONS]} />
        <SelectField label="موضوع" value={filters.subjectType || "all"} onChange={(value) => setFilter("subjectType", value === "all" ? "" : value)} options={[{ value: "all", label: "همه موضوع‌ها" }, ...SUBJECT_OPTIONS]} />
        <SelectField label="اولویت" value={filters.priority || "all"} onChange={(value) => setFilter("priority", value === "all" ? "" : value)} options={[{ value: "all", label: "همه اولویت‌ها" }, ...PRIORITY_OPTIONS]} />
        {role === "admin" && (
          <SelectField label="کاربر مرتبط" value={filters.userId} onChange={(value) => setFilter("userId", value)} options={[{ value: "", label: userLoading ? "در حال دریافت کاربران…" : "همه کاربران" }, ...userOptions.map((user) => ({ value: String(user.id), label: `${displayUser(user)} · ${user.role === "ADMIN" ? "مدیر" : "کارشناس"}` }))]} />
        )}
        <JalaliDateInput label="از تاریخ ایجاد" value={filters.createdFrom} onChange={(value) => setFilter("createdFrom", value)} />
        <JalaliDateInput label="تا تاریخ ایجاد" value={filters.createdTo} onChange={(value) => setFilter("createdTo", value)} />
        {role === "admin" && <SelectField label="مهلت پاسخ" value={filters.overdue || "all"} onChange={(value) => setFilter("overdue", value === "all" ? "" : value)} options={[{ value: "all", label: "همه" }, { value: "true", label: "SLA گذشته" }]} />}
      </div>
      {filters.createdFrom && filters.createdTo && filters.createdFrom > filters.createdTo && <p className="text-xs text-destructive mt-2">تاریخ شروع نمی‌تواند پس از تاریخ پایان باشد.</p>}
      <div className="flex justify-end mt-3">
        <button type="button" onClick={clear} disabled={!hasFilters} className={`text-xs ${hasFilters ? "text-destructive hover:underline" : "text-muted-foreground/50 cursor-not-allowed"}`}>پاک کردن فیلترها</button>
      </div>
    </Card>
  );
}

function TicketDetailPanel({
  detail,
  currentUserId,
  role,
  csrfToken,
  onRefresh,
}: {
  detail: TicketDetail | null;
  currentUserId: string | null;
  role: Role;
  csrfToken: string;
  onRefresh: () => Promise<void>;
}) {
  const [message, setMessage] = useState("");
  const [target, setTarget] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const recipients = detail?.recipients || [];
    const ownerId = detail?.createdBy?.id;
    const viewerIsOwner = String(ownerId || "") === String(currentUserId || "");
    const viewerIsRecipient = recipients.some((recipient) => String(recipient.id) === String(currentUserId || ""));
    setTarget(viewerIsRecipient && !viewerIsOwner
      ? String(currentUserId)
      : recipients.length === 1
      ? String(recipients[0].id)
      : "");
    setMessage("");
    setFiles([]);
    setError(null);
  }, [detail?.id, detail?.createdBy?.id, detail?.recipients, currentUserId]);

  if (!detail) {
    return <Card className="min-h-[32rem] flex items-center justify-center"><EmptyState icon={<MessageSquare size={28} />} title="یک تیکت را انتخاب کنید" description="برای مشاهده رشته پیام‌ها، یکی از تیکت‌های فهرست را باز کنید." /></Card>;
  }

  const isOwner = String(detail.createdBy?.id || "") === String(currentUserId || "");
  const isRecipient = detail.recipients.some((recipient) => String(recipient.id) === String(currentUserId || ""));
  const canTarget = isOwner || (role === "admin" && !isRecipient);
  const canClose = role === "admin" || isOwner || isRecipient;

  const onReplyFiles = (event: React.ChangeEvent<HTMLInputElement>) => {
    const next: File[] = [];
    for (const file of Array.from(event.target.files || [])) {
      const extension = file.name.split(".").pop()?.toLowerCase() || "";
      if (!["pdf", "jpg", "jpeg", "png", "webp"].includes(extension) || file.size > 10 * 1024 * 1024) {
        toast({ type: "error", message: "فقط PDF، JPG، PNG و WEBP تا حجم ۱۰ مگابایت مجاز است." });
        continue;
      }
      next.push(file);
    }
    setFiles(next.slice(0, 5));
  };

  const reply = async () => {
    if (!message.trim()) return setError("متن پاسخ الزامی است.");
    if (canTarget && detail.recipients.length > 1 && !target) return setError("رشته گیرنده پاسخ را انتخاب کنید.");
    setBusy(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("message", message.trim());
      if (target) formData.append("threadRecipientId", target);
      files.forEach((file) => formData.append("attachments", file));
      const res = await apiFetch(`/tickets/api/tickets/${detail.id}/reply/`, { method: "POST", body: formData }, csrfToken);
      const data = await readJson(res);
      if (!res.ok) throw new Error(apiErrorMessage(data, "ارسال پاسخ انجام نشد."));
      setMessage("");
      setFiles([]);
      await onRefresh();
      toast({ type: "success", message: "پاسخ با موفقیت ارسال شد." });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "ارسال پاسخ انجام نشد.");
    } finally {
      setBusy(false);
    }
  };

  const changeStatus = async (action: "close" | "reopen") => {
    setBusy(true);
    try {
      const res = await apiFetch(`/tickets/api/tickets/${detail.id}/${action}/`, { method: "POST" }, csrfToken);
      const data = await readJson(res);
      if (!res.ok) throw new Error(apiErrorMessage(data, "تغییر وضعیت انجام نشد."));
      await onRefresh();
      toast({ type: "success", message: action === "close" ? "تیکت بسته شد." : "تیکت بازگشایی شد." });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "تغییر وضعیت انجام نشد.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="min-h-[32rem] overflow-hidden flex flex-col">
      <div className="p-4 border-b border-border bg-secondary/30">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center flex-shrink-0"><MessageSquare size={18} /></div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap"><span className="text-xs font-mono text-muted-foreground">{detail.ticketNumber}</span><Badge label={detail.statusLabel} variant={statusTone(detail.status)} /><Badge label={detail.priorityLabel} variant={priorityTone(detail.priority)} /></div>
            <h2 className="text-base font-semibold mt-1 truncate">{detail.title}</h2>
            <p className="text-xs text-muted-foreground mt-1">{detail.subject?.restricted ? "موضوع مرتبط با دسترسی محدود" : detail.subject?.label} · ایجاد توسط {displayUser(detail.createdBy)}</p>
          </div>
          {canClose && <button type="button" disabled={busy} onClick={() => changeStatus(detail.status === "CLOSED" ? "reopen" : "close")} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-2 text-xs hover:bg-card disabled:opacity-50">{detail.status === "CLOSED" ? <RefreshCw size={13} /> : <Archive size={13} />}{detail.status === "CLOSED" ? "بازگشایی" : "بستن"}</button>}
        </div>
        <div className="flex flex-wrap gap-1.5 mt-3">
          {detail.tags?.map((tag) => <span key={tag} className="inline-flex items-center gap-1 rounded-full bg-card border border-border px-2 py-0.5 text-[11px] text-muted-foreground"><Tag size={10} />{tag}</span>)}
          {detail.isOverdue && <Badge label="SLA گذشته" variant="danger" />}
          {detail.slaDueAt && !detail.isOverdue && <span className="text-[11px] text-muted-foreground flex items-center gap-1"><Clock3 size={11} />مهلت {formatJalaliDT(detail.slaDueAt)}</span>}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3 max-h-[34rem]">
        {detail.messages.map((item) => {
          const own = String(item.sender?.id || "") === String(currentUserId || "");
          return <div key={String(item.id)} className={`flex ${own ? "justify-start" : "justify-end"}`}>
            <div className={`max-w-[88%] rounded-2xl border px-3.5 py-3 ${own ? "bg-primary/5 border-primary/15 rounded-br-md" : "bg-secondary/70 border-border rounded-bl-md"}`}>
              <div className="flex items-center gap-2 mb-1.5"><span className="text-xs font-semibold">{displayUser(item.sender)}</span>{item.isInitial && <Badge label="پیام اولیه" variant="info" />}<span className="text-[10px] text-muted-foreground">{formatJalaliDT(item.createdAt)}</span></div>
              <p className="text-sm leading-7 whitespace-pre-wrap break-words">{item.body}</p>
              {item.attachments?.length > 0 && <div className="mt-2 space-y-1.5 border-t border-border/70 pt-2">{item.attachments.map((attachment) => <a key={String(attachment.id)} href={attachment.downloadUrl} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-xs text-primary hover:underline"><Paperclip size={12} />{attachment.originalName}<span className="text-muted-foreground">({formatBytes(attachment.size)})</span></a>)}</div>}
            </div>
          </div>;
        })}
      </div>
      <div className="p-4 border-t border-border bg-card">
        {detail.recipients.length > 1 && canTarget && <SelectField label="پاسخ به رشته" value={target} onChange={setTarget} options={detail.recipients.map((recipient) => ({ value: String(recipient.id), label: displayUser(recipient) }))} placeholder="گیرنده پاسخ را انتخاب کنید" required />}
        {detail.status === "CLOSED" && <div className="mb-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 px-3 py-2 text-xs">ارسال پاسخ، تیکت بسته را دوباره باز می‌کند.</div>}
        <textarea value={message} onChange={(event) => setMessage(event.target.value)} rows={3} maxLength={10000} placeholder="پاسخ خود را بنویسید…" className="w-full resize-y rounded-xl border border-border bg-input-background p-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
        <div className="flex items-center gap-2 mt-2"><label className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-2 text-xs cursor-pointer hover:bg-secondary"><Paperclip size={13} />پیوست<input type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.webp" onChange={onReplyFiles} className="hidden" /></label>{files.length > 0 && <span className="text-xs text-muted-foreground">{files.length.toLocaleString("fa-IR")} فایل آماده ارسال</span>}<span className="mr-auto text-[11px] text-muted-foreground">{message.length.toLocaleString("fa-IR")} / ۱۰٬۰۰۰</span><Btn variant="primary" onClick={reply} disabled={busy}><Send size={13} />{busy ? "در حال ارسال…" : "ارسال پاسخ"}</Btn></div>
        {error && <p className="text-xs text-destructive mt-2">{error}</p>}
      </div>
    </Card>
  );
}

function TicketListPage({
  page,
  role,
  navigate,
  csrfToken,
  currentUserId,
  initialTicketId,
  onUnreadChanged,
}: {
  page: Page;
  role: Role;
  navigate: (page: Page, paramId?: string | number) => void;
  csrfToken: string;
  currentUserId: string | null;
  initialTicketId?: string | null;
  onUnreadChanged?: () => void;
}) {
  const folder = getFolder(page);
  const [rows, setRows] = useState<TicketRow[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(initialTicketId ? String(initialTicketId) : null);
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [listPage, setListPage] = useState(1);
  const [userOptions, setUserOptions] = useState<TicketUser[]>([]);
  const [userLoading, setUserLoading] = useState(false);
  const [filters, setFilters] = useState<Record<string, string>>({
    q: "", status: "", response: "", read: "", ticketType: "", subjectType: "", priority: "", userId: "", createdFrom: "", createdTo: "", overdue: "",
  });
  const currentFilterKey = useMemo(() => JSON.stringify(filters), [filters]);
  const listAbortRef = useRef<AbortController | null>(null);

  const setFilter = (key: string, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
    setListPage(1);
  };
  const clearFilters = () => {
    setFilters({ q: "", status: "", response: "", read: "", ticketType: "", subjectType: "", priority: "", userId: "", createdFrom: "", createdTo: "", overdue: "" });
    setListPage(1);
  };

  const buildQuery = (targetFolder = folder, includePagination = true) => {
    const params = new URLSearchParams();
    params.set("folder", targetFolder);
    if (includePagination) {
      params.set("page", String(listPage));
      params.set("page_size", String(PAGE_SIZE));
    }
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    return params;
  };

  const loadRows = async () => {
    listAbortRef.current?.abort();
    const controller = new AbortController();
    listAbortRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/tickets/api/tickets/?${buildQuery().toString()}`, { method: "GET", signal: controller.signal }, csrfToken);
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(apiErrorMessage(data, "خطا در دریافت تیکت‌ها"));
      setRows(data?.results || (Array.isArray(data) ? data : []));
      setTotal(data?.count ?? (Array.isArray(data) ? data.length : 0));
    } catch (err: unknown) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "خطا در دریافت تیکت‌ها");
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  };

  const loadDetail = async (id: string) => {
    setSelectedId(id);
    setDetailLoading(true);
    try {
      const res = await apiFetch(`/tickets/api/tickets/${id}/`, { method: "GET" }, csrfToken);
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(apiErrorMessage(data, "خطا در دریافت جزئیات تیکت"));
      setDetail(data);
      setRows((current) => current.map((row) => String(row.id) === String(id) ? { ...row, isRead: true, isUnread: false } : row));
      onUnreadChanged?.();
    } catch (err: unknown) {
      toast({ type: "error", message: err instanceof Error ? err.message : "خطا در دریافت جزئیات تیکت" });
    } finally {
      setDetailLoading(false);
    }
  };

  const refreshDetail = async () => {
    if (!selectedId) return;
    await loadDetail(selectedId);
    await loadRows();
  };

  useEffect(() => {
    setSelectedId(initialTicketId ? String(initialTicketId) : null);
  }, [initialTicketId]);

  useEffect(() => {
    void loadRows();
    return () => listAbortRef.current?.abort();
    // `currentFilterKey` is a stable serialized dependency; changing a filter
    // resets pagination and causes a single new server-side request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [folder, listPage, currentFilterKey, csrfToken]);

  useEffect(() => {
    if (!selectedId) return;
    // Notifications can open a ticket before its folder list has finished
    // loading, so detail access must not depend on the row being present yet.
    void loadDetail(selectedId);
    // Do not re-fetch the detail whenever the list response is refreshed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  useEffect(() => {
    if (role !== "admin") return;
    const controller = new AbortController();
    setUserLoading(true);
    void apiFetch("/tickets/api/recipients/?limit=100&includeSelf=true&includeInactive=true", { method: "GET", signal: controller.signal }, csrfToken)
      .then(async (res) => {
        const data = await res.json().catch(() => null);
        if (res.ok && Array.isArray(data)) setUserOptions(data);
      })
      .finally(() => {
        if (!controller.signal.aborted) setUserLoading(false);
      });
    return () => controller.abort();
  }, [role, csrfToken]);

  const exportCsv = async () => {
    try {
      const params = buildQuery("all", false);
      const res = await apiFetch(`/tickets/api/tickets/export/?${params.toString()}`, { method: "GET" }, csrfToken);
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(apiErrorMessage(data, "دریافت خروجی انجام نشد."));
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "tickets.csv";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      toast({ type: "error", message: err instanceof Error ? err.message : "دریافت خروجی انجام نشد." });
    }
  };

  const pageTitle = getPageTitle(page);
  const tabs: Array<{ page: Page; label: string }> = role === "admin" ? [
    { page: "tickets-sent", label: "تیکت‌های ارسالی" },
    { page: "tickets-received", label: "تیکت‌های دریافتی" },
    { page: "tickets-all", label: "فهرست همه تیکت‌ها" },
    { page: "create-ticket", label: "ثبت تیکت جدید" },
  ] : [
    { page: "tickets-sent", label: "تیکت‌های ارسالی" },
    { page: "tickets-received", label: "تیکت‌های دریافتی" },
    { page: "create-ticket", label: "ثبت تیکت جدید" },
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <PageHeader
        title={pageTitle}
        subtitle={`${total.toLocaleString("fa-IR")} تیکت`}
        actions={<div className="flex items-center gap-2">{role === "admin" && <Btn variant="secondary" onClick={exportCsv}><Download size={14} />خروجی CSV</Btn>}<Btn variant="primary" onClick={() => navigate("create-ticket")}><Plus size={14} />ثبت تیکت جدید</Btn></div>}
      />
      <div className="flex gap-1.5 mb-5 flex-wrap border-b border-border pb-3">
        {tabs.map((tab) => <button key={tab.page} type="button" onClick={() => navigate(tab.page)} className={`px-3.5 py-2 rounded-lg text-xs font-medium transition-colors ${page === tab.page ? "bg-primary text-white shadow-sm" : "bg-card border border-border hover:bg-secondary"}`}>{tab.label}</button>)}
      </div>
      <TicketFilters role={role} filters={filters} setFilter={setFilter} clear={clearFilters} userOptions={userOptions} userLoading={userLoading} />
      {filters.createdFrom && filters.createdTo && filters.createdFrom > filters.createdTo ? <EmptyState icon={<AlertCircle size={28} />} title="بازه تاریخ نامعتبر است" description="تاریخ شروع را پیش از تاریخ پایان انتخاب کنید." /> : <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(24rem,0.95fr)] gap-4 items-start">
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border"><div className="flex items-center gap-2 text-sm font-semibold"><MessageSquare size={15} className="text-primary" />{pageTitle}</div><button type="button" onClick={() => void loadRows()} className="text-muted-foreground hover:text-primary" title="بروزرسانی"><RefreshCw size={14} /></button></div>
          {loading ? <div className="p-8 flex justify-center text-muted-foreground"><Loader2 size={20} className="animate-spin" /></div> : error ? <div className="m-4 rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">{error}</div> : rows.length === 0 ? <EmptyState icon={<MessageSquare size={26} />} title="تیکتی یافت نشد" description="با فیلترهای فعلی تیکتی برای نمایش وجود ندارد." /> : <div className="divide-y divide-border">{rows.map((row) => <button type="button" key={String(row.id)} onClick={() => setSelectedId(String(row.id))} className={`w-full text-right p-4 transition-colors hover:bg-secondary/50 ${selectedId === String(row.id) ? "bg-primary/[0.04]" : ""} ${row.isUnread ? "font-semibold border-r-4 border-r-primary bg-primary/[0.035]" : ""}`}>
            <div className="flex items-start gap-3"><div className={`mt-1 w-2.5 h-2.5 rounded-full flex-shrink-0 ${row.isUnread ? "bg-primary ring-4 ring-primary/10" : "bg-border"}`} />
              <div className="flex-1 min-w-0"><div className="flex items-center gap-2 flex-wrap"><span className="font-mono text-[11px] text-muted-foreground">{row.ticketNumber}</span><span className="text-sm truncate">{row.title}</span>{row.isUnread && <Badge label="جدید" variant="info" />}</div><div className="flex items-center gap-1.5 mt-2 flex-wrap"><Badge label={row.statusLabel} variant={statusTone(row.status)} /><Badge label={row.priorityLabel} variant={priorityTone(row.priority)} /><span className="text-[11px] text-muted-foreground">{typeLabel(row.ticketType)} · {row.subject?.restricted ? "موضوع محدود" : row.subject?.label}</span></div><div className="flex items-center gap-3 mt-2 text-[11px] text-muted-foreground flex-wrap"><span className="flex items-center gap-1"><UserRound size={11} />{folder === "sent" ? `به ${row.recipients?.map(displayUser).join("، ") || "—"}` : `از ${displayUser(row.createdBy)}`}</span><span>{formatJalaliDT(row.lastMessageAt || row.createdAt)}</span><span>{row.replyCount.toLocaleString("fa-IR")} پاسخ</span>{row.needsResponse && <span className="text-amber-600">در انتظار پاسخ من</span>}{row.isOverdue && <span className="text-destructive">SLA گذشته</span>}</div></div>
            </div>
          </button>)}</div>}
          {!loading && total > 0 && <div className="p-3 border-t border-border"><Pagination page={listPage} total={total} pageSize={PAGE_SIZE} onPageChange={setListPage} /></div>}
        </Card>
        {detailLoading ? <Card className="min-h-[32rem] flex items-center justify-center text-muted-foreground"><Loader2 size={22} className="animate-spin" /></Card> : <TicketDetailPanel detail={detail} currentUserId={currentUserId} role={role} csrfToken={csrfToken} onRefresh={refreshDetail} />}
      </div>}
    </div>
  );
}

export function TicketsPage(props: React.ComponentProps<typeof TicketListPage>) {
  if (props.page === "create-ticket") {
    return <TicketCreateForm navigate={props.navigate} role={props.role} csrfToken={props.csrfToken} />;
  }
  return <TicketListPage {...props} />;
}

export { TicketCreateForm };
