import { OCSF_CLASSES } from "../lib/utils";

const CLASS_COLORS = {
  1001: "bg-slate-700/60 text-slate-300 border-slate-600",
  3001: "bg-purple-900/60 text-purple-300 border-purple-700/60",
  4001: "bg-brand-900/60 text-brand-300 border-brand-700/60",
};

export function OCSFBadge({ classUid }) {
  const label = OCSF_CLASSES[classUid] ?? `Class ${classUid}`;
  const color =
    CLASS_COLORS[classUid] ?? "bg-slate-700/60 text-slate-300 border-slate-600";
  return <span className={`badge border ${color}`}>{label}</span>;
}
