import { useState, useEffect } from "react";
import "./App.css";

const API_BASE = "http://127.0.0.1:8000";

function PromptLog() {
  const [prompts, setPrompts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/prompts`)
      .then((res) => {
        if (!res.ok) throw new Error(`Request failed: ${res.status}`);
        return res.json();
      })
      .then((data) => setPrompts(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="status">Loading prompts...</p>;
  if (error) return <p className="status error">Error: {error}</p>;
  if (prompts.length === 0) return <p className="status">No prompts captured yet.</p>;

  return (
    <div className="card-list">
      {prompts.map((p) => (
        <div key={p.id} className="card">
          <p className="sanitized-text">{p.sanitized_text}</p>
          <div className="tag-row">
            {Object.entries(p.detections || {}).map(([type, count]) => (
              <span key={type} className="tag">
                {type} × {count}
              </span>
            ))}
          </div>
          <p className="timestamp">{new Date(p.created_at).toLocaleString()}</p>
        </div>
      ))}
    </div>
  );
}

function AgentRuns() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/runs`)
      .then((res) => {
        if (!res.ok) throw new Error(`Request failed: ${res.status}`);
        return res.json();
      })
      .then((data) => setRuns(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="status">Loading runs...</p>;
  if (error) return <p className="status error">Error: {error}</p>;
  if (runs.length === 0) return <p className="status">No agent runs yet.</p>;

  return (
    <div className="card-list">
      {runs.map((r) => (
        <div key={r.run_id} className={`card ${r.has_unexpected_access ? "flagged" : ""}`}>
          <div className="run-header">
            <strong>{r.asset}</strong>
            {r.has_unexpected_access && <span className="badge">Unexpected access</span>}
          </div>
          <div className="access-row">
            <div>
              <span className="label">Declared</span>
              <p>{r.declared_data_sources.join(", ") || "—"}</p>
            </div>
            <div>
              <span className="label">Observed</span>
              <p>{r.observed_data_sources.join(", ") || "—"}</p>
            </div>
          </div>
          {r.has_unexpected_access && (
            <p className="unexpected-detail">
              Unexpected: {r.unexpected_access.join(", ")}
            </p>
          )}
          <p className="timestamp">
            {r.model} · {r.input_tokens}/{r.output_tokens} tokens ·{" "}
            {new Date(r.started_at).toLocaleString()}
          </p>
        </div>
      ))}
    </div>
  );
}

function PIISummary() {
  const [summary, setSummary] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/prompts/pii-summary`)
      .then((res) => {
        if (!res.ok) throw new Error(`Request failed: ${res.status}`);
        return res.json();
      })
      .then((data) => setSummary(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="status">Loading summary...</p>;
  if (error) return <p className="status error">Error: {error}</p>;
  if (summary.length === 0) return <p className="status">No PII detections yet.</p>;

  return (
    <table className="summary-table">
      <thead>
        <tr>
          <th>AI Asset</th>
          <th>PII Type</th>
          <th>Total Detections</th>
        </tr>
      </thead>
      <tbody>
        {summary.map((row, i) => (
          <tr key={i}>
            <td>{row.asset}</td>
            <td>{row.entity_type}</td>
            <td>{row.total}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function App() {
  const [tab, setTab] = useState("prompts");

  return (
    <div className="app">
      <header>
        <h1>AI Usage Monitoring</h1>
        <p className="subtitle">Governance visibility for AI activity</p>
      </header>

      <nav className="tabs">
        <button className={tab === "prompts" ? "active" : ""} onClick={() => setTab("prompts")}>
          Prompt Log
        </button>
        <button className={tab === "runs" ? "active" : ""} onClick={() => setTab("runs")}>
          Agent Runs
        </button>
        <button className={tab === "summary" ? "active" : ""} onClick={() => setTab("summary")}>
          PII Summary
        </button>
      </nav>

      <main>
        {tab === "prompts" && <PromptLog />}
        {tab === "runs" && <AgentRuns />}
        {tab === "summary" && <PIISummary />}
      </main>
    </div>
  );
}

export default App;
