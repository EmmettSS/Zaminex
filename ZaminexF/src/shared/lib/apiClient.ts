const CSRF_ERROR_MESSAGE =
  "نشست شما منقضی شده است. لطفاً صفحه را تازه‌سازی کنید و دوباره تلاش کنید.";

const isCsrfDetail = (value: unknown): boolean =>
  typeof value === "string" &&
  (value.startsWith("CSRF Failed") || value.includes("CSRF verification failed"));

const SESSION_EXPIRED_CODE = "not_authenticated";
const SESSION_EXPIRED_MESSAGE =
  "نشست شما پایان یافته است. برای ادامه دوباره وارد شوید.";

const isSessionExpired = (data: unknown): boolean =>
  !!data &&
  typeof data === "object" &&
  (data as { code?: unknown }).code === SESSION_EXPIRED_CODE;

let sessionExpiryHandler: (() => void) | null = null;

let sessionAuthenticated = false;

const setSessionAuthenticated = (value: boolean) => {
  sessionAuthenticated = Boolean(value);
};

const onSessionExpired = (handler: (() => void) | null) => {
  sessionExpiryHandler = handler;
};

let sessionExpiryNotified = false;

let intentionalLogoutInProgress = false;

const beginIntentionalLogout = () => {
  intentionalLogoutInProgress = true;
};

const notifySessionExpired = () => {
  if (intentionalLogoutInProgress) return;
  if (!sessionAuthenticated) return;
  if (sessionExpiryNotified) return;
  sessionExpiryNotified = true;
  try {
    sessionExpiryHandler?.();
  } catch {
    // A failing handler must never mask the original API error.
  }
};

const getCsrfToken = (fallback?: string): string => {
  if (typeof document !== "undefined") {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (match && match[1]) {
      return decodeURIComponent(match[1]);
    }
  }
  return fallback || "";
};

const apiFetch = async (url: string, opts: RequestInit = {}, csrfToken?: string) => {
  const method = String(opts.method || "GET").toUpperCase();
  const isWrite = !["GET", "HEAD", "OPTIONS"].includes(method);

  const isFormData =
    typeof FormData !== "undefined" && opts.body instanceof FormData;

  const send = (): Promise<Response> => {
    const headers: Record<string, string> = {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(opts.headers as Record<string, string> | undefined),
    };
    const token = getCsrfToken(csrfToken);
    if (token) headers["X-CSRFToken"] = token;
    return fetch(url, { credentials: "include", ...opts, headers });
  };

  const isCsrfRejection = async (res: Response): Promise<boolean> => {
    const contentType = res.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) return true;
    try {
      const data = await res.clone().json();
      return isCsrfDetail(data?.detail);
    } catch {
      return false;
    }
  };

  let res = await send();

  if (isWrite && res.status === 403 && (await isCsrfRejection(res))) {
    try {
      await fetch("/accounts/login/", {
        method: "GET",
        credentials: "include",
        cache: "no-store",
      });
    } catch {
      // The original response is kept and reported if the refresh fails.
    }
    res = await send();
  }

  if (res.status === 403) {
    try {
      const data = await res.clone().json();
      if (isSessionExpired(data)) notifySessionExpired();
    } catch {
      // Not a JSON body — nothing to inspect.
    }
  }

  return res;
};

const readJson = async (res: Response) => {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`خطای سرور (کد ${res.status}). لطفاً دوباره تلاش کنید.`);
  }
};

const apiErrorMessage = (data: any, fallback: string): string => {
  if (data == null) return fallback;

  if (typeof data === "string") {
    return isCsrfDetail(data) ? CSRF_ERROR_MESSAGE : data.trim() || fallback;
  }

  if (typeof data !== "object") return fallback;

  if (isSessionExpired(data)) return SESSION_EXPIRED_MESSAGE;

  if (isCsrfDetail((data as any).detail)) return CSRF_ERROR_MESSAGE;

  const METADATA_KEYS = new Set(["code"]);

  const seen = new WeakSet<object>();
  const messages: string[] = [];

  const collect = (value: unknown, depth: number): void => {
    if (value == null || depth > 4 || messages.length >= 4) return;

    if (typeof value === "string") {
      const text = value.trim();
      if (text && !messages.includes(text)) messages.push(text);
      return;
    }

    if (typeof value === "number" || typeof value === "boolean") return;

    if (typeof value === "object") {
      if (seen.has(value as object)) return;
      seen.add(value as object);

      if (Array.isArray(value)) {
        value.forEach((item) => collect(item, depth + 1));
        return;
      }
      Object.entries(value as Record<string, unknown>).forEach(([key, item]) => {
        if (METADATA_KEYS.has(key)) return;
        collect(item, depth + 1);
      });
    }
  };

  try {
    collect(data, 0);
  } catch {
    return fallback;
  }

  if (messages.some(isCsrfDetail)) return CSRF_ERROR_MESSAGE;

  return messages.length ? messages.join(" / ") : fallback;
};

export {
  getCsrfToken,
  apiFetch,
  readJson,
  apiErrorMessage,
  onSessionExpired,
  isSessionExpired,
  beginIntentionalLogout,
  setSessionAuthenticated,
  SESSION_EXPIRED_MESSAGE,
};
