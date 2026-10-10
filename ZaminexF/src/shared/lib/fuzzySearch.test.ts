import { describe, expect, it } from "vitest";
import { fuzzyFilter, fuzzyMatch, normalizeText, similarityScore } from "./fuzzySearch";

const ZWNJ = "\u200c";

describe("normalizeText", () => {
  it("removes the zero-width non-joiner", () => {
    expect(normalizeText(`می${ZWNJ}خواهم`)).toBe("میخواهم");
    expect(normalizeText(`کتاب${ZWNJ}خانه${ZWNJ}ملی`)).toBe("کتابخانهملی");
  });

  it("removes every occurrence, not just the first", () => {
    expect(normalizeText(`${ZWNJ}a${ZWNJ}b${ZWNJ}`)).toBe("ab");
  });

  it("agrees with the server pipeline on compounds", () => {
    const cases: Array<[string, string]> = [
      [`می${ZWNJ}خواهم`, "میخواهم"],
      [`خانه${ZWNJ}داری`, "خانهداری"],
      [`  آپارتمان   دو  خواب  `, "آپارتمان دو خواب"],
      ["\u0643\u064a\u0641", "کیف"],
      ["۱۲۳", "123"],
      ["ABC", "abc"],
    ];
    for (const [input, expected] of cases) {
      expect(normalizeText(input), `normalizeText(${JSON.stringify(input)})`).toBe(
        expected
      );
    }
  });

  it("leaves an already-normal string alone", () => {
    expect(normalizeText("آپارتمان لوکس")).toBe("آپارتمان لوکس");
  });

  it("handles empty and non-string input", () => {
    expect(normalizeText("")).toBe("");
    expect(normalizeText(null as unknown as string)).toBe("");
    expect(normalizeText(undefined as unknown as string)).toBe("");
  });
});

describe("searching across a zero-width non-joiner", () => {
  const items = [
    { name: `می${ZWNJ}خواهم بفروشم` },
    { name: "آپارتمان لوکس" },
  ];
  const getText = (item: { name: string }) => item.name;

  it("matches a compound when the query omits the joiner", () => {
    expect(fuzzyFilter(items, "میخواهم", getText)).toEqual([items[0]]);
  });

  it("matches a compound when the query includes the joiner", () => {
    expect(fuzzyFilter(items, `می${ZWNJ}خواهم`, getText)).toEqual([items[0]]);
  });

  it("still matches when the joiner splits a searched word", () => {
    expect(fuzzyMatch("کتابخانه", `کتاب${ZWNJ}خانه مرکزی`)).toBe(true);
  });

  it("reports the same score with and without the joiner", () => {
    expect(similarityScore("میخواهم", `می${ZWNJ}خواهم`)).toBe(
      similarityScore("میخواهم", "میخواهم")
    );
  });
});
