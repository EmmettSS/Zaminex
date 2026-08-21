import React, { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { Calendar, ChevronLeft, ChevronRight } from "lucide-react";
import { cx } from "../../lib/utils";
import {
  toJalaliISO,
  jalaliToGregorianISO,
  formatJalali,
  todayJalali,
  JALALI_MONTHS,
  daysInJalaliMonth,
  firstWeekdayOfJalaliMonth,
} from "../../lib/jdate";

const J_WEEKDAYS = ["ش", "ی", "د", "س", "چ", "پ", "ج"];
const faNum = (n: number) => n.toLocaleString("fa-IR", { useGrouping: false });
const POPOVER_W = 296;

function jalaliKey(jy: number, jm: number, jd: number) {
  return `${jy}-${String(jm).padStart(2, "0")}-${String(jd).padStart(2, "0")}`;
}

/**
 * A Shamsi (Jalali) date picker.
 *
 * Props mirror a native date input: `value` is the Gregorian "YYYY-MM-DD"
 * (what the rest of the app / the API expects), but the calendar shown and the
 * dates the user picks are real Jalali. Selecting a day emits its Gregorian
 * equivalent through `onChange`, so nothing below this component changes.
 */
function JalaliDateInput({
  label,
  value,
  onChange,
  required,
  error,
  placeholder,
  className,
}: {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  error?: string;
  placeholder?: string;
  className?: string;
}) {
  const t = todayJalali();
  const [open, setOpen] = useState(false);
  const [viewYear, setViewYear] = useState(t.jy);
  const [viewMonth, setViewMonth] = useState(t.jm);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  const placePopover = useCallback(() => {
    const el = btnRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const gap = 6;
    const height = 340;
    const spaceBelow = window.innerHeight - r.bottom;
    const openUp = spaceBelow < height && r.top > spaceBelow;
    const top = openUp ? Math.max(8, r.top - height - gap) : r.bottom + gap;
    let left = r.right - POPOVER_W;
    if (left < 8) left = 8;
    if (left + POPOVER_W > window.innerWidth - 8) left = window.innerWidth - POPOVER_W - 8;
    setPos({ top, left });
  }, []);

  useEffect(() => {
    if (value) {
      const parts = toJalaliISO(value).split("-");
      if (parts.length === 3) {
        setViewYear(parseInt(parts[0], 10));
        setViewMonth(parseInt(parts[1], 10));
      }
    }
  }, [value, open]);

  useEffect(() => {
    if (!open) return;
    placePopover();
    const onScroll = () => placePopover();
    window.addEventListener("resize", onScroll);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      window.removeEventListener("resize", onScroll);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open, placePopover]);

  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => {
      const target = e.target as Node;
      if (rootRef.current?.contains(target)) return;
      if (popRef.current?.contains(target)) return;
      setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", h);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", h);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const selected = value ? toJalaliISO(value) : "";
  const daysInMonth = daysInJalaliMonth(viewYear, viewMonth);
  const offset = firstWeekdayOfJalaliMonth(viewYear, viewMonth);
  const todayKey = jalaliKey(t.jy, t.jm, t.jd);

  const prevMonth = () => {
    if (viewMonth === 1) {
      setViewMonth(12);
      setViewYear(viewYear - 1);
    } else setViewMonth(viewMonth - 1);
  };
  const nextMonth = () => {
    if (viewMonth === 12) {
      setViewMonth(1);
      setViewYear(viewYear + 1);
    } else setViewMonth(viewMonth + 1);
  };

  const pick = (day: number) => {
    const g = jalaliToGregorianISO(jalaliKey(viewYear, viewMonth, day));
    onChange(g);
    setOpen(false);
  };

  const pickToday = () => {
    const g = jalaliToGregorianISO(todayKey);
    onChange(g);
    setOpen(false);
  };

  const totalCells = Math.ceil((offset + daysInMonth) / 7) * 7;
  const cells = Array.from({ length: totalCells }, (_, i) => {
    const day = i - offset + 1;
    return day >= 1 && day <= daysInMonth ? day : null;
  });

  const calendar = open && pos && typeof document !== "undefined"
    ? createPortal(
        <div
          ref={popRef}
          role="dialog"
          aria-label="تقویم شمسی"
          className="fixed z-[80] bg-card rounded-2xl border border-border shadow-2xl overflow-hidden"
          style={{ top: pos.top, left: pos.left, width: POPOVER_W }}
        >
          <div className="flex items-center justify-between gap-2 px-3 py-2.5 border-b border-border">
            <button
              type="button"
              onClick={prevMonth}
              className="w-8 h-8 flex items-center justify-center hover:bg-secondary rounded-xl transition-colors"
              aria-label="ماه قبل"
            >
              <ChevronRight size={16} />
            </button>
            <span className="text-sm font-semibold tabular-nums">
              {JALALI_MONTHS[viewMonth - 1]} {faNum(viewYear)}
            </span>
            <button
              type="button"
              onClick={nextMonth}
              className="w-8 h-8 flex items-center justify-center hover:bg-secondary rounded-xl transition-colors"
              aria-label="ماه بعد"
            >
              <ChevronLeft size={16} />
            </button>
          </div>
          <div className="grid grid-cols-7 px-2 pt-2">
            {J_WEEKDAYS.map((w) => (
              <div key={w} className="h-8 flex items-center justify-center text-[11px] font-semibold text-muted-foreground">
                {w}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-y-0.5 px-2 pb-2">
            {cells.map((d, i) => {
              if (d == null) return <div key={`e${i}`} className="h-9" />;
              const key = jalaliKey(viewYear, viewMonth, d);
              const isSelected = selected === key;
              const isToday = todayKey === key;
              return (
                <button
                  key={d}
                  type="button"
                  onClick={() => pick(d)}
                  className={cx(
                    "h-9 w-9 mx-auto rounded-xl text-[13px] font-medium tabular-nums flex items-center justify-center transition-colors",
                    isSelected
                      ? "bg-primary text-white font-bold shadow-sm"
                      : isToday
                      ? "bg-primary/10 text-primary font-semibold"
                      : "hover:bg-secondary text-foreground"
                  )}
                >
                  {faNum(d)}
                </button>
              );
            })}
          </div>
          <div className="flex items-center justify-between gap-2 px-3 py-2 border-t border-border bg-secondary/30">
            <button
              type="button"
              onClick={pickToday}
              className="px-2.5 py-1 text-[11px] font-medium rounded-lg text-primary hover:bg-primary/10 transition-colors"
            >
              امروز
            </button>
            {!required && (
              <button
                type="button"
                onClick={() => { onChange(""); setOpen(false); }}
                className="px-2.5 py-1 text-[11px] font-medium rounded-lg text-muted-foreground hover:bg-secondary transition-colors"
              >
                پاک کردن
              </button>
            )}
          </div>
        </div>,
        document.body
      )
    : null;

  return (
    <div className="relative space-y-1.5 w-full min-w-[13rem]" ref={rootRef}>
      {label && (
        <label className="block text-xs font-medium text-foreground">
          {label}
          {required && <span className="mr-1 text-destructive">*</span>}
        </label>
      )}
      <button
        ref={btnRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cx(
          "w-full flex items-center justify-between gap-2 text-right rounded-xl border border-border bg-input-background px-3 py-2.5 text-sm transition-all outline-none focus:ring-2 focus:ring-ring",
          open && "border-primary ring-2 ring-ring",
          error && "border-destructive focus:ring-destructive/20",
          className
        )}
      >
        <span className={cx("min-w-0 truncate", value ? "text-foreground font-medium" : "text-muted-foreground")}>
          {value ? formatJalali(value) : placeholder || "انتخاب تاریخ"}
        </span>
        <Calendar size={14} className="flex-shrink-0 text-muted-foreground" />
      </button>
      {calendar}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

export { JalaliDateInput };
