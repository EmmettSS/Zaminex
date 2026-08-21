import { ChevronDown, Search, Check, SlidersHorizontal, Zap } from "lucide-react";
import React, { useState, useEffect, useRef, useMemo } from "react";
import { cx } from "../../lib/utils";
import { fuzzyFilter } from "../../lib/fuzzySearch";

type AttributeOption = {
  id: number;
  displayName: string;
  name?: string;
  dataType?: string;
  isCore?: boolean;
  isFacility?: boolean;
};

function AttributeCombobox({
  value,
  onChange,
  attributes = [],
  placeholder,
  error,
}: {
  value: string;
  onChange: (v: string) => void;
  attributes?: AttributeOption[];
  placeholder?: string;
  error?: string;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(0);

  const filtered = useMemo(() => {
    return fuzzyFilter(
      attributes,
      q,
      (a) => `${a.displayName} ${a.name || ""}`
    );
  }, [attributes, q]);

  const selected = attributes.find((a) => String(a.id) === String(value));

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
      onChange(String(filtered[focused].id));
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
    <div className="flex flex-col gap-1.5 flex-1" ref={ref}>
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
              <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-violet-400 to-purple-500 flex items-center justify-center flex-shrink-0">
                {selected.isFacility ? <Zap size={12} className="text-white" /> : <SlidersHorizontal size={12} className="text-white" />}
              </div>
              <span className="flex-1 font-medium truncate text-right">{selected.displayName}</span>
              {selected.isCore && (
                <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">ثابت</span>
              )}
            </>
          ) : (
            <span className="flex-1 text-muted-foreground text-right">{placeholder || "انتخاب ویژگی"}</span>
          )}
          <ChevronDown size={14} className={cx("text-muted-foreground transition-transform flex-shrink-0", open && "rotate-180")} />
        </button>

        {open && (
          <div className="absolute z-50 w-full mt-1 bg-card rounded-xl border border-border shadow-lg overflow-hidden">
            <div className="p-2 border-b border-border">
              <div className="relative">
                <Search size={13} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  ref={inputRef}
                  value={q}
                  onChange={(e) => {
                    setQ(e.target.value);
                    setFocused(0);
                  }}
                  onKeyDown={handleKey}
                  placeholder="جستجوی ویژگی…"
                  className="w-full pr-8 pl-3 py-2 text-sm bg-secondary rounded-lg outline-none placeholder:text-muted-foreground"
                />
              </div>
            </div>

            <div className="max-h-60 overflow-y-auto py-1">
              {filtered.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">
                  ویژگی‌ای یافت نشد
                </p>
              ) : (
                filtered.map((attr, i) => (
                  <button
                    key={attr.id}
                    type="button"
                    onMouseEnter={() => setFocused(i)}
                    onClick={() => {
                      onChange(String(attr.id));
                      setOpen(false);
                    }}
                    className={cx(
                      "w-full flex items-center gap-3 px-3 py-2.5 text-right transition-colors",
                      i === focused ? "bg-secondary" : "hover:bg-secondary/50"
                    )}
                  >
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-400 to-purple-500 flex items-center justify-center flex-shrink-0">
                      {attr.isFacility ? <Zap size={14} className="text-white" /> : <SlidersHorizontal size={14} className="text-white" />}
                    </div>
                    <div className="flex-1 min-w-0 text-right">
                      <p className="text-sm font-medium truncate">{hl(attr.displayName)}</p>
                      <p className="text-xs text-muted-foreground truncate">
                        {attr.name} {attr.dataType ? `· ${attr.dataType}` : ""} {attr.isCore ? "· ثابت" : ""}
                      </p>
                    </div>
                    {String(value) === String(attr.id) && <Check size={13} className="text-primary flex-shrink-0" />}
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

export { AttributeCombobox };
