// =============================================================================
//  Jalali (Shamsi) ↔ Gregorian conversion helpers
// =============================================================================
// The database and the API contract stay in Gregorian (the backend's DateFields
// are Gregorian). This module lets the UI present and accept real Shamsi dates
// while everything below the surface keeps working in Gregorian:
//   - convert a Gregorian ISO date ("YYYY-MM-DD") to a Jalali one for display
//   - convert a Jalali date entered by the user back to Gregorian for storage
// The algorithm is the standard jalaali (Kazimierz Borkowski) conversion.
// =============================================================================

// NOTE: the jalaali algorithm needs integer division that truncates toward zero
// (like `~~` in JS), NOT Math.floor, because the math involves negative values.
const div = (a: number, b: number) => Math.trunc(a / b);
const mod = (a: number, b: number) => a - Math.trunc(a / b) * b;

export type JalaliDate = { jy: number; jm: number; jd: number };
export type GregorianDate = { gy: number; gm: number; gd: number };

function jalCal(jy: number): { leap: number; gy: number; march: number } {
  const breaks = [
    -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060,
    2097, 2192, 2262, 2324, 2394, 2456, 3178,
  ];
  const gy = jy + 621;
  let leapJ = -14;
  let jp = breaks[0];
  let jump = 0;
  for (let i = 1; i < breaks.length; i += 1) {
    const jm = breaks[i];
    jump = jm - jp;
    if (jy < jm) break;
    leapJ = leapJ + div(jump, 33) * 8 + div(mod(jump, 33), 4);
    jp = jm;
  }
  let n = jy - jp;
  leapJ = leapJ + div(n, 33) * 8 + div(mod(n, 33) + 3, 4);
  if (mod(jump, 33) === 4 && jump - n === 4) leapJ += 1;
  const leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
  const march = 20 + leapJ - leapG;
  if (jump - n < 6) n = n - jump + div(jump + 4, 33) * 33;
  let leap = mod(mod(n + 1, 33) - 1, 4);
  if (leap === -1) leap = 4;
  return { leap, gy, march };
}

function g2d(gy: number, gm: number, gd: number): number {
  let d =
    div((gy + div(gm - 8, 6) + 100100) * 1461, 4) +
    div(153 * mod(gm + 9, 12) + 2, 5) +
    gd -
    34840408;
  d = d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752;
  return d;
}

function d2g(jdn: number): GregorianDate {
  let j = 4 * jdn + 139361631;
  j = j + div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
  const i = div(mod(j, 1461), 4) * 5 + 308;
  const gd = div(mod(i, 153), 5) + 1;
  const gm = mod(div(i, 153), 12) + 1;
  const gy = div(j, 1461) - 100100 + div(8 - gm, 6);
  return { gy, gm, gd };
}

function j2d(jy: number, jm: number, jd: number): number {
  const r = jalCal(jy);
  return (
    g2d(r.gy, 3, r.march) +
    (jm - 1) * 31 -
    div(jm, 7) * (jm - 7) +
    jd -
    1
  );
}

function d2j(jdn: number): JalaliDate {
  const gy = d2g(jdn).gy;
  let jy = gy - 621;
  const r = jalCal(jy);
  const jdn1f = g2d(gy, 3, r.march);
  let jd: number;
  let jm: number;
  let k = jdn - jdn1f;
  if (k >= 0) {
    if (k <= 185) {
      jm = 1 + div(k, 31);
      jd = mod(k, 31) + 1;
      return { jy, jm, jd };
    }
    k -= 186;
  } else {
    jy -= 1;
    k += 179;
    if (r.leap === 1) k += 1;
  }
  jm = 7 + div(k, 30);
  jd = mod(k, 30) + 1;
  return { jy, jm, jd };
}

function g2j(gy: number, gm: number, gd: number): JalaliDate {
  return d2j(g2d(gy, gm, gd));
}

function j2g(jy: number, jm: number, jd: number): GregorianDate {
  return d2g(j2d(jy, jm, jd));
}

const pad = (n: number) => String(n).padStart(2, "0");

/** Persian digits without thousands grouping — years like ۱۴۰۵ must stay ۱۴۰۵, not ۱٬۴۰۵. */
const faNum = (n: number) => n.toLocaleString("fa-IR", { useGrouping: false });

export const JALALI_MONTHS = [
  "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
];

/** Parse "YYYY-MM-DD" (or "YYYY/MM/DD") into parts, else null. */
export function parseGregorianISO(v?: string | null): GregorianDate | null {
  if (!v) return null;
  const m = String(v).match(/^(\d{4})[-/](\d{2})[-/](\d{2})/);
  if (!m) return null;
  const gy = parseInt(m[1], 10);
  const gm = parseInt(m[2], 10);
  const gd = parseInt(m[3], 10);
  if (gy < 1 || gm < 1 || gm > 12 || gd < 1 || gd > 31) return null;
  return { gy, gm, gd };
}

