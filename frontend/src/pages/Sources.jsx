import { useEffect, useState } from "react";
import { Plus, RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import { fmtDate, shortId } from "../lib/utils";
import { LoadingState } from "../components/Spinner";
import { ErrorBanner } from "../components/ErrorBanner";
import { Modal } from "../components/Modal";

function SourceForm({ onCreated, onClose }) {
  const [form, setForm] = useState({
    name: "",
    source_type: "network_device",
    vendor: "",
    product: "",
    description: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const src = await api.createSource({
        ...form,
        vendor: form.vendor || undefined,
        product: form.product || undefined,
        description: form.description || undefined,
      });
      onCreated(src);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <ErrorBanner message={error} />

      <div>
        <label className="label">Source Name *</label>
        <input className="input" required value={form.name} onChange={set("name")} placeholder="e.g. edge-firewall-01" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Type</label>
          <select className="input" value={form.source_type} onChange={set("source_type")}>
            <option value="network_device">Network Device</option>
            <option value="firewall">Firewall</option>
            <option value="ids">IDS/IPS</option>
            <option value="router">Router</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div>
          <label className="label">Vendor</label>
          <input className="input" value={form.vendor} onChange={set("vendor")} placeholder="e.g. Cisco" />
        </div>
      </div>
      <div>
        <label className="label">Product</label>
        <input className="input" value={form.product} onChange={set("product")} placeholder="e.g. ASA Firewall" />
      </div>
      <div>
        <label className="label">Description</label>
        <textarea className="input resize-none" rows={2} value={form.description} onChange={set("description")} placeholder="Optional description" />
      </div>

      <div className="flex justify-end gap-3 pt-2">
        <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? "Creating…" : "Create Source"}
        </button>
      </div>
    </form>
  );
}

export default function Sources() {
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const load = () => {
    setLoading(true);
    setError("");
    api.listSources()
      .then(setSources)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Sources</h1>
          <p className="text-sm text-slate-400 mt-1">
            Register perimeter network devices that produce logs for ingestion.
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={load}><RefreshCw className="w-4 h-4" /></button>
          <button className="btn-primary" onClick={() => setShowCreate(true)}>
            <Plus className="w-4 h-4" /> New Source
          </button>
        </div>
      </div>

      <ErrorBanner message={error} />

      {loading ? (
        <LoadingState />
      ) : sources.length === 0 ? (
        <div className="card p-10 text-center text-slate-400">
          <p className="text-sm">No sources registered yet.</p>
          <button className="btn-primary mt-4 mx-auto" onClick={() => setShowCreate(true)}>
            <Plus className="w-4 h-4" /> Register First Source
          </button>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-slate-700/60 text-slate-400 text-xs uppercase tracking-wider">
                <th className="table-cell">Name</th>
                <th className="table-cell">Type</th>
                <th className="table-cell">Vendor / Product</th>
                <th className="table-cell">Status</th>
                <th className="table-cell">ID</th>
                <th className="table-cell">Created</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.id} className="border-b border-slate-800 hover:bg-slate-800/50 transition-colors">
                  <td className="table-cell font-medium text-slate-200">{s.name}</td>
                  <td className="table-cell text-slate-400">{s.source_type}</td>
                  <td className="table-cell text-slate-400">
                    {[s.vendor, s.product].filter(Boolean).join(" / ") || "—"}
                  </td>
                  <td className="table-cell">
                    <span className={`badge border ${s.is_active ? "bg-green-900/60 text-green-300 border-green-700/60" : "bg-slate-700 text-slate-400 border-slate-600"}`}>
                      {s.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="table-cell mono text-slate-500">{shortId(s.id)}</td>
                  <td className="table-cell text-slate-400">{fmtDate(s.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && (
        <Modal title="Register New Source" onClose={() => setShowCreate(false)}>
          <SourceForm onCreated={(s) => setSources((prev) => [s, ...prev])} onClose={() => setShowCreate(false)} />
        </Modal>
      )}
    </div>
  );
}
