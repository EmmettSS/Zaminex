import React from "react";
import { Card } from "./Card";
import { cx } from "../../lib/utils";

function ChartCard({ title, subtitle, children, actions, className }: { title: string; subtitle?: string; children: React.ReactNode; actions?: React.ReactNode; className?: string; }) {
  return (
    <Card className={cx("p-5 overflow-hidden", className)}>
      <div className="flex items-start justify-between gap-3 mb-4 flex-wrap">
        <div>
          <h3 className="text-sm font-semibold">{title}</h3>
          {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
        </div>
        {actions}
      </div>
      {children}
    </Card>
  );
}

export { ChartCard };
