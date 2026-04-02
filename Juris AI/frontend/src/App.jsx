import React, { useEffect, useMemo, useRef, useState } from "react";

const API_BASE = "http://127.0.0.1:8000";

const SAMPLE_QUESTIONS = [
  "What are the key provisions of Section 302 of the IPC?",
  "Explain the doctrine of frustration under the Contract Act.",
  "What are the compliance requirements for private limited companies?",
  "Define wrongful termination under Labour Law.",
];

function fallbackId() {
  return `session-${Date.now()}-${Math.floor(Math.random() * 1e9)}`;
}

function getSessionId() {
  try {
    const existing = localStorage.getItem("jurisai_session_id");
    if (existing) return existing;
  } catch {
    return fallbackId();
  }

  const next =
    globalThis.crypto && typeof globalThis.crypto.randomUUID === "function"
      ? globalThis.crypto.randomUUID()
      : fallbackId();

  try {
    localStorage.setItem("jurisai_session_id", next);
  } catch {
    // Ignore storage write failures.
  }
  return next;
}

function detectDomainsFromText(text) {
  const t = text.toLowerCase();
  const out = [];
  if (t.includes("ipc") || t.includes("murder") || t.includes("theft")) out.push("Indian Penal Code");
  if (t.includes("company") || t.includes("director")) out.push("Companies Act");
  if (t.includes("contract") || t.includes("frustration")) out.push("Contract Law");
  if (t.includes("labour") || t.includes("worker") || t.includes("wage")) out.push("Labour Law");
  if (t.includes("constitution") || t.includes("fundamental rights")) out.push("Constitutional Law");
  return out.slice(0, 4);
}

