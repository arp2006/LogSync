import { useEffect, useState } from "react";
import { RefreshCw, AlertTriangle, Search, Plus } from "lucide-react";
import { api } from "../lib/api";
import { fmtDate, shortId } from "../lib/utils";
import { StatusBadge } from "../components/StatusBadge";
import { LoadingState } from "../components/Spinner";
import { ErrorBanner } from "../components/ErrorBanner";
import { Modal } from "../components/Modal";
import { getSavedJobIds, saveJobId, clearJobHistory } from "../lib/jobHistory";

// ── Modals ─────────────────────────────────────────────────
function JobErrorsModal({ jobId, onClose }) {
  const [errors, setErrors] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.getJobErrors(jobId)
      .then((r) => setErrors(r.items))
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [jobId]);

  return (
    <Modal title="Parsing Errors" onClose={onClose}>
      {loading && <LoadingState />}
      <ErrorBanner message={err} />
      {errors?.length === 0 && (
        <p className="text-slate-400 text-sm text-center py-8">No parsing errors recorded for this job.</p>
      )}
      <div className="space-y-3">
        {errors?.map((e) => (
          <div key={e.id} className="bg-slate-800 rounded-lg p-3 text-xs space-y-1 border border-slate-700/60">
            <div className="flex justify-between">
              <span className="text-red-400 font-medium">{e.error_type}</span>
              <span className="mono text-slate-500">{shortId(e.raw_event_id)}</span>
            </div>
            <p className="text-slate-300">{e.error_message}</p>
            <p className="text-slate-500">{fmtDate(e.created_at)}</p>
          </div>
        ))}
      </div>
    </Modal>
  );
}

