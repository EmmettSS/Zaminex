import { ChevronDown, Search, Check, Settings } from "lucide-react";
import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { cx } from "../../lib/utils";
import { fuzzyFilter } from "../../lib/fuzzySearch";
import { ActivityLogUserOption } from "../../lib/types";

type Item = {
  id: string;
  name: string;
  count?: number;
  system?: boolean;
};

function ActivityUserCombobox({
  value,
  onChange,
  users,
  systemCount,
  loading = false,
}: {
  value: string;
  onChange: (v: string) => void;
  users: ActivityLogUserOption[];
  systemCount: number;
  loading?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(0);

  const items: Item[] = useMemo(() => {
    const out: Item[] = [{ id: "all", name: "همه کاربران" }];
    if (systemCount > 0) out.push({ id: "system", name: "سیستم", count: systemCount, system: true });
    for (const u of users) out.push({ id: String(u.id), name: u.name, count: u.logCount });
    return out;
  }, [users, systemCount]);

  const selected = useMemo(() => items.find((i) => i.id === String(value)), [items, value]);
  const filtered = useMemo(
    () =>
      String(value) === "all"
        ? items
        : fuzzyFilter(items, q, (i) => i.name),
    [items, q, value]
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

  const handleKey = useCallback(
    (e: React.KeyboardEvent) => {
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
    },
    [filtered, focused, onChange]
  );

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cx(
          "w-full px-3 py-2 rounded-xl border border-border bg-white text-right text-xs font-medium flex items-center justify-between transition-colors hover:border-primary/30"
        )}
      >
        <span className={cx("flex-1 truncate", selected?.system && "flex items-center gap-1.5")}>
          {selected?.system && <Settings size={12} className="text-muted-foreground flex-shrink-0" />}
          {loading ? "در حال بارگذاری…" : selected ? selected.name : "همه کاربران"}
        </span>
        {selected && selected.count != null && (
          <span className="text-[10px] text-muted-foreground flex-shrink-0 ml-2">
            {selected.count.toLocaleString("fa-IR")}
          </span>
        )}
        <ChevronDown
          size={13}
          className={cx("text-muted-foreground transition-transform flex-shrink-0 ml-1", open && "rotate-180")}
        />
      </button>

      {open && (
        <div className="absolute z-50 w-full mt-1 bg-card rounded-xl border border-border shadow-lg overflow-hidden">
          <div className="p-2 border-b border-border">
            <div className="relative">
              <Search size={12} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                ref={inputRef}
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setFocused(0);
                }}
                onKeyDown={handleKey}
                placeholder="جستجوی نام کاربر…"
                className="w-full pr-7 pl-3 py-1.5 text-xs bg-secondary rounded-lg outline-none placeholder:text-muted-foreground"
              />
            </div>
          </div>
          <div className="max-h-56 overflow-y-auto py-1">
            {filtered.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-4">موردی یافت نشد</p>
            ) : (
              filtered.map((it, i) => (
                <button
                  key={it.id}
                  type="button"
                  onMouseEnter={() => setFocused(i)}
                  onClick={() => {
                    onChange(it.id);
                    setOpen(false);
                  }}
                  className={cx(
                    "w-full flex items-center justify-between gap-2 px-3 py-2 text-right transition-colors",
                    i === focused ? "bg-secondary" : "hover:bg-secondary/50"
                  )}
                >
                  <span className="flex items-center gap-1.5 min-w-0 flex-1">
                    {it.system && <Settings size={12} className="text-muted-foreground flex-shrink-0" />}
                    <span className="truncate text-xs font-medium">{it.name}</span>
                  </span>
                  <span className="flex items-center gap-1.5 flex-shrink-0">
                    {it.count != null && (
                      <span className="text-[10px] text-muted-foreground">
                        {it.count.toLocaleString("fa-IR")}
                      </span>
                    )}
                    {String(value) === it.id && <Check size={12} className="text-primary" />}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export { ActivityUserCombobox };
