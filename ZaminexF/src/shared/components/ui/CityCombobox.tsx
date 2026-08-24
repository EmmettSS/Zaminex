import { ChevronDown, Search, Check, MapPin } from "lucide-react";
import React, { useState, useEffect, useRef, useMemo } from "react";
import { cx } from "../../lib/utils";
import { fuzzyFilter } from "../../lib/fuzzySearch";

function CityCombobox({
  label,
  value,
  onChange,
  citiesList = [],
  error,
  required,
}: {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  citiesList?: string[];
  error?: string;
  required?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(0);

  const filtered = useMemo(() => fuzzyFilter(citiesList, q, (d) => d), [citiesList, q]);

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
      onChange(filtered[focused]);
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
    <div className="space-y-1.5">
      {label && (
        <label className="block text-xs font-medium text-foreground">
          {label}
          {required && <span className="mr-1 text-destructive">*</span>}
        </label>
      )}
      <div className="relative" ref={ref}>
        <button
          type="button"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          aria-haspopup="listbox"
          className={cx(
            "w-full flex items-center gap-2 rounded-xl border border-border bg-input-background px-3 py-2.5 text-sm text-right transition-all outline-none focus:ring-2 focus:ring-ring",
            open && "border-primary ring-2 ring-ring",
            error && "border-destructive focus:ring-destructive/20"
          )}
        >
          <MapPin size={13} className="text-muted-foreground flex-shrink-0" />
          <span className={cx("flex-1 truncate", value ? "text-foreground font-medium" : "text-muted-foreground")}>
            {value || "انتخاب شهر"}
          </span>
          <ChevronDown size={13} className={cx("text-muted-foreground transition-transform flex-shrink-0", open && "rotate-180")} />
        </button>

        {open && (
          <div className="absolute z-50 w-full mt-1 bg-card rounded-xl border border-border shadow-lg overflow-hidden">
            <div className="p-2 border-b border-border">
              <div className="relative">
                <Search size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  ref={inputRef}
                  value={q}
                  onChange={(e) => {
                    setQ(e.target.value);
                    setFocused(0);
                  }}
                  onKeyDown={handleKey}
                  placeholder="جستجوی شهر…"
                  className="w-full pr-7 pl-2 py-1.5 text-xs bg-secondary rounded-lg outline-none placeholder:text-muted-foreground"
                />
              </div>
            </div>

            <div className="max-h-52 overflow-y-auto py-1">
              {filtered.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">شهری یافت نشد</p>
              ) : (
                filtered.map((d, i) => (
                  <button
                    key={d}
                    type="button"
                    onMouseEnter={() => setFocused(i)}
                    onClick={() => {
                      onChange(d);
                      setOpen(false);
                    }}
                    className={cx(
                      "w-full flex items-center gap-3 px-3 py-2.5 text-right transition-colors text-xs",
                      i === focused ? "bg-secondary" : "hover:bg-secondary/50",
                      value === d && "bg-primary/5 text-primary font-medium"
                    )}
                  >
                    <MapPin size={12} className="text-muted-foreground flex-shrink-0" />
                    <span className="flex-1 text-right">{hl(d)}</span>
                    {value === d && <Check size={12} className="text-primary flex-shrink-0" />}
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

export { CityCombobox };
