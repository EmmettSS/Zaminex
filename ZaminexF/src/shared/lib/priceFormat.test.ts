import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { DynamicAttributeFields } from "../components/ui/DynamicAttributeFields";
import { Input } from "../components/ui/Input";
import {
  formatPriceToPersianWords,
  formatPriceWithCommas,
  normalizePriceDigits,
  numberToPersianWords,
} from "./utils";

describe("normalizePriceDigits", () => {
  it("extracts digits and strips leading zeros", () => {
    expect(normalizePriceDigits("")).toBe("");
    expect(normalizePriceDigits("0")).toBe("");
    expect(normalizePriceDigits("0001500")).toBe("1500");
    expect(normalizePriceDigits("1,500,000,000")).toBe("1500000000");
  });

  it("normalizes Persian and Arabic digits", () => {
    expect(normalizePriceDigits("۱,۵۰۰,۰۰۰,۰۰۰")).toBe("1500000000");
    expect(normalizePriceDigits("١٥٠٠٠٠٠٠٠٠")).toBe("1500000000");
  });

  it("strips trailing decimal zeros from backend strings", () => {
    expect(normalizePriceDigits("18000000000.00")).toBe("18000000000");
  });

  it("caps length at 18 digits", () => {
    expect(normalizePriceDigits("12345678901234567890")).toBe("123456789012345678");
  });

  it("rejects zero and negative numbers across all formats", () => {
    expect(normalizePriceDigits(0)).toBe("");
    expect(normalizePriceDigits(-1)).toBe("");
    expect(normalizePriceDigits(-1500000000)).toBe("");
    expect(normalizePriceDigits("0")).toBe("");
    expect(normalizePriceDigits("0000")).toBe("");
    expect(normalizePriceDigits("۰")).toBe("");
    expect(normalizePriceDigits("٠")).toBe("");
    expect(normalizePriceDigits("-1500000000")).toBe("");
    expect(normalizePriceDigits("−1500000000")).toBe("");
    expect(normalizePriceDigits("-۱,۵۰۰,۰۰۰,۰۰۰")).toBe("");
  });
});

describe("formatPriceWithCommas", () => {
  it("formats numbers into 3-digit groups", () => {
    expect(formatPriceWithCommas("")).toBe("");
    expect(formatPriceWithCommas("0")).toBe("");
    expect(formatPriceWithCommas("5")).toBe("5");
    expect(formatPriceWithCommas("500")).toBe("500");
    expect(formatPriceWithCommas("1500")).toBe("1,500");
    expect(formatPriceWithCommas("1500000000")).toBe("1,500,000,000");
    expect(formatPriceWithCommas("۱۸۵۰۰۰۰۰۰۰۰")).toBe("18,500,000,000");
  });
});

describe("numberToPersianWords & formatPriceToPersianWords", () => {
  it("returns empty string for empty or zero input", () => {
    expect(numberToPersianWords("")).toBe("");
    expect(numberToPersianWords("0")).toBe("");
    expect(formatPriceToPersianWords("")).toBe("");
    expect(formatPriceToPersianWords("0")).toBe("");
  });

  it("converts exact user example (1,500,000,000) to Persian words", () => {
    expect(formatPriceToPersianWords("1500000000")).toBe("یک میلیارد و پانصد میلیون تومان");
    expect(formatPriceToPersianWords("1,500,000,000")).toBe("یک میلیارد و پانصد میلیون تومان");
    expect(formatPriceToPersianWords("۱۵۰۰۰۰۰۰۰۰")).toBe("یک میلیارد و پانصد میلیون تومان");
  });

  it("converts ones, teens, tens, hundreds, thousands, millions, billions, trillions accurately", () => {
    expect(formatPriceToPersianWords("1")).toBe("یک تومان");
    expect(formatPriceToPersianWords("12")).toBe("دوازده تومان");
    expect(formatPriceToPersianWords("25")).toBe("بیست و پنج تومان");
    expect(formatPriceToPersianWords("100")).toBe("صد تومان");
    expect(formatPriceToPersianWords("200")).toBe("دویست تومان");
    expect(formatPriceToPersianWords("300")).toBe("سیصد تومان");
    expect(formatPriceToPersianWords("500")).toBe("پانصد تومان");
    expect(formatPriceToPersianWords("1000")).toBe("یک هزار تومان");
    expect(formatPriceToPersianWords("45000000")).toBe("چهل و پنج میلیون تومان");
    expect(formatPriceToPersianWords("850000000")).toBe("هشتصد و پنجاه میلیون تومان");
    expect(formatPriceToPersianWords("18750000000")).toBe("هجده میلیارد و هفتصد و پنجاه میلیون تومان");
    expect(formatPriceToPersianWords("2500000000000")).toBe("دو تریلیون و پانصد میلیارد تومان");
  });
});

describe("Input with isPrice", () => {
  it("renders formatted 3-digit value and Persian words subtitle below the input", () => {
    const html = renderToStaticMarkup(
      React.createElement(Input, {
        label: "قیمت فروش (تومان)",
        isPrice: true,
        placeholder: "مبلغ به تومان",
        value: "1500000000",
        onChange: () => {},
      })
    );
    expect(html).toContain('value="1,500,000,000"');
    expect(html).toContain('inputMode="numeric"');
    expect(html).toContain("یک میلیارد و پانصد میلیون تومان");
  });

  it("does not render Persian words subtitle when value is empty", () => {
    const html = renderToStaticMarkup(
      React.createElement(Input, {
        label: "قیمت فروش (تومان)",
        isPrice: true,
        placeholder: "مبلغ به تومان",
        value: "",
        onChange: () => {},
      })
    );
    expect(html).toContain('value=""');
    expect(html).not.toContain("تومان</p>");
  });

  it("rejects zero or negative values in Input with isPrice", () => {
    for (const invalid of ["0", "000", "۰", "-1500000", "−5000"]) {
      const html = renderToStaticMarkup(
        React.createElement(Input, {
          label: "قیمت فروش (تومان)",
          isPrice: true,
          placeholder: "مبلغ به تومان",
          value: invalid,
          onChange: () => {},
        })
      );
      expect(html).toContain('value=""');
      expect(html).not.toContain("تومان</p>");
    }
  });

  it("formats dynamic price attributes in DynamicAttributeFields with commas and Persian words", () => {
    const html = renderToStaticMarkup(
      React.createElement(DynamicAttributeFields, {
        schema: {
          fields: [
            {
              id: 1,
              name: "commission_amount",
              displayName: "مبلغ کمیسیون",
              dataType: "integer",
              inputType: "price",
              unit: "تومان",
              isFacility: false,
              isRequired: false,
              isCore: false,
              sortOrder: 1,
              options: [],
            },
          ],
          facilities: [],
        },
        values: { commission_amount: "25000000" },
        onChange: vi.fn(),
      })
    );
    expect(html).toContain('value="25,000,000"');
    expect(html).toContain("بیست و پنج میلیون تومان");
  });
});


