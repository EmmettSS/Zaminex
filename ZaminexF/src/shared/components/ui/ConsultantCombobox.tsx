import { ChevronDown, Search, Check, ChevronUp, MoreVertical, X } from "lucide-react";
import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Badge } from "./Badge";
import { ProfileAvatar } from "./ProfileAvatar";
import { Input } from "./Input";
import { cx } from "../../lib/utils";
import { fuzzyFilter } from "../../lib/fuzzySearch";
function ConsultantCombobox({
  value,
  onChange,
  label,
  required,
  disabled,
  error,
  consultants,
}: {
  value: string;
  onChange: (v: string) => void;
  label?: string;
  required?: boolean;
  disabled?: boolean;
  error?: string;
  consultants: Array<{
    id: string | number;
    full_name?: string;
    role?: string;
    user?: {
      id?: string | number;
      first_name?: string;
      last_name?: string;
      username?: string;
      role?: string;
    };
    branch?: string;
    is_active?: boolean;
    profile_image?: string | null;
  }>;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(0);

  const assignableConsultants = consultants.filter((c) => {
    const r = (c.user?.role ?? c.role ?? "").toString().toUpperCase();
    return !r || r === "AGENT";
  });

  const consultantItems = assignableConsultants.map((c) => {
    const name =
      c.full_name?.trim() ||
      `${c.user?.first_name || ""} ${c.user?.last_name || ""}`.trim() ||
      c.user?.username ||
      "مشاور نامشخص";

    const branch = c.branch || "";
    const role = "مشاور";

    return {
      id: String(c.user?.id || c.id),
      name,
      role,
      branch,
      imageUrl: c.profile_image ?? null,
      active: c.is_active ?? true,
      avatar:
        name
          .split(/\s+/)
          .filter(Boolean)
          .slice(0, 2)
          .map((part) => part[0]?.toUpperCase() || "")
          .join("") || "??",
    };
  });

  const selected = useMemo(() => consultantItems.find((c) => c.id === String(value)), [consultantItems, value]);
  const filtered = useMemo(
    () => fuzzyFilter(consultantItems, q, (c) => `${c.name} ${c.role} ${c.branch}`),
    [consultantItems, q]
  );

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setFocused(0);
    } else {
      setQ("");
    }
  }, [open]);

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocused((p) => Math.min(p + 1, filtered.length - 1));
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocused((p) => Math.max(p - 1, 0));
    }
    if (e.key === "Enter" && filtered[focused]) {
      onChange(filtered[focused].id);
      setOpen(false);
    }
    if (e.key === "Escape") setOpen(false);
  };

  const hl = (text: string) => {
    if (!q) return <>{text}</>;
    const i = text.toLowerCase().indexOf(q.toLowerCase());
    if (i === -1) return <>{text}</>;
    return (
      <>
        {text.slice(0, i)}
        <mark className="bg-primary/20 text-primary rounded-sm not-italic">
          {text.slice(i, i + q.length)}
        </mark>
        {text.slice(i + q.length)}
      </>
    );
  };

  return (
    <div className="flex flex-col gap-1.5" ref={ref}>
      {label && (
        <label className="text-sm font-medium text-foreground">
          {label}
          {required && <span className="text-primary mr-1">*</span>}
        </label>
      )}
      <div className="relative">
        <button
          type="button"
          onClick={() => !disabled && setOpen(!open)}
          disabled={disabled}
          className={cx(
            "w-full px-3 py-2 rounded-xl border border-border bg-white text-right text-sm flex items-center justify-between transition-colors",
            disabled ? "opacity-60 cursor-not-allowed" : "hover:border-primary/30"
          )}
        >
          {selected ? (
            <>
              <ProfileAvatar imageUrl={selected.imageUrl} initials={selected.avatar} size="xs" />
              <span className="flex-1 font-medium">{selected.name}</span>
              <span className="text-xs text-muted-foreground">{selected.branch}</span>
            </>
          ) : (
            <span className="flex-1 text-muted-foreground">انتخاب مشاور…</span>
          )}
          <ChevronDown
            size={14}
            className={cx(
              "text-muted-foreground transition-transform flex-shrink-0",
              open && "rotate-180"
            )}
          />
        </button>

        {open && !disabled && (
          <div className="absolute z-50 w-full mt-1 bg-card rounded-xl border border-border shadow-lg overflow-hidden">
            <div className="p-2 border-b border-border">
              <div className="relative">
                <Search
                  size={13}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                />
                <input
                  ref={inputRef}
                  value={q}
                  onChange={(e) => {
                    setQ(e.target.value);
                    setFocused(0);
                  }}
                  onKeyDown={handleKey}
                  placeholder="جستجوی نام، نقش، شعبه…"
                  className="w-full pr-8 pl-3 py-2 text-sm bg-secondary rounded-lg outline-none placeholder:text-muted-foreground"
                />
              </div>
            </div>

            <div className="max-h-52 overflow-y-auto py-1">
              {filtered.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">
                  مشاوری یافت نشد
                </p>
              ) : (
                filtered.map((c, i) => (
                  <button
                    key={c.id}
                    type="button"
                    onMouseEnter={() => setFocused(i)}
                    onClick={() => {
                      onChange(c.id);
                      setOpen(false);
                    }}
                    className={cx(
                      "w-full flex items-center gap-3 px-3 py-2.5 text-right transition-colors",
                      i === focused ? "bg-secondary" : "hover:bg-secondary/50"
                    )}
                  >
                    <ProfileAvatar imageUrl={c.imageUrl} initials={c.avatar} size="sm" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium">{hl(c.name)}</p>
                      <p className="text-xs text-muted-foreground">
                        {c.role} · {c.branch}
                      </p>
                    </div>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <div
                        className={cx(
                          "w-1.5 h-1.5 rounded-full",
                          c.active ? "bg-emerald-400" : "bg-muted-foreground"
                        )}
                      />
                      {String(value) === c.id && <Check size={13} className="text-primary" />}
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        )}
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

export { ConsultantCombobox };
