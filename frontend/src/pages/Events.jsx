import { useEffect, useState, useCallback } from "react";
import { Search, ChevronRight, X, RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import { fmtDate, shortId, OCSF_CLASSES } from "../lib/utils";
import { OCSFBadge } from "../components/OCSFBadge";
import { LoadingState } from "../components/Spinner";
import { ErrorBanner } from "../components/ErrorBanner";
import { Modal } from "../components/Modal";

function InfoCell({ label, value, mono }) {
  return (
    <div>
      <p className="label">{label}</p>
      <p className={`text-slate-200 truncate ${mono ? "mono" : ""}`}>{value ?? "—"}</p>
    </div>
  );
}

function EventDetailModal({ eventId, onClose }) {
  const [ev, setEv] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.getEvent(eventId)
      .then(setEv)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [eventId]);

  return (
    <Modal title="Normalized Event" onClose={onClose}>
      {loading && <LoadingState />}
      <ErrorBanner message={err} />
      {ev && (
        <div className="space-y-4 text-sm">
          <div className="grid grid-cols-2 gap-3">
            <InfoCell label="Event ID"   value={ev.id} mono />
            <InfoCell label="OCSF Class" value={<OCSFBadge classUid={ev.class_uid} />} />
            <InfoCell label="Event Time" value={fmtDate(ev.event_time)} />
            <InfoCell label="OCSF Ver."  value={ev.ocsf_version} />
            <InfoCell label="Source ID"  value={ev.source_id} mono />
            <InfoCell label="Raw Evt ID" value={ev.raw_event_id} mono />
          </div>
          <div>
            <p className="label mb-2">Event Data (OCSF Payload)</p>
            <pre className="mono bg-slate-800 rounded-lg p-4 overflow-x-auto text-slate-300 text-xs leading-relaxed whitespace-pre-wrap">
              {JSON.stringify(ev.event_data, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </Modal>
  );
}

export default function Events() {
  const [events, setEvents] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sources, setSources] = useState([]);
  const [selectedEventId, setSelectedEventId] = useState(null);

  const [filters, setFilters] = useState({
    source_id: "",
    class_uid: "",
    from: "",
    to: "",
    limit: 50,
  });

  useEffect(() => {
    api.listSources().then(setSources).catch(() => {});
  }, []);

  const search = useCallback(
    async (cursor = null, append = false) => {
      setLoading(true);
      setError("");
      try {
        const params = { ...filters, cursor: cursor || undefined };
        // remove empty strings
        Object.keys(params).forEach((k) => { if (params[k] === "") delete params[k]; });
        const res = await api.searchEvents(params);
        setEvents((prev) => (append ? [...prev, ...res.items] : res.items));
        setNextCursor(res.next_cursor);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    },
    [filters]
  );

  useEffect(() => { search(); }, []); // initial load

  const setFilter = (k) => (e) =>
    setFilters((f) => ({ ...f, [k]: e.target.value }));

  const clearFilters = () => {
    setFilters({ source_id: "", class_uid: "", from: "", to: "", limit: 50 });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Normalized Events</h1>
        <p className="text-sm text-slate-400 mt-1">
          OCSF 1.1.0 canonical events — filter, inspect payloads, and verify raw evidence.
        </p>
      </div>

      {/* Filters */}
      <div className="card p-4 space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label className="label">Source</label>
            <select className="input" value={filters.source_id} onChange={setFilter("source_id")}>
              <option value="">All sources</option>
              {sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">OCSF Class</label>
            <select className="input" value={filters.class_uid} onChange={setFilter("class_uid")}>
              <option value="">All classes</option>
              {Object.entries(OCSF_CLASSES).map(([uid, name]) => (
                <option key={uid} value={uid}>{uid} — {name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">From</label>
            <input className="input" type="datetime-local" value={filters.from} onChange={setFilter("from")} />
          </div>
          <div>
            <label className="label">To</label>
            <input className="input" type="datetime-local" value={filters.to} onChange={setFilter("to")} />
          </div>
        </div>
        <div className="flex gap-2 justify-end">
          <button className="btn-secondary" onClick={clearFilters}><X className="w-4 h-4" /> Clear</button>
          <button className="btn-primary" onClick={() => search(null, false)}>
            <Search className="w-4 h-4" /> Search
          </button>
        </div>
      </div>

      <ErrorBanner message={error} />

      {/* Table */}
      {loading && events.length === 0 ? (
        <LoadingState />
      ) : events.length === 0 ? (
        <div className="card p-10 text-center text-slate-400 text-sm">
          No events found. <a href="/ingest" className="text-brand-400 underline">Ingest some logs →</a>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-slate-700/60 text-slate-400 text-xs uppercase tracking-wider">
                <th className="table-cell">Event ID</th>
                <th className="table-cell">OCSF Class</th>
                <th className="table-cell">Event Time</th>
                <th className="table-cell">Source</th>
                <th className="table-cell">Raw Event</th>
                <th className="table-cell"></th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => (
                <tr
                  key={ev.id}
                  className="border-b border-slate-800 hover:bg-slate-800/40 transition-colors cursor-pointer"
                  onClick={() => setSelectedEventId(ev.id)}
                >
                  <td className="table-cell mono text-slate-400">{shortId(ev.id)}</td>
                  <td className="table-cell"><OCSFBadge classUid={ev.class_uid} /></td>
                  <td className="table-cell text-slate-300">{fmtDate(ev.event_time)}</td>
                  <td className="table-cell mono text-slate-500">{shortId(ev.source_id)}</td>
                  <td className="table-cell mono text-slate-500">{shortId(ev.raw_event_id)}</td>
                  <td className="table-cell text-right">
                    <ChevronRight className="w-4 h-4 text-slate-500 inline-block" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {nextCursor && (
            <div className="px-5 py-4 border-t border-slate-700/60 flex justify-center">
              <button
                className="btn-secondary"
                onClick={() => search(nextCursor, true)}
                disabled={loading}
              >
                {loading ? "Loading…" : "Load More"}
              </button>
            </div>
          )}
        </div>
      )}

      {selectedEventId && (
        <EventDetailModal eventId={selectedEventId} onClose={() => setSelectedEventId(null)} />
      )}
    </div>
  );
}
