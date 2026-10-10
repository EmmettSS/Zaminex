import React from "react";
import { Input } from "./Input";
import { SelectField } from "./SelectField";
import { JalaliDateInput } from "./JalaliDateInput";
import { cx } from "../../lib/utils";

export type AttributeOption = { value: string; displayName: string };

export type AttributeField = {
  id: number;
  name: string;
  displayName: string;
  dataType: "text" | "integer" | "decimal" | "boolean" | "date" | "select" | "multiselect";
  inputType: "default" | "price";
  unit?: string;
  isFacility: boolean;
  isCore: boolean;
  coreField?: string;
  isRequired: boolean;
  sortOrder: string | number;
  options: AttributeOption[];
};

export type AttributeSchema = {
  fields: AttributeField[];
  facilities: AttributeField[];
};

function labelFor(field: AttributeField) {
  return field.unit ? `${field.displayName} (${field.unit})` : field.displayName;
}

function AttributeInput({
  field,
  value,
  onChange,
  error,
}: {
  field: AttributeField;
  value: any;
  onChange: (name: string, value: any) => void;
  error?: string;
}) {
  switch (field.dataType) {
    case "boolean":
      return (
        <label className="flex items-center gap-2.5 rounded-xl border border-border bg-input-background px-3.5 py-2.5 cursor-pointer hover:border-primary transition-colors">
          <input
            type="checkbox"
            checked={value === true}
            onChange={(e) => onChange(field.name, e.target.checked)}
            className="w-4 h-4 rounded border-border accent-primary"
          />
          <span className="text-sm text-foreground">{field.displayName}</span>
        </label>
      );

    case "select":
      return (
        <SelectField
          label={labelFor(field)}
          value={value ?? ""}
          onChange={(v) => onChange(field.name, v)}
          options={field.options.map((o) => ({ label: o.displayName, value: o.value }))}
          placeholder="انتخاب کنید"
          required={field.isRequired}
          error={error}
        />
      );

    case "multiselect":
      return (
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-foreground">
            {labelFor(field)}
            {field.isRequired && <span className="text-primary mr-1">*</span>}
          </label>
          <div className="flex flex-wrap gap-2">
            {field.options.map((o) => {
              const selected: string[] = Array.isArray(value) ? value : [];
              const on = selected.includes(o.value);
              return (
                <button
                  key={o.value}
                  type="button"
                  onClick={() =>
                    onChange(
                      field.name,
                      on ? selected.filter((v) => v !== o.value) : [...selected, o.value]
                    )
                  }
                  className={cx(
                    "px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors",
                    on
                      ? "bg-primary/10 border-primary text-primary"
                      : "bg-input-background border-border text-muted-foreground hover:border-primary"
                  )}
                >
                  {o.displayName}
                </button>
              );
            })}
          </div>
          {error && <p className="text-xs text-destructive">{error}</p>}
        </div>
      );

    case "date":
      return (
        <JalaliDateInput
          label={labelFor(field)}
          value={value ?? ""}
          onChange={(v) => onChange(field.name, v)}
          required={field.isRequired}
          error={error}
        />
      );

    case "integer":
    case "decimal": {
      const isPriceField = field.inputType === "price" || Boolean(field.unit && field.unit.includes("تومان"));
      return (
        <Input
          label={labelFor(field)}
          type={isPriceField ? "text" : "number"}
          isPrice={isPriceField}
          placeholder={isPriceField ? "مبلغ به تومان" : ""}
          value={value ?? ""}
          onChange={(v) => onChange(field.name, v)}
          required={field.isRequired}
          error={error}
        />
      );
    }

    default: {
      const isPriceField = field.inputType === "price" || Boolean(field.unit && field.unit.includes("تومان"));
      return (
        <Input
          label={labelFor(field)}
          isPrice={isPriceField}
          placeholder={isPriceField ? "مبلغ به تومان" : undefined}
          value={value ?? ""}
          onChange={(v) => onChange(field.name, v)}
          required={field.isRequired}
          error={error}
        />
      );
    }
  }
}


function DynamicAttributeFields({
  schema,
  values,
  onChange,
  errors = {},
  loading = false,
}: {
  schema: AttributeSchema | null;
  values: Record<string, any>;
  onChange: (name: string, value: any) => void;
  errors?: Record<string, string>;
  loading?: boolean;
}) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="space-y-1.5">
            <div className="h-4 w-24 rounded bg-secondary animate-pulse" />
            <div className="h-10 rounded-xl bg-secondary animate-pulse" />
          </div>
        ))}
      </div>
    );
  }

  if (!schema) return null;

  const fields = schema.fields.filter((f) => !f.isCore);
  const facilities = schema.facilities;

  if (fields.length === 0 && facilities.length === 0) return null;

  return (
    <>
      {fields.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          {fields.map((field) => (
            <AttributeInput
              key={field.name}
              field={field}
              value={values[field.name]}
              onChange={onChange}
              error={errors[field.name]}
            />
          ))}
        </div>
      )}

      {facilities.length > 0 && (
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">امکانات</label>
          <div className="grid grid-cols-3 gap-2">
            {facilities.map((field) => (
              <AttributeInput
                key={field.name}
                field={field}
                value={values[field.name]}
                onChange={onChange}
                error={errors[field.name]}
              />
            ))}
          </div>
        </div>
      )}
    </>
  );
}

export { DynamicAttributeFields, AttributeInput };
