import { useCallback, useEffect, useState } from "react";
import { CircleCheck, Info, TriangleAlert, XCircle } from "lucide-react";
import { cx, subscribeToToasts, ToastItem } from "../../lib/utils";

function ToastContainer() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const add = useCallback((item: Omit<ToastItem, "id">) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((current) => [...current, { ...item, id }]);
    setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, 3500);
  }, []);

  useEffect(() => subscribeToToasts(add), [add]);

  const styles = {
    success: "border-emerald-200 text-emerald-700 bg-white",
    error: "border-red-200 text-red-700 bg-white",
    warning: "border-amber-200 text-amber-700 bg-white",
    info: "border-blue-200 text-blue-700 bg-white",
  };
  const icons = {
    success: <CircleCheck size={15} />,
    error: <XCircle size={15} />,
    warning: <TriangleAlert size={15} />,
    info: <Info size={15} />,
  };

  return (
    <div className="fixed bottom-6 left-6 z-[9999] flex flex-col gap-2 pointer-events-none">
      {toasts.map((item) => (
        <div
          key={item.id}
          className={cx(
            "flex items-center gap-3 px-4 py-3 rounded-xl border shadow-lg text-sm font-medium pointer-events-auto min-w-72",
            styles[item.type],
          )}
        >
          {icons[item.type]}
          <span className="text-foreground">{item.message}</span>
        </div>
      ))}
    </div>
  );
}

export { ToastContainer };
