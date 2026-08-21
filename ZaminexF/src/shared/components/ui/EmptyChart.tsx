import React from "react";

function EmptyChart({ message }: { message: string }) {
  return (
    <div className="h-40 flex items-center justify-center text-xs text-muted-foreground border border-dashed border-border rounded-xl bg-secondary/20">
      {message}
    </div>
  );
}

export { EmptyChart };
