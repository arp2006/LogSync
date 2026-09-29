import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Server,
  Upload,
  ListChecks,
  ShieldCheck,
  Download,
  Activity,
} from "lucide-react";
import { cn } from "../lib/utils";

const NAV = [
  { to: "/",         label: "Dashboard",    icon: LayoutDashboard },
  { to: "/sources",  label: "Sources",      icon: Server },
  { to: "/ingest",   label: "Ingest Logs",  icon: Upload },
  { to: "/jobs",     label: "Jobs",         icon: ListChecks },
  { to: "/events",   label: "Events",       icon: Activity },
  { to: "/evidence", label: "Evidence",     icon: ShieldCheck },
  { to: "/export",   label: "Export",       icon: Download },
];

export function Sidebar() {
  return (
    <aside className="w-60 shrink-0 h-screen sticky top-0 flex flex-col bg-slate-900 border-r border-slate-700/60">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-slate-700/60">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
            <ShieldCheck className="w-4 h-4 text-white" />
          </div>
          <div>
            <p className="font-bold text-sm text-white leading-none">LogSync</p>
            <p className="text-[10px] text-slate-400 mt-0.5 leading-none">Log Pre-processing</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                isActive
                  ? "bg-brand-600/20 text-brand-300 border border-brand-700/40"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              )
            }
          >
            <Icon className="w-4 h-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-slate-700/60 text-[10px] text-slate-500 space-y-0.5">
        <p className="font-semibold text-slate-400">LogSync v0.1.0</p>
        <p>OCSF 1.1.0 · pgcrypto SHA-256</p>
      </div>
    </aside>
  );
}
