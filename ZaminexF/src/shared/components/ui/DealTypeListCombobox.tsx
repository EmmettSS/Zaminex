import { ChevronDown, Check, Tag } from "lucide-react";
import React, { useState, useRef, useEffect } from "react";
import { cx } from "../../lib/utils";

type DealTypeOption = { id: string | number; displayName: string; name?: string };

function DealTypeListCombobox({
  label,
  value,
  onChange,
  options,
  placeholder,
  error,
  required,
}: {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  options: DealTypeOption[];
  placeholder?: string;
  error?: string;
  required?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const selected = options.find((o) => String(o.id) === String(value));

  // Map "رهن و اجاره" to "اجاره" for display as requested
  const getDisplayLabel = (opt: DealTypeOption) => {
    if (opt.displayName === "رهن و اجاره") return "اجاره";
    return opt.displayName;
  };

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

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
              <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-violet-400 to-purple-500 flex items-center justify-center flex-shrink-0">
                <Tag size={12} className="text-white" />
              </div>
              <span className="flex-1 font-medium truncate text-right">{getDisplayLabel(selected)}</span>
            </>
          ) : (
            <span className="flex-1 text-muted-foreground text-right">{placeholder || "انتخاب نوع معامله"}</span>
          )}
          <ChevronDown size={14} className={cx("text-muted-foreground transition-transform flex-shrink-0", open && "rotate-180")} />
        </button>

        {open && (
          <div className="absolute z-50 w-full mt-1 bg-card rounded-xl border border-border shadow-lg overflow-hidden">
            <div className="max-h-60 overflow-y-auto py-1">
              {options.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">نوع معامله‌ای یافت نشد</p>
              ) : (
                options.map((opt) => (
                  <button
                    key={String(opt.id)}
                    type="button"
                    onClick={() => {
                      onChange(String(opt.id));
                      setOpen(false);
                    }}
                    className={cx(
                      "w-full flex items-center gap-3 px-3 py-2.5 text-right transition-colors",
                      String(value) === String(opt.id) ? "bg-secondary" : "hover:bg-secondary/50"
                    )}
                  >
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-400 to-purple-500 flex items-center justify-center flex-shrink-0">
                      <Tag size={14} className="text-white" />
                    </div>
                    <div className="flex-1 min-w-0 text-right">
                      <p className="text-sm font-medium truncate">{getDisplayLabel(opt)}</p>
                      {opt.name && <p className="text-xs text-muted-foreground">{opt.name}</p>}
                    </div>
                    {String(value) === String(opt.id) && <Check size={13} className="text-primary flex-shrink-0" />}
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

export { DealTypeListCombobox };
