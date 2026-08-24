import React, { useState, useRef, useEffect } from "react";
import { ChevronDown, DollarSign, X } from "lucide-react";
import { cx } from "../../lib/utils";

type PriceRange = { min: string; max: string };

function PriceRangeFilter({
  label,
  placeholder,
  value,
  onChange,
}: {
  label?: string;
  placeholder?: string;
  value: PriceRange;
  onChange: (v: PriceRange) => void;
}) {
  const [open, setOpen] = useState(false);
  const [localMin, setLocalMin] = useState(value.min);
  const [localMax, setLocalMax] = useState(value.max);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLocalMin(value.min);
    setLocalMax(value.max);
  }, [value.min, value.max]);

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const hasValue = value.min || value.max;
  const display = hasValue
    ? `${value.min ? `${Number(value.min).toLocaleString("fa-IR")} از` : ""} ${value.max ? `${Number(value.max).toLocaleString("fa-IR")} تا` : ""}`.trim() || label
    : placeholder || label;

  const apply = () => {
    onChange({ min: localMin, max: localMax });
    setOpen(false);
  };

  const clear = () => {
    setLocalMin("");
    setLocalMax("");
    onChange({ min: "", max: "" });
    setOpen(false);
  };

  return (
    <div className="flex flex-col gap-1.5" ref={ref}>
      {label && <label className="text-xs font-medium text-foreground">{label}</label>}
      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className={cx(
            "w-full flex items-center gap-2 rounded-xl border border-border bg-input-background px-3 py-2.5 text-sm text-right transition-all outline-none focus:ring-2 focus:ring-ring",
            open && "border-primary ring-2 ring-ring",
            hasValue && "border-primary/50 bg-primary/5"
          )}
        >
          <DollarSign size={13} className="text-muted-foreground flex-shrink-0" />
          <span className={cx("flex-1 truncate", hasValue ? "text-foreground font-medium" : "text-muted-foreground")}>
            {hasValue ? `${label}: ${value.min ? `از ${Number(value.min).toLocaleString("fa-IR")}` : ""} ${value.max ? `تا ${Number(value.max).toLocaleString("fa-IR")}` : ""}`.trim() : placeholder || label}
          </span>
          {hasValue ? (
            <span
              onClick={(e) => {
                e.stopPropagation();
                clear();
              }}
              className="p-0.5 hover:bg-secondary rounded-full"
            >
              <X size={12} className="text-muted-foreground" />
            </span>
          ) : null}
          <ChevronDown size={13} className={cx("text-muted-foreground transition-transform flex-shrink-0", open && "rotate-180")} />
        </button>

        {open && (
          <div className="absolute z-50 w-64 mt-1 bg-card rounded-xl border border-border shadow-lg overflow-hidden p-3">
            <p className="text-xs font-semibold mb-2">{label || placeholder}</p>
            <div className="flex flex-col gap-2">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-foreground">حداقل (تومان)</label>
                <input
                  type="number"
                  value={localMin}
                  onChange={(e) => setLocalMin(e.target.value)}
                  placeholder="حداقل"
                  className="w-full rounded-xl border border-border bg-input-background px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-foreground">حداکثر (تومان)</label>
                <input
                  type="number"
                  value={localMax}
                  onChange={(e) => setLocalMax(e.target.value)}
                  placeholder="حداکثر"
                  className="w-full rounded-xl border border-border bg-input-background px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div className="flex gap-2 mt-2">
                <button
                  onClick={clear}
                  className="flex-1 py-2 text-xs rounded-xl border border-border bg-white hover:bg-secondary transition-colors"
                >
                  پاک کردن
                </button>
                <button
                  onClick={apply}
                  className="flex-1 py-2 text-xs rounded-xl bg-primary text-white hover:bg-primary/90 transition-colors"
                >
                  اعمال
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export { PriceRangeFilter };
