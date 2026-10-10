import { ChevronDown, Search, Check, Layers } from "lucide-react";
import React, { useState, useEffect, useRef, useMemo } from "react";
import { Badge } from "./Badge";
import { cx } from "../../lib/utils";
import { fuzzyFilter } from "../../lib/fuzzySearch";

type CategoryOption = {
  id: string | number;
  name: string;
  displayName: string;
  isActive?: boolean;
  attributeCount?: number;
  isSystem?: boolean;
};

function CategoryCombobox({
  value,
  onChange,
  label,
  required,
  error,
  categories,
  placeholder,
  emptyMessage,
}: {
  value: string;
  onChange: (name: string) => void;
  label?: string;
  required?: boolean;
  error?: string;
  categories: CategoryOption[];
  placeholder?: string;
  emptyMessage?: string;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(0);

  const gradientClasses = [
    "from-sky-400 to-blue-500",
    "from-emerald-400 to-teal-500",
    "from-violet-400 to-purple-500",
    "from-amber-400 to-orange-500",
    "from-rose-400 to-pink-500",
    "from-cyan-400 to-indigo-500",
  ];

  const items = useMemo(
    () =>
      categories.map((c) => ({
        id: String(c.id),
        name: c.name || "",
        displayName: c.displayName || "",
        isActive: c.isActive !== false,
        count: Number(c.attributeCount) || 0,
        isSystem: c.isSystem === true,
        gradient: gradientClasses[(Number(c.id) || 0) % gradientClasses.length],
      })),
    [categories]
  );

  const selected = useMemo(() => items.find((c) => c.name === value), [items, value]);
  const filtered = useMemo(
    () => fuzzyFilter(items, q, (c) => `${c.displayName} ${c.name}`),
    [items, q]
  );

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setFocused(0);
    } else setQ("");
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
      onChange(filtered[focused].name);
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
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          aria-haspopup="listbox"
          className={cx(
            "w-full flex items-center gap-2.5 rounded-xl border border-border bg-input-background px-3.5 py-2.5 text-sm text-right transition-all outline-none focus:ring-2 focus:ring-ring",
            open && "border-primary ring-2 ring-ring"
          )}
        >
          {selected ? (
            <>
              <div
                className={cx(
                  "w-6 h-6 rounded-lg bg-gradient-to-br flex items-center justify-center flex-shrink-0",
                  selected.gradient
                )}
              >
                <Layers size={12} className="text-white" />
              </div>
              <span className="flex-1 font-medium truncate">{selected.displayName}</span>
              {selected.isSystem && <Badge label="پایه" variant="info" />}
            </>
          ) : (
            <span className="flex-1 text-muted-foreground">
              {placeholder || "جستجو و انتخاب دسته‌بندی…"}
            </span>
          )}
          <ChevronDown
            size={14}
            className={cx(
              "text-muted-foreground transition-transform flex-shrink-0",
              open && "rotate-180"
            )}
          />
        </button>
        {open && (
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
                  placeholder="جستجوی دسته‌بندی…"
                  className="w-full pr-8 pl-3 py-2 text-sm bg-secondary rounded-lg outline-none placeholder:text-muted-foreground"
                />
              </div>
            </div>
            <div className="max-h-60 overflow-y-auto py-1">
              {filtered.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">
                  {emptyMessage || "دسته‌بندی‌ای یافت نشد"}
                </p>
              ) : (
                filtered.map((c, i) => (
                  <button
                    key={c.id}
                    type="button"
                    onMouseEnter={() => setFocused(i)}
                    onClick={() => {
                      onChange(c.name);
                      setOpen(false);
                    }}
                    className={cx(
                      "w-full flex items-center gap-3 px-3 py-2.5 text-right transition-colors",
                      i === focused ? "bg-secondary" : "hover:bg-secondary/50"
                    )}
                  >
                    <div
                      className={cx(
                        "w-8 h-8 rounded-lg bg-gradient-to-br flex items-center justify-center flex-shrink-0",
                        c.gradient
                      )}
                    >
                      <Layers size={14} className="text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <p className="text-sm font-medium truncate">{hl(c.displayName)}</p>
                        {c.isSystem && <Badge label="پایه" variant="info" />}
                        {!c.isActive && <Badge label="غیرفعال" variant="muted" />}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {[c.name, `${c.count.toLocaleString("fa-IR")} ویژگی`].filter(Boolean).join(" · ")}
                      </p>
                    </div>
                    {value === c.name && (
                      <Check size={13} className="text-primary flex-shrink-0" />
                    )}
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

export { CategoryCombobox };
