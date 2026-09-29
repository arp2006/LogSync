import { STATUS_META } from "../lib/utils";

export function StatusBadge({ status }) {
  const meta = STATUS_META[status] ?? {
    color: "bg-slate-700 text-slate-300 border-slate-600",
    label: status,
  };
  return (
    <span className={`badge border ${meta.color}`}>{meta.label}</span>
  );
}
