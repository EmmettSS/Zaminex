import React, { useEffect, useLayoutEffect, useRef } from "react";
import { cx, formatPriceToPersianWords, formatPriceWithCommas, normalizePriceDigits } from "../../lib/utils";
import { Building2, LayoutDashboard, FileText, CheckSquare, Users, BarChart3, Settings, Bell, Search, LogOut, Plus, ChevronLeft, ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, MoreHorizontal, MapPin, Eye, Edit2, Trash2, Archive, Phone, Mail, Calendar, TrendingUp, Activity, Command, Star, List, LayoutGrid, Download, Shield, User, Lock, Key, RefreshCw, Circle, Zap, Target, Award, Upload, Check, AlertTriangle, Info, XCircle, Loader2, CircleCheck, TriangleAlert, Columns, Send, BellRing, X, ChevronUp, SlidersHorizontal, ArrowUpRight, Layers, MessageSquare, Sparkles, GripVertical, MoreVertical, Building, History, Flame, Image } from "lucide-react";
import { BadgeV } from "../../lib/types";

const useIsomorphicLayoutEffect = typeof window !== "undefined" ? useLayoutEffect : useEffect;

function caretPositionForDigitCount(formatted: string, digitCount: number): number {
  if (digitCount <= 0) return 0;
  let seen = 0;
  for (let i = 0; i < formatted.length; i++) {
    if (/\d/.test(formatted[i])) {
      seen++;
      if (seen === digitCount) {
        return i + 1;
      }
    }
  }
  return formatted.length;
}

function Input({ label, type = "text", placeholder, value, onChange, icon, error, required, textarea, rows, readOnly, isPrice }: {
  label?: string; type?: string; placeholder?: string; value: string;
  onChange: (v: string) => void; icon?: React.ReactNode; error?: string;
  required?: boolean; textarea?: boolean; rows?: number; readOnly?: boolean;
  isPrice?: boolean;
}) {
  const cls = "w-full rounded-xl border border-border bg-input-background px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground outline-none transition-all focus:ring-2 focus:ring-ring focus:border-primary";
  const inputRef = useRef<HTMLInputElement | null>(null);
  const lastKeyRef = useRef<string | null>(null);
  const pendingCaretRef = useRef<number | null>(null);

  const displayValue = isPrice ? formatPriceWithCommas(value) : value;
  const priceWords = isPrice ? formatPriceToPersianWords(value) : "";

  useIsomorphicLayoutEffect(() => {
    if (!isPrice || pendingCaretRef.current === null || !inputRef.current) return;
    const pos = pendingCaretRef.current;
    pendingCaretRef.current = null;
    try {
      inputRef.current.setSelectionRange(pos, pos);
    } catch {
      // ignore if input does not support selection range
    }
  }, [displayValue, isPrice]);

  const handlePriceKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    lastKeyRef.current = e.key;
    if (e.key === "-" || e.key === "−" || e.key === "+" || e.key === "e" || e.key === "E" || e.key === ".") {
      e.preventDefault();
      return;
    }
    if (e.key === "0" || e.key === "۰" || e.key === "٠") {
      const selStart = e.currentTarget.selectionStart ?? 0;
      if (!displayValue || selStart === 0) {
        e.preventDefault();
      }
    }
  };

  const handlePricePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const pasted = e.clipboardData?.getData("text") ?? "";
    if (/[-−]/.test(pasted) || !normalizePriceDigits(pasted)) {
      e.preventDefault();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!isPrice) {
      onChange(e.target.value);
      return;
    }
    let rawInput = e.target.value;
    let sel = e.target.selectionStart ?? rawInput.length;

    if (/[-−]/.test(rawInput)) {
      onChange(displayValue ? normalizePriceDigits(displayValue) : "");
      return;
    }

    if (
      rawInput.length === displayValue.length - 1 &&
      normalizePriceDigits(rawInput) === normalizePriceDigits(displayValue)
    ) {
      if (lastKeyRef.current === "Backspace" && sel > 0) {
        rawInput = rawInput.slice(0, sel - 1) + rawInput.slice(sel);
        sel -= 1;
      } else if (lastKeyRef.current === "Delete" && sel < rawInput.length) {
        rawInput = rawInput.slice(0, sel) + rawInput.slice(sel + 1);
      }
    }

    const digitsBeforeCaret = normalizePriceDigits(rawInput.slice(0, sel)).length;
    const nextDigits = normalizePriceDigits(rawInput);
    const nextFormatted = formatPriceWithCommas(nextDigits);
    pendingCaretRef.current = caretPositionForDigitCount(nextFormatted, digitsBeforeCaret);
    onChange(nextDigits);
  };

  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-sm font-medium text-foreground">{label}{required && <span className="text-primary mr-1">*</span>}</label>}
      <div className="relative">
        {icon && <span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground">{icon}</span>}
        {textarea
          ? <textarea value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} rows={rows ?? 4} className={cx(cls, "resize-none")} readOnly={readOnly} />
          : <input
              ref={inputRef}
              type={isPrice ? "text" : type}
              inputMode={isPrice ? "numeric" : undefined}
              placeholder={placeholder}
              value={displayValue}
              onKeyDown={isPrice ? handlePriceKeyDown : undefined}
              onPaste={isPrice ? handlePricePaste : undefined}
              onChange={handleInputChange}
              className={cx(cls, icon && "pr-10")}
              readOnly={readOnly}
            />}
      </div>
      {isPrice && priceWords && (
        <p className="text-xs text-muted-foreground/80 pr-1 leading-relaxed">{priceWords}</p>
      )}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

export { Input };

