import { AlertCircle } from "lucide-react";

export function ErrorBanner({ message }) {
  if (!message) return null;
  return (
    <div className="flex items-start gap-3 p-4 rounded-lg bg-red-950/60 border border-red-700/60 text-red-300 text-sm">
      <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  );
}
