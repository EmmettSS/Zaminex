import { ChevronDown, Search, Check, ChevronUp, MoreVertical, X, User } from "lucide-react";
import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Badge } from "./Badge";
import { Input } from "./Input";
import { cx } from "../../lib/utils";
import { fuzzyFilter } from "../../lib/fuzzySearch";
import { ConsultantOption } from "../../lib/types";
function MultiConsultantCombobox({
  values,
  onChange,
  label,
  consultants,
}: {
  values: string[];
  onChange: (v: string[]) => void;
  label?: string;
  consultants: ConsultantOption[];
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(0);

  const assignableConsultants = consultants.filter((u) => {
    const r = (u.user?.role ?? u.role ?? "").toString().toUpperCase();
    return !r || r === "AGENT";
  });

  const consultantItems = assignableConsultants.map((u) => {
    const fullName = u.name || u.full_name || "";
    const initials =
      fullName
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase() || "")
        .join("") || "??";

    return {
      id: String(u.user?.id || u.id),
      name: fullName,
      email: u.email || "",
      phone: u.phone || u.mobile || "",
      initials,
      role: u.role || "",
      branch: u.branch || "",
      active: u.active ?? u.is_active ?? true,
    };
  });

  const filtered = useMemo(
    () => fuzzyFilter(consultantItems, q, (u) => `${u.name} ${u.role}`),
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
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const toggleSelect = (id: string) => {
    if (values.includes(id)) {
      onChange(values.filter((v) => v !== id));
    } else {
      onChange([...values, id]);
    }
  };

  const handleSelectAll = () => {
    if (values.length === consultantItems.length) {
      onChange([]);
    } else {
      onChange(consultantItems.map((u) => u.id));
    }
  };

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
      e.preventDefault();
      toggleSelect(filtered[focused].id);
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

  const isAllSelected =
    consultantItems.length > 0 && values.length === consultantItems.length;

  return (
    <div className="flex flex-col gap-1.5 w-full" ref={ref}>
      {label && (
        <label className="text-sm font-medium text-foreground">{label}</label>
      )}
      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className={cx(
            "w-full flex items-center gap-2 rounded-xl border border-border bg-input-background px-3 py-1.5 text-xs text-right transition-all outline-none focus:ring-1 focus:ring-primary min-h-[32px]",
            open && "border-primary ring-1 ring-primary"
          )}
        >
          <div className="flex-1 flex flex-wrap gap-1 items-center truncate">
            {isAllSelected ? (
              <span className="font-semibold text-primary">
                همه مشاوران
              </span>
            ) : values.length > 0 ? (
              <span className="font-medium text-foreground">
                انتخاب شده ({values.length})
              </span>
            ) : (
              <span className="text-muted-foreground">
                انتخاب مشاوران…
              </span>
            )}
          </div>
          <ChevronDown size={12} className="text-muted-foreground mr-1" />
        </button>

        {open && (
          <div className="absolute z-50 mt-1 w-full rounded-xl border border-border bg-popover shadow-lg py-1 flex flex-col max-h-60 overflow-hidden">
            <div className="px-2 py-1.5 border-b border-border flex items-center gap-2">
              <Search size={12} className="text-muted-foreground" />
              <input
                ref={inputRef}
                type="text"
                placeholder="جستجوی مشاور..."
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setFocused(0);
                }}
                onKeyDown={handleKey}
                className="w-full bg-transparent text-xs outline-none border-none p-0 focus:ring-0"
              />
            </div>

            <div className="p-1 border-b border-border">
              <button
                type="button"
                onClick={handleSelectAll}
                className="w-full flex items-center justify-between px-2 py-1.5 rounded-lg text-xs font-medium text-right hover:bg-secondary transition-colors"
              >
                <span>{isAllSelected ? "لغو انتخاب همه" : "انتخاب همه"}</span>
                <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                  {consultantItems.length} مورد
                </span>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-1 space-y-0.5">
              {filtered.length === 0 ? (
                <div className="text-xs text-muted-foreground p-3 text-center">
                  مشاوری یافت نشد
                </div>
              ) : (
                filtered.map((u, idx) => {
                  const isSelected = values.includes(u.id);
                  return (
                    <button
                      key={u.id}
                      type="button"
                      onClick={() => toggleSelect(u.id)}
                      className={cx(
                        "w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-right transition-colors text-xs",
                        idx === focused && "bg-secondary/70",
                        isSelected
                          ? "bg-primary/5 text-foreground font-medium"
                          : "hover:bg-secondary text-muted-foreground"
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        readOnly
                        className="rounded border-gray-300 text-primary focus:ring-primary h-3.5 w-3.5"
                      />
                      <User
                        className="w-5 h-5 rounded-full object-cover"
                      />
                      <div className="flex-1 truncate">
                        <span className="font-medium text-foreground block">
                          {hl(u.name)}
                        </span>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export { MultiConsultantCombobox };