/** Gregorian "YYYY-MM-DD" → Jalali object. */
export function gregorianToJalali(v?: string | null): JalaliDate | null {
  const g = parseGregorianISO(v);
  if (!g) return null;
  return g2j(g.gy, g.gm, g.gd);
}

/** Today (now) as a Jalali object. */
export function todayJalali(): JalaliDate {
  const n = new Date();
  return g2j(n.getFullYear(), n.getMonth() + 1, n.getDate());
}

/** Gregorian "YYYY-MM-DD" → Jalali "YYYY-MM-DD" string (for display). */
export function toJalaliISO(v?: string | null): string {
  const j = gregorianToJalali(v);
  if (!j) return "";
  return `${j.jy}-${pad(j.jm)}-${pad(j.jd)}`;
}

/** Jalali "YYYY-MM-DD" → Gregorian "YYYY-MM-DD" string (for storage/API). */
export function jalaliToGregorianISO(v?: string | null): string {
  if (!v) return "";
  const m = String(v).match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})/);
  if (!m) return "";
  const jy = parseInt(m[1], 10);
  const jm = parseInt(m[2], 10);
  const jd = parseInt(m[3], 10);
  if (jy < 1 || jm < 1 || jm > 12 || jd < 1 || jd > 31) return "";
  if (jd > daysInJalaliMonth(jy, jm)) return "";
  const g = j2g(jy, jm, jd);
  return `${g.gy}-${pad(g.gm)}-${pad(g.gd)}`;
}

/** Days in a given Jalali month (1–12). */
export function daysInJalaliMonth(jy: number, jm: number): number {
  if (jm <= 6) return 31;
  if (jm < 12) return 30;
  // In the jalaali convention a Jalali leap year has `leap === 0`
  // (Esfand gets 30 days instead of 29).
  const r = jalCal(jy);
  return r.leap === 0 ? 30 : 29;
}

/**
 * Weekday (0..6) of the first day of a Jalali month, aligned to the Persian
 * week that starts on Saturday: 0 = شنبه, 1 = یکشنبه, ... 6 = جمعه.
 */
export function firstWeekdayOfJalaliMonth(jy: number, jm: number): number {
  const g = j2g(jy, jm, 1);
  const jsDay = new Date(g.gy, g.gm - 1, g.gd).getDay(); // 0=Sun .. 6=Sat
  return (jsDay + 1) % 7;
}

/** Gregorian ISO → Jalali, rendered as "ماه سال" (e.g. "آذر ۱۴۰۴"). */
export function jalaliMonthLabel(v?: string | null): string {
  const j = gregorianToJalali(v);
  if (!j) return "";
  return `${JALALI_MONTHS[j.jm - 1]} ${faNum(j.jy)}`;
}

/** Gregorian ISO → full Jalali, e.g. "۱۲ آذر ۱۴۰۴". */
export function formatJalali(v?: string | null, withYear = true): string {
  const j = gregorianToJalali(v);
  if (!j) return "—";
  const day = faNum(j.jd);
  const month = JALALI_MONTHS[j.jm - 1];
  if (!withYear) return `${day} ${month}`;
  return `${day} ${month} ${faNum(j.jy)}`;
}

/** Gregorian datetime → Jalali date (time dropped), used for display. */
export function formatJalaliFromDT(v?: string | null, withYear = true): string {
  if (!v) return "—";
  return formatJalali(String(v).split("T")[0], withYear);
}

/**
 * Gregorian ISO datetime → Jalali date + time, e.g. "۲۰ مرداد ۱۴۰۵، ۱۴:۳۰".
 * Accepts "YYYY-MM-DDTHH:MM:SS" or "YYYY-MM-DD HH:MM".
 */
export function formatJalaliDT(v?: string | null): string {
  if (!v) return "—";
  const s = String(v).replace(" ", "T");
  const [datePart, timePart] = s.split("T");
  const dateLabel = formatJalali(datePart, true);
  if (!timePart) return dateLabel;
  const hm = timePart.slice(0, 5);
  return `${dateLabel}، ${hm}`;
}

/**
 * Gregorian ISO datetime → Jalali date + clock in Asia/Tehran.
 * Year/day digits are ungrouped (۱۴۰۵ not ۱٬۴۰۵).
 */
export function formatJalaliDateTime(v?: string | null): { date: string; time: string; full: string } {
  if (!v) return { date: "—", time: "", full: "—" };
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) {
    return { date: formatJalaliDT(v), time: "", full: formatJalaliDT(v) };
  }
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Tehran",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    })
      .formatToParts(d)
      .map((p) => [p.type, p.value])
  ) as Record<string, string>;
  const hour = parts.hour === "24" ? "00" : parts.hour;
  const date = formatJalali(`${parts.year}-${parts.month}-${parts.day}`);
  const time = hour && parts.minute ? `${hour}:${parts.minute}` : "";
  return { date, time, full: time ? `${date}، ${time}` : date };
}
