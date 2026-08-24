import React, { useEffect, useState } from "react";
import { Sparkles, Check, X, Loader2, AlertTriangle, RefreshCw } from "lucide-react";
import { Card } from "./Card";
import { Btn } from "./Btn";
import { apiFetch, readJson, apiErrorMessage } from "../../lib/apiClient";

export type AIDescription = {
  positives: string[];
  negatives: string[];
  summary: string;
};

/**
 * Reusable "توصیف هوش مصنوعی" card, styled like the static AI sections.
 * Renders three positives, three negatives and a summary (Digikala-style).
 * When AI is not configured it shows a graceful "خالی" state.
 */
function AIDescription({
  title,
  fetchFn,
  className,
  reloadKey,
}: {
  title: string;
  /** Async function returning the AI description (or null when unavailable). */
  fetchFn: () => Promise<AIDescription | null>;
  className?: string;
  /** Change this when the entity changes so we never show another record's text. */
  reloadKey?: string | number;
}) {
  const [data, setData] = useState<AIDescription | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFn();
      if (result === null) {
        setUnavailable(true);
        setData(null);
      } else {
        setUnavailable(false);
        setData(result);
      }
    } catch (e: any) {
      setError(e?.message || "خطا در دریافت توصیف");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadKey]);

  return (
    <Card className={`p-5 border-2 border-purple-500/40 bg-gradient-to-br from-purple-50/60 via-white to-purple-50/30 shadow-md shadow-purple-500/10 relative overflow-hidden ${className || ""}`}>
      <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/5 rounded-full blur-2xl pointer-events-none" />
      <div className="flex items-center gap-2.5 mb-3">
        <div className="w-8 h-8 rounded-xl bg-purple-100 text-purple-600 flex items-center justify-center flex-shrink-0 shadow-sm border border-purple-200">
          <Sparkles size={16} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-bold text-foreground">{title}</h3>
            <span className="text-[10px] font-semibold bg-purple-100 text-purple-700 border border-purple-200 px-2 py-0.5 rounded-full">
              هوش مصنوعی زمینکس
            </span>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground bg-white/80 rounded-xl p-3.5 border border-purple-100">
          <Loader2 size={14} className="animate-spin text-purple-600" />در حال تحلیل…
        </div>
      ) : unavailable ? (
        <p className="text-xs text-muted-foreground leading-relaxed bg-white/80 rounded-xl p-3.5 border border-purple-100">
          برای این بخش هوش مصنوعی فعال نشده است. لطفاً API را در پنل مدیریت پیکربندی کنید.
        </p>
      ) : error ? (
        <div className="flex items-center justify-between gap-3 bg-white/80 rounded-xl p-3.5 border border-red-100">
          <div className="flex items-center gap-2 text-xs text-red-600">
            <AlertTriangle size={14} />{error}
          </div>
          <Btn variant="secondary" size="xs" onClick={load}><RefreshCw size={11} />تلاش مجدد</Btn>
        </div>
      ) : data ? (
        <div className="space-y-3">
          {data.summary && (
            <p className="text-xs text-foreground/90 leading-relaxed bg-white/80 backdrop-blur-sm border border-purple-100 rounded-xl p-3.5 shadow-sm">
              {data.summary}
            </p>
          )}

          {data.positives.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold text-emerald-700 mb-1.5">نکات مثبت</p>
              <ul className="space-y-1.5">
                {data.positives.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-foreground/90 bg-emerald-50/70 border border-emerald-100 rounded-lg px-2.5 py-1.5">
                    <Check size={13} className="text-emerald-600 flex-shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {data.negatives.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold text-red-700 mb-1.5">نکات منفی</p>
              <ul className="space-y-1.5">
                {data.negatives.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-foreground/90 bg-red-50/70 border border-red-100 rounded-lg px-2.5 py-1.5">
                    <X size={13} className="text-red-500 flex-shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : null}
    </Card>
  );
}

export { AIDescription };

/** Build an AIDescription fetch function for an entity via the AI endpoint. */
export function makeAIDescriptionFetcher(
  entity: "consultant" | "property",
  id: string | number,
  csrfToken?: string
): () => Promise<AIDescription | null> {
  return async () => {
    const res = await apiFetch(
      `/common/api/ai/${entity}/${id}/`,
      { method: "POST" },
      csrfToken
    );
    // 503 means AI is not configured → treat as unavailable (null), not error.
    if (res.status === 503) return null;
    if (!res.ok) {
      const payload = await readJson(res);
      throw new Error(apiErrorMessage(payload, "خطا در دریافت توصیف"));
    }
    const payload = await readJson(res);
    return {
      positives: Array.isArray(payload.positives) ? payload.positives : [],
      negatives: Array.isArray(payload.negatives) ? payload.negatives : [],
      summary: typeof payload.summary === "string" ? payload.summary : "",
    };
  };
}
