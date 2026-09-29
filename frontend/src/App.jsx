import { Routes, Route } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Sources    from "./pages/Sources";
import Ingest     from "./pages/Ingest";
import Jobs       from "./pages/Jobs";
import Events     from "./pages/Events";
import Evidence   from "./pages/Evidence";
import Export     from "./pages/Export";

export default function App() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-y-auto px-6 lg:px-10 py-8">
        <div className="max-w-6xl mx-auto">
          <Routes>
            <Route path="/"         element={<Dashboard />} />
            <Route path="/sources"  element={<Sources />} />
            <Route path="/ingest"   element={<Ingest />} />
            <Route path="/jobs"     element={<Jobs />} />
            <Route path="/events"   element={<Events />} />
            <Route path="/evidence" element={<Evidence />} />
            <Route path="/export"   element={<Export />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}
