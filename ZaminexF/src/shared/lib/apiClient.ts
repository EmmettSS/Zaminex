// =============================================================================
//  API Client (extracted exactly from App.tsx)
// =============================================================================

// A CSRF rejection is a session/plumbing problem, not a data problem. DRF
// reports it as an English `detail` and the plain CSRF middleware answers with
// an HTML page, so without this the user is shown either English text or the
// caller's generic fallback ("خطا در اضافه کردن شهر") and has no idea the fix
// is simply to reload. Detected here, once, for every caller.
const CSRF_ERROR_MESSAGE =
  "نشست شما منقضی شده است. لطفاً صفحه را تازه‌سازی کنید و دوباره تلاش کنید.";

const isCsrfDetail = (value: unknown): boolean =>
  typeof value === "string" &&
  (value.startsWith("CSRF Failed") || value.includes("CSRF verification failed"));

// The API answers an expired session with the same 403 it uses for a genuine
// permission denial, and every message is translated to Persian, so the text
// cannot be used to tell them apart. The backend therefore also returns a
// stable `code` (see apps/common/exceptions.py) — that is what we switch on.
const SESSION_EXPIRED_CODE = "not_authenticated";
const SESSION_EXPIRED_MESSAGE =
  "نشست شما پایان یافته است. برای ادامه دوباره وارد شوید.";

/** True when the response says "you are not signed in (any more)". */
const isSessionExpired = (data: unknown): boolean =>
  !!data &&
  typeof data === "object" &&
  (data as { code?: unknown }).code === SESSION_EXPIRED_CODE;

let sessionExpiryHandler: (() => void) | null = null;

// Whether this page was served to a signed-in user.
//
// A 403 `not_authenticated` only means "your session ended" when there *was*
// a session. On a public page — the login screen above all — it is the normal,
// expected answer for any authenticated endpoint, and escalating it to the
// expiry flow makes the login page redirect to itself in a loop.
//
// The value is published once at bootstrap from the server-rendered
// `initialData.isAuthenticated` (see src/main.tsx), so it is known before the
// first request leaves the page and no call site has to opt out by hand.
let sessionAuthenticated = false;

/**
 * Declare whether the current page belongs to a signed-in user.
 *
 * Called once from the entry point. Until it is called the app is treated as
 * anonymous, which is the safe default: at worst an expiry goes unreported,
 * never the other way round.
 */
const setSessionAuthenticated = (value: boolean) => {
  sessionAuthenticated = Boolean(value);
};

/**
 * Register what should happen when the API reports the session as gone.
 *
 * The app installs a handler that warns the user and sends them back to the
 * login page. Keeping it here means every caller gets the behaviour without
 * repeating the check, and the module stays free of UI imports.
 */
const onSessionExpired = (handler: (() => void) | null) => {
  sessionExpiryHandler = handler;
};

// Fired at most once: a dashboard can have several requests in flight and all
// of them fail together, which must not queue up several redirects.
let sessionExpiryNotified = false;

// Set while an intentional logout is in flight. The POST to /accounts/logout/
// destroys the server-side session before the browser navigates away, so every
// background poll that completes in that window (notifications, etc.) would
// otherwise come back as a 403 "not_authenticated" and re-trigger the generic
// "session ended" flow — which schedules its own redirect to the login page and
// is exactly what caused the login page to keep reloading after logout.
// While this flag is on those 403s are the expected consequence of a logout we
// initiated ourselves, so they are reported to the caller but never escalated.
let intentionalLogoutInProgress = false;

const beginIntentionalLogout = () => {
  intentionalLogoutInProgress = true;
};

const notifySessionExpired = () => {
  // A logout we started is not an expired session — do not fire the handler.
  if (intentionalLogoutInProgress) return;
  // Neither is a 403 on a page that never had a session. The login screen
  // renders inside the same SPA bundle, so requests meant for the dashboard
  // can still reach the network there; answering them with the expiry flow
  // would reload the login page every couple of seconds.
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

  // A FormData body must NOT carry an explicit Content-Type. The browser has
  // to set it itself so it can append the multipart boundary; forcing
  // "application/json" (or even "multipart/form-data" without a boundary)
  // leaves the server unable to parse the request.
  //
  // Honouring that here is what lets the file-upload call sites — consultant
  // avatars and the property gallery — go through apiFetch and inherit the
  // CSRF retry below, instead of each hand-rolling its own fetch().
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

  // DRF's SessionAuthentication enforces CSRF on writes itself. When the
  // browser's csrftoken cookie is missing or stale (the session cookie stays
  // valid), every write comes back as 403 {"detail": "CSRF Failed: …"} — this
  // is the error the district management showed when adding a city. Recover by
  // refreshing the cookie through a CSRF-issuing GET and retrying exactly
  // once. Genuine permission 403s keep their own detail and pass through.
  const isCsrfRejection = async (res: Response): Promise<boolean> => {
    const contentType = res.headers.get("content-type") || "";
    // Non-DRF endpoints are protected by the CSRF middleware, which answers
    // with a raw HTML page rather than JSON.
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

  // A 403 that survived the retry may mean the session itself is gone (the tab
  // was left open past the 12-hour idle timeout, or the user logged out in
  // another tab). That is not something the caller can fix, so it is handled
  // centrally here rather than in each screen's error branch.
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

/**
 * Turn a DRF error payload into a single Persian sentence.
 *
 * DRF reports validation errors keyed by field — `{"province": ["این مقدار
 * لازم است."]}` — and nests them arbitrarily deep for related serializers.
 * Flattening only the top level (the previous behaviour) turned any nested or
 * non-string value into "[object Object]", and a payload keyed by a field the
 * caller did not anticipate was dropped entirely in favour of the fallback.
 */
const apiErrorMessage = (data: any, fallback: string): string => {
  if (data == null) return fallback;

  if (typeof data === "string") {
    return isCsrfDetail(data) ? CSRF_ERROR_MESSAGE : data.trim() || fallback;
  }

  if (typeof data !== "object") return fallback;

  // Reported before the generic walk so the user is told their session ended
  // rather than the literal "credentials were not provided".
  if (isSessionExpired(data)) return SESSION_EXPIRED_MESSAGE;

  if (isCsrfDetail((data as any).detail)) return CSRF_ERROR_MESSAGE;

  // Keys that are metadata, not something to read out to the user. `code` is
  // the machine-readable discriminator the API sends next to `detail`; without
  // this it would be concatenated onto the message as "… / permission_denied".
  const METADATA_KEYS = new Set(["code"]);

  // Collect every leaf string, keeping the order the server sent them in and
  // guarding against a cyclic payload.
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