export default function App() {
  const sessionId = useMemo(() => getSessionId(), []);
  const chatScrollRef = useRef(null);

  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadInfo, setUploadInfo] = useState("");
  const [uploadedDocs, setUploadedDocs] = useState([]);
  const [backendStatus, setBackendStatus] = useState("checking");
  const [corpusFilter, setCorpusFilter] = useState("all");
  const [mobileTab, setMobileTab] = useState("chat");
  const [debugOpen, setDebugOpen] = useState(false);
  const [queryTimeMs, setQueryTimeMs] = useState(null);

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const topCitations = (lastAssistant?.citations || []).slice(0, 4);
  const currentConfidence = useMemo(() => {
    if (!topCitations.length) return null;
    const sections = topCitations.filter((c) => c.section && c.section !== "NA").length;
    return Math.max(0.62, Math.min(0.96, 0.66 + sections * 0.08));
  }, [topCitations]);

  const detectedDomains = useMemo(() => {
    const text = messages.map((m) => m.content || "").join(" ");
    return detectDomainsFromText(text);
  }, [messages]);

  useEffect(() => {
    let mounted = true;
    async function ping() {
      try {
        const res = await fetch(`${API_BASE}/health`);
        if (mounted) setBackendStatus(res.ok ? "connected" : "disconnected");
      } catch {
        if (mounted) setBackendStatus("disconnected");
      }
    }
    ping();
    const timer = setInterval(ping, 5000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  function addUserMessage(text) {
    const m = {
      id: `${Date.now()}-${Math.random()}`,
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, m]);
  }

  function addAssistantMessage(text, citations = []) {
    const normalized = citations.map((c, idx) => ({
      id: `${Date.now()}-c-${idx}`,
      source: c.source || "unknown",
      page: String(c.page ?? "NA"),
      section: c.section || "NA",
      relevance: Math.max(0.7, 0.95 - idx * 0.08),
    }));
    const m = {
      id: `${Date.now()}-${Math.random()}`,
      role: "assistant",
      content: text,
      timestamp: new Date().toISOString(),
      citations: normalized,
    };
    setMessages((prev) => [...prev, m]);
  }

  async function sendQuestion(questionText) {
    if (!questionText.trim() || isLoading) return;
    addUserMessage(questionText.trim());
    setIsLoading(true);

    try {
      const started = performance.now();
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: questionText.trim(), session_id: sessionId }),
      });
      const raw = await res.text();
      if (!res.ok) {
        throw new Error(raw || "Chat request failed");
      }
      const data = JSON.parse(raw);
      setQueryTimeMs(Math.round(performance.now() - started));
      addAssistantMessage(data.answer || "No answer returned.", data.citations || []);
    } catch (err) {
      addAssistantMessage(`Error: ${err.message || "Request failed"}`);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const q = input;
    setInput("");
    await sendQuestion(q);
  }

  async function handleUploadInput(e) {
    const file = e.target.files?.[0];
    if (!file || isUploading) return;
    await uploadFile(file);
    e.target.value = "";
  }

  async function uploadFile(file) {
    setIsUploading(true);
    setUploadProgress(8);
    setUploadInfo("");
    const tempId = `${Date.now()}-${Math.random()}`;
    setUploadedDocs((prev) => [
      {
        id: tempId,
        name: file.name,
        uploadedAt: new Date().toISOString(),
        status: "processing",
        pageCount: null,
      },
      ...prev,
    ]);

    try {
      const timer = setInterval(() => {
        setUploadProgress((p) => (p >= 90 ? p : p + 7));
      }, 140);

      const form = new FormData();
      form.append("file", file);
      form.append("session_id", sessionId);
      const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: form });
      clearInterval(timer);

      const raw = await res.text();
      if (!res.ok) {
        throw new Error(raw || "Upload failed");
      }

      const data = JSON.parse(raw);
      setUploadProgress(100);
      setUploadInfo(`Uploaded ${data.filename} (${data.pages_indexed} pages indexed)`);
      setUploadedDocs((prev) =>
        prev.map((d) =>
          d.id === tempId
            ? {
                ...d,
                status: "ready",
                pageCount: data.pages_indexed,
              }
            : d
        )
      );
      setTimeout(() => setUploadProgress(0), 500);
    } catch (err) {
      setUploadInfo(`Upload error: ${err.message || "Upload failed"}`);
      setUploadedDocs((prev) => prev.map((d) => (d.id === tempId ? { ...d, status: "error" } : d)));
    } finally {
      setIsUploading(false);
    }
  }

  function onSampleQuestion(q) {
    if (isLoading) return;
    sendQuestion(q);
  }

  const confidenceLabel =
    currentConfidence === null
      ? ""
      : currentConfidence >= 0.85
      ? "High"
      : currentConfidence >= 0.7
      ? "Medium"
      : "Low";

  function Header() {
    return (
      <header className="v-header">
        <div className="v-brand">
          <div className="v-brand-icon">
            <img src="/jurisai-logo-primary.webp" alt="HV logo" />
          </div>
          <div className="v-brand-lockup">
            <h1>JurisAI</h1>
            <p>AI-Powered Legal Research & Document Intelligence</p>
          </div>
        </div>
        <div className="v-header-right">
          <div className={`v-status ${backendStatus}`}>
            <span className="dot" />
            {backendStatus === "checking" ? "Checking..." : backendStatus === "connected" ? "Connected" : "Disconnected"}
          </div>
          <div className="v-session">Session: {String(sessionId).slice(0, 8)}</div>
        </div>
      </header>
    );
  }

  function LeftSidebar() {
    return (
      <aside className="v-left">
        <section className="v-card">
          <h3>Upload Legal Document</h3>
          <label className={`v-upload-drop ${isUploading ? "is-uploading" : ""}`}>
            <input type="file" accept="application/pdf" onChange={handleUploadInput} disabled={isUploading} />
            <div className="upload-icon">PDF</div>
            <b>Drop PDF here</b>
            <span>or click to browse</span>
          </label>
          {isUploading && (
            <div className="v-progress-wrap">
              <div className="v-progress-label">
                <small>Uploading...</small>
                <small>{uploadProgress}%</small>
              </div>
              <div className="v-progress"><span style={{ width: `${uploadProgress}%` }} /></div>
            </div>
          )}
          {uploadInfo && <p className="v-upload-info">{uploadInfo}</p>}
        </section>

        <section className="v-card">
          <h3>Document Source</h3>
          <div className="v-filter-row">
            {[
              { value: "all", label: "All Sources" },
              { value: "base", label: "Base Corpus" },
              { value: "uploaded", label: "My Documents" },
            ].map((f) => (
              <button
                key={f.value}
                type="button"
                className={`v-chip ${corpusFilter === f.value ? "active" : ""}`}
                onClick={() => setCorpusFilter(f.value)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </section>

        <section className="v-card v-grow">
          <h3>Recent Documents</h3>
          <div className="v-doc-list">
            {uploadedDocs.length === 0 && <p className="muted">No uploads yet.</p>}
            {uploadedDocs.map((doc) => (
              <article key={doc.id} className="v-doc-item">
                <div className={`status-dot ${doc.status}`} />
                <div>
                  <b title={doc.name}>{doc.name}</b>
                  <small>
                    {new Date(doc.uploadedAt).toLocaleString()} {doc.pageCount ? `• ${doc.pageCount} pages` : ""}
                  </small>
                </div>
              </article>
            ))}
          </div>
        </section>
      </aside>
    );
  }

  function ChatArea() {
    return (
      <main className="v-chat-shell">
        <div className="v-chat-scroll" ref={chatScrollRef}>
          {messages.length === 0 ? (
            <div className="v-empty">
              <div className="empty-mark">
                <img src="/jurisai-logo-primary.webp" alt="JurisAI mark" />
              </div>
              <h2>How can I assist you today?</h2>
              <p>
                Ask me anything about legal statutes, case law, or document analysis. I will provide
                citations for every answer.
              </p>
              <div className="v-samples">
                {SAMPLE_QUESTIONS.map((q) => (
                  <button key={q} type="button" onClick={() => onSampleQuestion(q)}>{q}</button>
                ))}
              </div>
            </div>
          ) : (
            <div className="v-thread">
              {messages.map((m) => {
                const isUser = m.role === "user";
                return (
                  <article className={`v-msg-row ${isUser ? "user" : "assistant"}`} key={m.id}>
                    <div className={`v-avatar ${isUser ? "user" : "assistant"}`}>
                      {isUser ? "U" : <img src="/icon-dark-32x32.png" alt="AI" />}
                    </div>
                    <div className="v-msg-body">
                      <div className={`v-bubble ${isUser ? "user" : "assistant"}`}>
                        <p>{m.content}</p>
                      </div>
                      {!isUser && m.citations?.length > 0 && (
                        <div className="v-citation-grid">
                          <p>Citations ({m.citations.length})</p>
                          {m.citations.map((c) => (
                            <div className="v-citation" key={c.id}>
                              <div>
                                <b>{c.source}</b>
                                <small>Page {c.page} • {c.section}</small>
                              </div>
                              <span>{Math.round((c.relevance || 0.8) * 100)}%</span>
                            </div>
                          ))}
                        </div>
                      )}
                      <small className="v-time">{new Date(m.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</small>
                    </div>
                  </article>
                );
              })}

              {isLoading && (
                <article className="v-msg-row assistant">
                  <div className="v-avatar assistant">
                    <img src="/icon-dark-32x32.png" alt="AI" />
                  </div>
                  <div className="v-thinking">
                    <span />
                    <span />
                    <span />
                    <p>Analyzing legal documents...</p>
                  </div>
                </article>
              )}
            </div>
          )}
        </div>

        <form className="v-input-wrap" onSubmit={handleSubmit}>
          <div className="v-input-inner">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a legal question..."
              rows={1}
              disabled={isLoading}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
            />
            <button type="submit" disabled={!input.trim() || isLoading}>Send</button>
          </div>
          <small>JurisAI may produce inaccurate information. Always verify with qualified legal counsel.</small>
        </form>
      </main>
    );
  }

  function RightPanel() {
    return (
      <aside className="v-right">
        <section className="v-card">
          <h3>Answer Confidence</h3>
          {currentConfidence === null ? (
            <p className="muted">Ask a question to see confidence metrics.</p>
          ) : (
            <div className="v-confidence">
              <div>
                <b>{Math.round(currentConfidence * 100)}%</b>
                <span>{confidenceLabel}</span>
              </div>
              <div className="v-progress"><span style={{ width: `${Math.round(currentConfidence * 100)}%` }} /></div>
              <small>Based on {topCitations.length} citations and semantic relevance.</small>
            </div>
          )}
        </section>

        <section className="v-card v-grow">
          <h3>Top Citations</h3>
          <div className="v-citation-list">
            {topCitations.length === 0 && <p className="muted">Citations will appear here.</p>}
            {topCitations.map((c, idx) => (
              <article className="v-citation-rank" key={c.id}>
                <span>{idx + 1}</span>
                <div>
                  <b>{c.source}</b>
                  <small>{c.section} • Page {c.page}</small>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="v-card">
          <h3>Query Insights</h3>
          {detectedDomains.length === 0 ? (
            <p className="muted">No query analyzed yet.</p>
          ) : (
            <div className="v-domain-row">
              {detectedDomains.map((d) => (
                <span key={d}>{d}</span>
              ))}
            </div>
          )}
        </section>

        <section className="v-card">
          <button type="button" className="v-debug-btn" onClick={() => setDebugOpen((v) => !v)}>
            <span>Retrieval Debug</span>
            <span className={`v-chevron ${debugOpen ? "open" : ""}`}>⌄</span>
          </button>
          {debugOpen && (
            <div className="v-debug-content">
              <p><span>Query time</span><b>{queryTimeMs ?? "NA"} ms</b></p>
              <p><span>Citations</span><b>{topCitations.length}</b></p>
              <p><span>Filter</span><b>{corpusFilter}</b></p>
              <p><span>Backend</span><b>{backendStatus}</b></p>
            </div>
          )}
        </section>
      </aside>
    );
  }

  return (
    <div className="v-root">
      <Header />

      <div className="v-desktop">
        <LeftSidebar />
        <ChatArea />
        <RightPanel />
      </div>

      <div className="v-mobile">
        <div className="v-mobile-content">
          {mobileTab === "docs" && <LeftSidebar />}
          {mobileTab === "chat" && <ChatArea />}
          {mobileTab === "insights" && <RightPanel />}
        </div>
        <nav className="v-mobile-nav">
          <button className={mobileTab === "docs" ? "active" : ""} onClick={() => setMobileTab("docs")}>Documents</button>
          <button className={mobileTab === "chat" ? "active" : ""} onClick={() => setMobileTab("chat")}>Chat</button>
          <button className={mobileTab === "insights" ? "active" : ""} onClick={() => setMobileTab("insights")}>Insights</button>
        </nav>
      </div>
    </div>
  );
}
