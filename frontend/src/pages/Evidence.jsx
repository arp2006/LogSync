import { useState } from "react";
import { Search, ShieldCheck, ShieldX, Hash } from "lucide-react";
import { api } from "../lib/api";
import { fmtDate } from "../lib/utils";
import { ErrorBanner } from "../components/ErrorBanner";
import { Spinner } from "../components/Spinner";

function VerifyResult({ result }) {
  const ok = result.matches;
  return (
    <div className={`card p-5 space-y-4 border ${ok ? "border-green-700/60" : "border-red-700/60"}`}>
      <div className="flex items-center gap-3">
        {ok ? (
          <ShieldCheck className="w-7 h-7 text-green-400" />
        ) : (
          <ShieldX className="w-7 h-7 text-red-400" />
        )}
        <div>
          <p className={`font-semibold text-lg ${ok ? "text-green-300" : "text-red-300"}`}>
            {ok ? "Integrity Verified ✓" : "Integrity Mismatch ✗"}
          </p>
          <p className="text-xs text-slate-400 mt-0.5">Verified at {fmtDate(result.verified_at)}</p>
        </div>
      </div>
      <div className="space-y-2 text-sm">
        <HashRow label="Stored SHA-256"   value={result.stored_sha256}   />
        <HashRow label="Computed SHA-256" value={result.computed_sha256} match={result.matches} />
      </div>
      {!ok && (
        <p className="text-red-400 text-xs p-3 rounded bg-red-950/40 border border-red-800/50">
          ⚠ The recomputed hash does not match the stored hash — the raw evidence may have been tampered with or corrupted.
        </p>
      )}
    </div>
  );
}

function HashRow({ label, value, match }) {
  return (
    <div className="space-y-0.5">
      <p className="label">{label}</p>
      <code className={`mono text-xs break-all ${match === false ? "text-red-400" : match === true ? "text-green-400" : "text-slate-300"}`}>
        {value}
      </code>
    </div>
  );
}

function RawEventCard({ raw }) {
  return (
    <div className="card p-5 space-y-3 text-sm">
      <div className="grid grid-cols-2 gap-3">
        <InfoCell label="Raw Event ID"  value={raw.id} />
        <InfoCell label="Job ID"        value={raw.job_id} />
        <InfoCell label="Source ID"     value={raw.source_id} />
        <InfoCell label="Record Index"  value={raw.record_index} />
        <InfoCell label="Received At"   value={fmtDate(raw.received_at)} />
      </div>
      <div>
        <p className="label flex items-center gap-1.5 mb-2"><Hash className="w-3 h-3" /> SHA-256</p>
        <code className="mono text-xs break-all text-slate-300">{raw.raw_sha256}</code>
      </div>
      {raw.raw_text && (
        <div>
          <p className="label mb-2">Original Raw Text</p>
          <pre className="mono text-xs bg-slate-800 rounded-lg p-3 overflow-x-auto text-slate-300 whitespace-pre-wrap border border-slate-700/60">
            {raw.raw_text}
          </pre>
        </div>
      )}
    </div>
  );
}

function InfoCell({ label, value }) {
  return (
    <div>
      <p className="label">{label}</p>
      <p className="mono text-slate-300 truncate">{value ?? "—"}</p>
    </div>
  );
}

export default function Evidence() {
  const [rawId, setRawId] = useState("");
  const [rawEvent, setRawEvent] = useState(null);
  const [verifyResult, setVerifyResult] = useState(null);
  const [fetchLoading, setFetchLoading] = useState(false);
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchRaw = async (e) => {
    e.preventDefault();
    if (!rawId.trim()) return;
    setError("");
    setRawEvent(null);
    setVerifyResult(null);
    setFetchLoading(true);
    try {
      const r = await api.getRawEvent(rawId.trim());
      setRawEvent(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setFetchLoading(false);
    }
  };

  const verify = async () => {
    setVerifyLoading(true);
    setVerifyResult(null);
    setError("");
    try {
      const r = await api.verifyRawEvent(rawId.trim());
      setVerifyResult(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setVerifyLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Evidence Store</h1>
        <p className="text-sm text-slate-400 mt-1">
          Retrieve original raw log bytes and verify cryptographic SHA-256 integrity for forensic traceability.
        </p>
      </div>

      {/* Explainer */}
      <div className="card p-4 text-sm text-slate-300 space-y-2 border-brand-700/30">
        <p className="flex items-center gap-2 font-medium text-brand-300">
          <ShieldCheck className="w-4 h-4" /> Immutable Evidence Preservation
        </p>
        <p className="text-slate-400 leading-relaxed">
          Every raw log record is stored on disk at{" "}
          <code className="mono bg-slate-800 px-1 rounded">data/raw/YYYY/MM/&lt;job-id&gt;/</code> and
          its SHA-256 hash is recorded at ingestion time. The verify endpoint recomputes the hash
          server-side using <code className="mono bg-slate-800 px-1 rounded">hmac.compare_digest</code>{" "}
          — any modification to the evidence is immediately detectable.
        </p>
      </div>

      {/* Lookup form */}
      <form onSubmit={fetchRaw} className="card p-5 space-y-4">
        <div>
          <label className="label">Raw Event ID (UUID)</label>
          <input
            className="input"
            value={rawId}
            onChange={(e) => setRawId(e.target.value)}
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            required
          />
        </div>
        <button type="submit" className="btn-primary" disabled={fetchLoading}>
          {fetchLoading ? <Spinner className="w-4 h-4" /> : <Search className="w-4 h-4" />}
          Fetch Evidence
        </button>
      </form>

      <ErrorBanner message={error} />

      {rawEvent && (
        <>
          <RawEventCard raw={rawEvent} />
          <div className="flex justify-end">
            <button className="btn-secondary" onClick={verify} disabled={verifyLoading}>
              {verifyLoading ? <Spinner className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4" />}
              Verify SHA-256 Integrity
            </button>
          </div>
        </>
      )}

      {verifyResult && <VerifyResult result={verifyResult} />}
    </div>
  );
}
