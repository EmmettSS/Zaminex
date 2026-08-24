import { ChevronDown, Search, Check, ChevronUp, MoreVertical, X } from "lucide-react";
import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Badge } from "./Badge";
import { Input } from "./Input";
import { cx, fmtShort } from "../../lib/utils";
import { fuzzyFilter } from "../../lib/fuzzySearch";
function PropertyCombobox({
  value,
  onChange,
  label,
  required,
  locked,
  lockedLabel,
  error,
  properties,
}: {
  value: string;
  onChange: (v: string) => void;
  label?: string;
  required?: boolean;
  locked?: boolean;
  lockedLabel?: string;
  error?: string;
  properties: Array<{
    id: string | number;
    title?: string;
    internalCode?: string;
    district?: string;
    price?: number | string;
  }>;
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

  const propertyItems = properties.map((p, index) => ({
    id: String(p.id),
    title: p.title || "",
    internalCode: p.internalCode || "",
    district: p.district || "",
    price: typeof p.price === "string" ? Number(p.price) || 0 : p.price || 0,
    isShared: (p as any).isShared === true,
    gradient: gradientClasses[index % gradientClasses.length],
  }));

  const selected = useMemo(() => propertyItems.find((p) => p.id === String(value)), [propertyItems, value]);
  const filtered = useMemo(
    () => fuzzyFilter(propertyItems, q, (p) => `${p.title} ${p.internalCode} ${p.district}`),
    [propertyItems, q]
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

  if (locked) {
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label className="text-sm font-medium text-foreground">
            {label}
            {required && <span className="text-primary mr-1">*</span>}
          </label>
        )}
        <div className="flex items-center gap-2.5 rounded-xl border border-border bg-muted px-3.5 py-2.5 opacity-75 cursor-not-allowed">
          {selected && (
            <div
              className={cx(
                "w-6 h-6 rounded-lg bg-gradient-to-br flex-shrink-0",
                selected.gradient
              )}
            />
          )}
          <span className="flex-1 text-sm font-medium text-foreground truncate">
            {lockedLabel || selected?.title || "—"}
          </span>
          <span className="text-xs text-muted-foreground bg-secondary px-2 py-0.5 rounded-full">
            قفل
          </span>
        </div>
        {error && <p className="text-xs text-destructive">{error}</p>}
      </div>
    );
  }

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
          className={cx(
            "w-full flex items-center gap-2.5 rounded-xl border border-border bg-input-background px-3.5 py-2.5 text-sm text-right transition-all outline-none focus:ring-2 focus:ring-ring",
            open && "border-primary ring-2 ring-ring"
          )}
        >
          {selected ? (
            <>
              <div
                className={cx(
                  "w-6 h-6 rounded-lg bg-gradient-to-br flex-shrink-0",
                  selected.gradient
                )}
              />
              <span className="flex-1 font-medium truncate">{selected.title}</span>
              {selected.isShared && (
                <Badge label="اشتراکی" variant="info" />
              )}
            </>
          ) : (
            <span className="flex-1 text-muted-foreground">
              جستجو و انتخاب ملک…
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
                  placeholder="جستجو بر اساس عنوان، کد یا محله…"
                  className="w-full pr-8 pl-3 py-2 text-sm bg-secondary rounded-lg outline-none placeholder:text-muted-foreground"
                />
              </div>
            </div>
            <div className="max-h-60 overflow-y-auto py-1">
              {filtered.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">
                  ملکی یافت نشد
                </p>
              ) : (
                filtered.map((p, i) => (
                  <button
                    key={p.id}
                    type="button"
                    onMouseEnter={() => setFocused(i)}
                    onClick={() => {
                      onChange(p.id);
                      setOpen(false);
                    }}
                    className={cx(
                      "w-full flex items-center gap-3 px-3 py-2.5 text-right transition-colors",
                      i === focused ? "bg-secondary" : "hover:bg-secondary/50"
                    )}
                  >
                    <div
                      className={cx(
                        "w-8 h-8 rounded-lg bg-gradient-to-br flex-shrink-0",
                        p.gradient
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <p className="text-sm font-medium truncate">{hl(p.title)}</p>
                        {p.isShared && (
                          <Badge label="اشتراکی" variant="info" />
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {[p.district, p.internalCode].filter(Boolean).join(" · ")}
                      </p>
                    </div>
                    {String(value) === p.id && (
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

export { PropertyCombobox };
