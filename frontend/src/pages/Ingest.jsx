import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Upload, CheckCircle2, AlertCircle, FileText } from "lucide-react";
import { api } from "../lib/api";
import { FORMAT_OPTIONS } from "../lib/utils";
import { ErrorBanner } from "../components/ErrorBanner";
import { Spinner } from "../components/Spinner";
import { saveJobId } from "../lib/jobHistory";

const STEP = { FORM: "form", UPLOADING: "uploading", SUCCESS: "success" };

export default function Ingest() {
  const [sources, setSources] = useState([]);
  const [form, setForm] = useState({ source_id: "", format: "cef" });
  const [file, setFile] = useState(null);
  const [step, setStep] = useState(STEP.FORM);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    api.listSources(true).then(setSources).catch(() => {});
  }, []);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    if (!file) { setError("Please select a log file."); return; }
    if (!form.source_id) { setError("Please select a source."); return; }
    setError("");
    setStep(STEP.UPLOADING);
    try {
      const job = await api.uploadLogs(form.source_id, form.format, file);
      const id = job.job_id || job.id;
      saveJobId(id);
      setResult({ ...job, id });
      setStep(STEP.SUCCESS);
    } catch (err) {
      setError(err.message);
      setStep(STEP.FORM);
    }
  };

  const reset = () => {
    setStep(STEP.FORM);
    setFile(null);
    setResult(null);
    setError("");
  };

  if (step === STEP.SUCCESS && result) {
    return (
      <div className="max-w-lg mx-auto space-y-6">
        <div className="card p-8 text-center space-y-4">
          <CheckCircle2 className="w-12 h-12 text-green-400 mx-auto" />
          <h2 className="text-xl font-bold text-slate-100">Upload Accepted</h2>
          <p className="text-slate-400 text-sm">
            Your log file has been received and queued for processing. The worker will parse and normalize events shortly.
          </p>
          <div className="text-left bg-slate-800 rounded-lg p-4 space-y-2 text-sm">
            <Row label="Job ID"     value={result.id} mono />
            <Row label="Status"     value={result.status} />
            <Row label="Format"     value={result.format} />
            <Row label="Source ID"  value={result.source_id} mono />
          </div>
          <div className="flex gap-3 justify-center pt-2">
            <button className="btn-secondary" onClick={reset}>Upload Another</button>
            <Link className="btn-primary" to="/jobs">View Jobs →</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Ingest Logs</h1>
        <p className="text-sm text-slate-400 mt-1">
          Upload a raw log file from a perimeter device. LogSync will preserve the original bytes with a
          SHA-256 hash, then parse and normalize events into OCSF.
        </p>
      </div>

      {/* Info callout */}
      <div className="flex gap-3 p-4 rounded-lg bg-brand-950/40 border border-brand-800/50 text-brand-300 text-sm">
        <AlertCircle className="w-4 h-4 mt-0.5 shrink-0 text-brand-400" />
        <div className="space-y-1">
          <p className="font-medium text-brand-200">Supported formats</p>
          <ul className="text-xs space-y-0.5 text-brand-300/80">
            <li>• <strong>CEF</strong> — ArcSight Common Event Format (pipe-delimited)</li>
            <li>• <strong>Syslog</strong> — RFC 5424 / RFC 3164 BSD format</li>
            <li>• <strong>JSON</strong> — Newline-delimited JSON (NDJSON)</li>
          </ul>
        </div>
      </div>

      <form onSubmit={submit} className="card p-6 space-y-5">
        <ErrorBanner message={error} />

        {/* Source */}
        <div>
          <label className="label">Source *</label>
          {sources.length === 0 ? (
            <p className="text-sm text-yellow-400">
              No active sources found.{" "}
              <a href="/sources" className="underline text-brand-400">Register one first →</a>
            </p>
          ) : (
            <select className="input" required value={form.source_id} onChange={set("source_id")}>
              <option value="">Select a source…</option>
              {sources.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.source_type})
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Format */}
        <div>
          <label className="label">Log Format *</label>
          <div className="flex gap-2">
            {FORMAT_OPTIONS.map((f) => (
              <label
                key={f}
                className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg border text-sm font-medium cursor-pointer transition-all
                  ${form.format === f
                    ? "bg-brand-700/30 border-brand-500 text-brand-300"
                    : "bg-slate-800 border-slate-600 text-slate-400 hover:border-slate-500"}`}
              >
                <input type="radio" className="hidden" value={f} checked={form.format === f} onChange={set("format")} />
                {f.toUpperCase()}
              </label>
            ))}
          </div>
        </div>

        {/* File */}
        <div>
          <label className="label">Log File *</label>
          <label className={`flex flex-col items-center justify-center gap-3 p-8 rounded-lg border-2 border-dashed cursor-pointer transition-colors
            ${file ? "border-brand-500 bg-brand-950/30" : "border-slate-600 hover:border-slate-500 bg-slate-800/40"}`}>
            <input
              type="file"
              className="hidden"
              accept=".log,.txt,.cef,.json,.syslog,text/plain,application/json"
              onChange={(e) => setFile(e.target.files[0] ?? null)}
            />
            {file ? (
              <>
                <FileText className="w-8 h-8 text-brand-400" />
                <div className="text-center">
                  <p className="text-sm font-medium text-slate-200">{file.name}</p>
                  <p className="text-xs text-slate-400 mt-1">{(file.size / 1024).toFixed(1)} KB</p>
                </div>
              </>
            ) : (
              <>
                <Upload className="w-8 h-8 text-slate-500" />
                <div className="text-center">
                  <p className="text-sm text-slate-300">Click to select a log file</p>
                  <p className="text-xs text-slate-500 mt-1">.log, .txt, .json, .cef accepted</p>
                </div>
              </>
            )}
          </label>
        </div>

        <button
          type="submit"
          className="btn-primary w-full justify-center py-3"
          disabled={step === STEP.UPLOADING}
        >
          {step === STEP.UPLOADING ? (
            <><Spinner className="w-4 h-4" /> Uploading…</>
          ) : (
            <><Upload className="w-4 h-4" /> Upload &amp; Queue</>
          )}
        </button>
      </form>
    </div>
  );
}

function Row({ label, value, mono }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-slate-400 shrink-0">{label}</span>
      <span className={`text-slate-200 text-right truncate ${mono ? "font-mono text-xs" : ""}`}>{value}</span>
    </div>
  );
}
