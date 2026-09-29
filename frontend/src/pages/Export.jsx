import { useEffect, useState } from "react";
import { Download, FileDown, ExternalLink } from "lucide-react";
import { api } from "../lib/api";
import { OCSF_CLASSES } from "../lib/utils";

export default function Export() {
  const [sources, setSources] = useState([]);
  const [form, setForm] = useState({
    source_id: "",
    from: "",
    to: "",
  });

  useEffect(() => {
    api.listSources().then(setSources).catch(() => {});
  }, []);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const params = {
    source_id: form.source_id || undefined,
    from: form.from ? new Date(form.from).toISOString() : undefined,
    to: form.to ? new Date(form.to).toISOString() : undefined,
  };

  const url = api.exportEventsUrl(params);

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Export Events</h1>
        <p className="text-sm text-slate-400 mt-1">
          Stream normalized OCSF events as Newline-Delimited JSON (NDJSON) for SIEM, analytics, or archival.
        </p>
      </div>

      {/* Info */}
      <div className="card p-4 space-y-3 text-sm text-slate-300 border-brand-700/30">
        <p className="font-medium text-brand-300 flex items-center gap-2">
          <FileDown className="w-4 h-4" /> JSONL Streaming Export
        </p>
        <ul className="space-y-1 text-slate-400 text-xs list-disc list-inside">
          <li>Each line is a valid JSON object (OCSF event_data payload)</li>
          <li>Events ordered by <code className="mono bg-slate-800 px-1 rounded">event_time DESC</code></li>
          <li>Compatible with Splunk, Elastic, Chronicle, and other SIEMs</li>
          <li>Use the time range filters to narrow the export window</li>
        </ul>
      </div>

      {/* Filters */}
      <div className="card p-6 space-y-5">
        <div>
          <label className="label">Source (optional)</label>
          <select className="input" value={form.source_id} onChange={set("source_id")}>
            <option value="">All sources</option>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">From (optional)</label>
            <input className="input" type="datetime-local" value={form.from} onChange={set("from")} />
          </div>
          <div>
            <label className="label">To (optional)</label>
            <input className="input" type="datetime-local" value={form.to} onChange={set("to")} />
          </div>
        </div>

        {/* Preview URL */}
        <div>
          <label className="label">Export URL</label>
          <div className="flex gap-2 items-center">
            <code className="mono flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-300 overflow-x-auto whitespace-nowrap">
              {url}
            </code>
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="btn-secondary px-2 py-2"
              title="Open in new tab"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>
        </div>

        <a href={url} download="export_events.jsonl" className="btn-primary w-full justify-center py-3">
          <Download className="w-4 h-4" /> Download export_events.jsonl
        </a>
      </div>

      {/* curl snippet */}
      <div className="card p-5">
        <p className="label mb-3">cURL Command</p>
        <pre className="mono text-xs text-slate-300 bg-slate-800 rounded-lg p-4 overflow-x-auto whitespace-pre-wrap border border-slate-700/60">
{`curl -o export_events.jsonl \\
  "${window.location.origin}${url}"`}
        </pre>
      </div>
    </div>
  );
}