function JobDetailModal({ jobId, onClose }) {
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.getJob(jobId)
      .then(setJob)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [jobId]);

  return (
    <Modal title="Job Details" onClose={onClose}>
      {loading && <LoadingState />}
      <ErrorBanner message={err} />
      {job && (
        <div className="space-y-3 text-sm">
          <Row label="Job ID"         value={job.job_id || job.id} mono />
          <Row label="Status"         value={<StatusBadge status={job.status} />} />
          <Row label="Format"         value={job.format} />
          <Row label="Total Records"  value={job.total_records ?? "—"} />
          <Row label="Processed Records" value={job.processed_records ?? job.parsed_records ?? "—"} />
          <Row label="Failed Records" value={job.failed_records ?? "—"} />
          <Row label="Created"        value={fmtDate(job.created_at)} />
          <Row label="Updated"        value={fmtDate(job.updated_at)} />
          {job.error_message && (
            <div className="mt-2 p-3 rounded bg-red-950/50 border border-red-700/60 text-red-300 text-xs">
              {job.error_message}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

// ── Main page ──────────────────────────────────────────────
export default function Jobs() {
  const [jobs, setJobs] = useState([]);          // fetched job objects
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [detailJobId, setDetailJobId] = useState(null);
  const [errorJobId, setErrorJobId] = useState(null);

  // Manual lookup state
  const [lookupId, setLookupId] = useState("");
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState("");

  // Load all saved IDs on mount and whenever localStorage changes
  const loadAll = async () => {
    const ids = getSavedJobIds();
    if (ids.length === 0) return;
    setRefreshing(true);
    setError("");
    try {
      const results = await Promise.allSettled(ids.map((id) => api.getJob(id)));
      const fetched = results
        .filter((r) => r.status === "fulfilled")
        .map((r) => r.value);
      setJobs(fetched);
    } catch (e) {
      setError(e.message);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  // Look up a job by ID manually
  const handleLookup = async (e) => {
    e.preventDefault();
    const id = lookupId.trim();
    if (!id) return;
    setLookupLoading(true);
    setLookupError("");
    try {
      const job = await api.getJob(id);
      saveJobId(id);
      setJobs((prev) => {
        const exists = prev.find((j) => j.id === job.id);
        return exists
          ? prev.map((j) => (j.id === job.id ? job : j))
          : [job, ...prev];
      });
      setLookupId("");
    } catch (e) {
      setLookupError(e.message);
    } finally {
      setLookupLoading(false);
    }
  };

  const clearHistory = () => {
    clearJobHistory();
    setJobs([]);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Ingestion Jobs</h1>
          <p className="text-sm text-slate-400 mt-1">
            Track log upload and processing pipeline status. Jobs uploaded this session are remembered automatically.
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={loadAll} disabled={refreshing}>
            <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </button>
          {jobs.length > 0 && (
            <button className="btn-danger" onClick={clearHistory}>
              Clear History
            </button>
          )}
        </div>
      </div>

      {/* Lookup by ID */}
      <form onSubmit={handleLookup} className="card p-4 flex gap-3 items-end">
        <div className="flex-1">
          <label className="label">Look up a Job by ID</label>
          <input
            className="input"
            value={lookupId}
            onChange={(e) => setLookupId(e.target.value)}
            placeholder="Paste a job UUID…"
          />
        </div>
        <button type="submit" className="btn-primary shrink-0" disabled={lookupLoading}>
          <Search className="w-4 h-4" />
          {lookupLoading ? "Looking up…" : "Fetch"}
        </button>
      </form>
      <ErrorBanner message={lookupError} />

      <ErrorBanner message={error} />

      {/* Jobs table */}
      {refreshing && jobs.length === 0 ? (
        <LoadingState />
      ) : jobs.length === 0 ? (
        <div className="card p-10 text-center text-slate-400 text-sm space-y-3">
          <p>No jobs in history yet.</p>
          <p>
            <a href="/ingest" className="text-brand-400 underline inline-flex items-center gap-1">
              <Plus className="w-4 h-4" /> Upload some logs
            </a>
            {" "}or look up a job ID above.
          </p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-slate-700/60 text-slate-400 text-xs uppercase tracking-wider">
                <th className="table-cell">Job ID</th>
                <th className="table-cell">Format</th>
                <th className="table-cell">Status</th>
                <th className="table-cell">Records</th>
                <th className="table-cell">Created</th>
                <th className="table-cell">Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => {
                const id = j.job_id || j.id;
                const processed = j.processed_records ?? j.parsed_records;
                return (
                  <tr key={id} className="border-b border-slate-800 hover:bg-slate-800/40 transition-colors">
                    <td className="table-cell mono text-slate-400">{shortId(id)}</td>
                    <td className="table-cell text-slate-300 uppercase">{j.format}</td>
                    <td className="table-cell"><StatusBadge status={j.status} /></td>
                    <td className="table-cell text-slate-300">
                      {processed != null ? (
                        <span>
                          {processed}
                          {j.failed_records > 0 && (
                            <span className="text-orange-400 ml-1">/ {j.failed_records} err</span>
                          )}
                        </span>
                      ) : "—"}
                    </td>
                    <td className="table-cell text-slate-400">{fmtDate(j.created_at)}</td>
                    <td className="table-cell">
                      <div className="flex gap-2">
                        <button
                          className="btn-secondary px-2 py-1 text-xs"
                          onClick={() => setDetailJobId(id)}
                        >
                          Details
                        </button>
                        {(j.failed_records > 0 || j.status === "completed_with_errors") && (
                          <button
                            className="btn-danger px-2 py-1 text-xs"
                            onClick={() => setErrorJobId(id)}
                          >
                            <AlertTriangle className="w-3 h-3" /> Errors
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {detailJobId && <JobDetailModal jobId={detailJobId} onClose={() => setDetailJobId(null)} />}
      {errorJobId  && <JobErrorsModal jobId={errorJobId}  onClose={() => setErrorJobId(null)} />}
    </div>
  );
}

function Row({ label, value, mono }) {
  return (
    <div className="flex justify-between items-center gap-4 py-1.5 border-b border-slate-800">
      <span className="text-slate-400 shrink-0 text-xs uppercase tracking-wider">{label}</span>
      <span className={`text-slate-200 text-right ${mono ? "mono" : ""}`}>{value}</span>
    </div>
  );
}
