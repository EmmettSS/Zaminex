/**
 * Fuzzy Search Gateway
 *
 * This module is the single front-end gateway for fuzzy search in Zaminex.
 * Every search input, combobox, table filter, and client-side filter imports
 * from here — call sites must never inline their own matching logic.
 */
import Fuse from "fuse.js";

const DIGIT_MAP: Record<string, string> = {
  // Persian digits (U+06F0..U+06F9)
  "\u06F0": "0",
  "\u06F1": "1",
  "\u06F2": "2",
  "\u06F3": "3",
  "\u06F4": "4",
  "\u06F5": "5",
  "\u06F6": "6",
  "\u06F7": "7",
  "\u06F8": "8",
  "\u06F9": "9",
  // Arabic-Indic digits (U+0660..U+0669)
  "\u0660": "0",
  "\u0661": "1",
  "\u0662": "2",
  "\u0663": "3",
  "\u0664": "4",
  "\u0665": "5",
  "\u0666": "6",
  "\u0667": "7",
  "\u0668": "8",
  "\u0669": "9",
};

/** The single place where the 70% sensitivity requirement lives on the client. */
export const FUZZY_THRESHOLD = 0.7;

/**
 * Normalizes Persian / Arabic text for approximate comparison.
 * Returns "" for null / undefined input, so callers can chain safely.
 */
export function normalizeText(
  text: string | undefined | null
): string {
  if (!text) return "";
  return (
    text
      .toString()
      .toLowerCase()
      .normalize("NFC")
      // Unify Arabic letter variants to Persian equivalents
      .replace(/\u064a/g, "\u06CC") // Arabic ye          → Persian ye
      .replace(/\u0649/g, "\u06CC") // Arabic alef maksura → Persian ye
      .replace(/\u0643/g, "\u06A9") // Arabic kaf         → Persian kaf
      .replace(/\u0629/g, "\u0647") // Arabic ta marbuta  → Persian he
      // Unify Persian / Arabic-Indic digits to ASCII
      .replace(/[\u06F0-\u06F9\u0660-\u0669]/g, (d) => DIGIT_MAP[d] ?? d)
      // Remove zero-width non-joiner (ZWNJ)
      .replace(/\200c/g, "")
      // Collapse multiple whitespaces to a single space
      .replace(/\s+/g, " ")
      .trim()
  );
}

/**
 * Filters an array of generic items by fuzzy-matching `query` against the
 * text returned by `getSearchableText(item)`.
 */
export function fuzzyFilter<T>(
  items: T[],
  query: string,
  getSearchableText: (item: T) => string,
  threshold: number = FUZZY_THRESHOLD
): T[] {
  const normalizedQuery = normalizeText(query);
  if (normalizedQuery === "") return items;

  // Substring match fallback for short queries or errors
  if (normalizedQuery.length <= 2) {
    return items.filter((item) =>
      normalizeText(getSearchableText(item)).includes(normalizedQuery)
    );
  }

  try {
    const docs = items.map((item) => ({
      _item: item,
      searchText: normalizeText(getSearchableText(item)),
    }));

    const fuse = new Fuse(docs, {
      keys: ["searchText"],
      threshold: 1 - threshold,
      ignoreLocation: true,
      includeScore: true,
      shouldSort: true,
    });

    const results = fuse.search(normalizedQuery).map((result) => result.item._item);
    if (results.length > 0) return results;

    // Fallback to substring matching if Fuse returns empty
    return items.filter((item) =>
      normalizeText(getSearchableText(item)).includes(normalizedQuery)
    );
  } catch (err) {
    // Fail gracefully on any pattern/regex exception
    return items.filter((item) =>
      normalizeText(getSearchableText(item)).includes(normalizedQuery)
    );
  }
}

/**
 * Determines whether `target` matches `query`.
 */
export function fuzzyMatch(
  query: string | undefined | null,
  target: string | undefined | null,
  threshold: number = FUZZY_THRESHOLD
): boolean {
  const normalizedQuery = normalizeText(query);
  if (normalizedQuery === "") return true;
  if (normalizedQuery.length <= 2) {
    return normalizeText(target).includes(normalizedQuery);
  }
  return fuzzyFilter([target || ""], query || "", (t) => t, threshold).length > 0;
}

/**
 * Returns a normalized similarity score in [0, 1].
 */
export function similarityScore(
  query: string,
  target: string
): number {
  const normalizedTarget = normalizeText(target);
  if (normalizeText(query) === "") {
    return normalizedTarget === "" ? 1 : 0;
  }

  try {
    const fuse = new Fuse([{ searchText: normalizedTarget }], {
      keys: ["searchText"],
      threshold: 1,
      ignoreLocation: true,
      includeScore: true,
    });

    const results = fuse.search(normalizeText(query));
    if (results.length === 0 || results[0].score == null) return 0;
    return Math.min(1, Math.max(0, 1 - results[0].score));
  } catch (err) {
    return normalizeText(target).includes(normalizeText(query)) ? 1 : 0;
  }
}
