import { useEffect, useState } from "react";
import {
  Server,
  ListChecks,
  Activity,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react";
import { api } from "../lib/api";
import { LoadingState } from "../components/Spinner";
import { fmtDate } from "../lib/utils";

function StatCard({ icon: Icon, label, value, color = "text-brand-400" }) {
  return (
    <div className="card p-5 flex items-center gap-4">
      <div className={`p-3 rounded-lg bg-slate-800 ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-2xl font-bold text-slate-100">{value ?? "—"}</p>
        <p className="text-xs text-slate-400 mt-0.5">{label}</p>
      </div>
    </div>
  );
}

function HealthIndicator({ status }) {
  if (status === "ok")
    return (
      <span className="flex items-center gap-1.5 text-green-400 text-sm font-medium">
        <CheckCircle2 className="w-4 h-4" /> API Healthy
      </span>
    );
  if (status === "error")
    return (
      <span className="flex items-center gap-1.5 text-red-400 text-sm font-medium">
        <XCircle className="w-4 h-4" /> API Unreachable
      </span>
    );
  return (
    <span className="flex items-center gap-1.5 text-slate-400 text-sm">
      <Loader2 className="w-4 h-4 animate-spin" /> Checking…
    </span>
  );
}

export default function Dashboard() {
  const [health, setHealth] = useState("checking");
  const [sources, setSources] = useState(null);
  const [events, setEvents] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.health().then((r) => {
        setHealth(r?.status === "ready" ? "ok" : "error");
      }).catch(() => setHealth("error")),
      api.listSources().then(setSources).catch(() => setSources([])),
      api.searchEvents({ limit: 5 }).then(setEvents).catch(() => setEvents({ items: [] })),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState label="Loading dashboard…" />;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Dashboard</h1>
          <p className="text-sm text-slate-400 mt-1">
            Security telemetry pipeline · ingestion, normalization, evidence preservation
          </p>
        </div>
        <HealthIndicator status={health} />
      </div>

      {/* Explainer banner */}
      <div className="card p-5 bg-gradient-to-r from-brand-900/40 to-slate-900 border-brand-700/40">
        <h2 className="font-semibold text-brand-300 mb-2 text-sm uppercase tracking-wider">
          What is LogSync?
        </h2>
        <p className="text-slate-300 text-sm leading-relaxed">
          LogSync is a ULPF. This <strong className="text-white">Universal Log Pre-processing Framework</strong> is a
          backend-first security telemetry pipeline. It ingests raw logs from perimeter network
          devices (firewalls, IDS, routers), preserves the original bytes with a cryptographic
          SHA-256 hash for forensic integrity, parses CEF / Syslog / JSON formats, and normalizes
          every event into the{" "}
          <span className="text-brand-300 font-medium">OCSF 1.1.0</span> canonical schema — ready
          for SIEM consumption or streaming export.
        </p>
        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          {["CEF Parser", "Syslog Parser", "JSON Parser", "OCSF 1.1.0", "SHA-256 Evidence", "SIEM Export"].map((t) => (
            <span key={t} className="px-2 py-1 rounded bg-brand-900/60 border border-brand-700/40 text-brand-300">
              {t}
            </span>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard icon={Server}    label="Registered Sources"     value={sources?.length} color="text-brand-400" />
        <StatCard icon={CheckCircle2} label="Active Sources"      value={sources?.filter((s) => s.is_active).length} color="text-green-400" />
        <StatCard icon={Activity}  label="Recent Normalized Events" value={events?.items?.length} color="text-purple-400" />
        <StatCard icon={ShieldCheck} label="Integrity Verification" value="SHA-256" color="text-yellow-400" />
      </div>

      {/* Pipeline overview */}
      <div className="card p-5">
        <h2 className="font-semibold text-slate-200 mb-4">Pipeline Architecture</h2>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {[
            { step: "1", label: "Register Source", desc: "Network device or log source" },
            { step: "2", label: "Ingest Logs", desc: "Upload CEF / Syslog / JSON" },
            { step: "3", label: "Evidence Store", desc: "Immutable SHA-256 snapshot" },
            { step: "4", label: "Parse & Normalize", desc: "OCSF canonical events" },
            { step: "5", label: "Query & Export", desc: "Search, verify, stream JSONL" },
          ].map((s, i, arr) => (
            <div key={s.step} className="flex items-center gap-2">
              <div className="flex flex-col items-center text-center min-w-[110px]">
                <div className="w-8 h-8 rounded-full bg-brand-700 text-white flex items-center justify-center text-xs font-bold mb-1.5">
                  {s.step}
                </div>
                <p className="font-medium text-slate-200 text-xs">{s.label}</p>
                <p className="text-slate-500 text-[10px] mt-0.5">{s.desc}</p>
              </div>
              {i < arr.length - 1 && (
                <div className="text-slate-600 text-lg">→</div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Recent events table */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-700/60">
          <h2 className="font-semibold text-slate-200">Recent Normalized Events</h2>
        </div>
        {events?.items?.length === 0 ? (
          <p className="text-center py-10 text-slate-500 text-sm">No events yet — ingest some logs to get started.</p>
        ) : (
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-slate-700/60 text-slate-400 text-xs uppercase tracking-wider">
                <th className="table-cell">Event ID</th>
                <th className="table-cell">OCSF Class</th>
                <th className="table-cell">Event Time</th>
                <th className="table-cell">Source ID</th>
              </tr>
            </thead>
            <tbody>
              {events?.items?.map((ev) => (
                <tr key={ev.id} className="border-b border-slate-800 hover:bg-slate-800/50 transition-colors">
                  <td className="table-cell mono text-slate-400">{ev.id.slice(0, 8)}…</td>
                  <td className="table-cell text-slate-300">{ev.class_uid ?? "—"}</td>
                  <td className="table-cell text-slate-300">{fmtDate(ev.event_time)}</td>
                  <td className="table-cell mono text-slate-400">{ev.source_id?.slice(0, 8)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
