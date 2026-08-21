import React from "react";
import {
  AIDescription,
  makeAIDescriptionFetcher,
} from "../../../shared/components/ui/AIDescription";

/**
 * AI description card for a single property (dynamic, driven by the backend).
 * Styled identically to the consultant AI section via the shared AIDescription.
 */
function PropertyAISummary({
  property,
  csrfToken,
}: {
  property: any;
  csrfToken?: string;
}) {
  const title = property?.title || "ملک";
  const id = property?.id;
  if (id == null) {
    return null;
  }
  return (
    <AIDescription
      key={id}
      reloadKey={id}
      title={`تحلیل ملک «${title}» توسط هوش مصنوعی`}
      fetchFn={makeAIDescriptionFetcher("property", id, csrfToken)}
    />
  );
}

export { PropertyAISummary };
