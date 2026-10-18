import { useState, useRef, useEffect } from "react";
import Editor from "@monaco-editor/react";
import "./App.css";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function Tree({ nodes, path = "", onOpen, glow, active }) {
  return (
    <ul className="tree">
      {nodes.map((n) => {
        const full = path ? `${path}/${n.name}` : n.name;
        if (n.type === "folder") {
          return <Folder key={full} node={n} full={full} onOpen={onOpen} glow={glow} active={active} />;
        }
        const cls = "file" + (glow.has(full) ? " glow" : "") + (active === full ? " active" : "");
        return (
          <li key={full} className={cls} onClick={() => onOpen(full)}>
            📄 {n.name}
          </li>
        );
      })}
    </ul>
  );
}

function Folder({ node, full, onOpen, glow, active }) {
  const hasGlow = [...glow].some((g) => g.startsWith(full + "/"));
  const [open, setOpen] = useState(false);
  const shown = open || hasGlow;
  return (
    <li>
      <div className="folder" onClick={() => setOpen(!open)}>
        {shown ? "📂" : "📁"} {node.name}
      </div>
      {shown && <Tree nodes={node.children} path={full} onOpen={onOpen} glow={glow} active={active} />}
    </li>
  );
}

export default function App() {
  const [url, setUrl] = useState("https://github.com/pallets/flask");
  const [repo, setRepo] = useState("");
  const [tree, setTree] = useState([]);
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState({ path: "", content: "" });
  const [highlight, setHighlight] = useState(null);
  const [glow, setGlow] = useState(new Set());
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [thinking, setThinking] = useState(false);
  const editorRef = useRef(null);
  const monacoRef = useRef(null);
  const decoRef = useRef([]);

  async function loadRepo() {
    setLoading(true);
    try {
      const res = await fetch(`${API}/load`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      setRepo(data.repo);
      setTree(data.tree);
      setMessages([{ role: "cairn", text: `Loaded ${data.repo}. Ask me anything about it.` }]);
    } catch {
      alert("Could not load. Is the backend running?");
    }
    setLoading(false);
  }

  async function openFile(path, lines) {
    const res = await fetch(`${API}/file?repo=${repo}&path=${encodeURIComponent(path)}`);
    if (!res.ok) return;
    const data = await res.json();
    setFile(data);
    setHighlight(lines || null);
  }

  async function sendQuestion() {
    if (!question.trim() || !repo) return;
    const q = question;
    setQuestion("");
    setMessages((m) => [...m, { role: "you", text: q }]);
    setThinking(true);
    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo, question: q }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);
      const unique = [];
      const seen = new Set();
      for (const s of data.sources) {
        const key = `${s.file}:${s.start_line}-${s.end_line}`;
        if (!seen.has(key)) { seen.add(key); unique.push(s); }
      }
      setMessages((m) => [...m, { role: "cairn", text: data.answer, sources: unique.slice(0, 6) }]);
      setGlow(new Set(unique.map((s) => s.file)));
      if (unique[0]) openFile(unique[0].file, [unique[0].start_line, unique[0].end_line]);
    } catch (e) {
      setMessages((m) => [...m, { role: "cairn", text: "Sorry, something went wrong: " + e.message }]);
    }
    setThinking(false);
  }

  useEffect(() => {
    if (!editorRef.current || !monacoRef.current) return;
    const monaco = monacoRef.current;
    if (!highlight) {
      decoRef.current = editorRef.current.deltaDecorations(decoRef.current, []);
      return;
    }
    const [a, b] = highlight;
    decoRef.current = editorRef.current.deltaDecorations(decoRef.current, [
      { range: new monaco.Range(a, 1, b, 1), options: { isWholeLine: true, className: "cited-lines" } },
    ]);
    editorRef.current.revealLineInCenter(a);
  }, [highlight, file]);

  return (
    <div className="app">
      <header>
        <span className="logo">🪨 Cairn</span>
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="Paste a GitHub URL" />
        <button onClick={loadRepo} disabled={loading}>{loading ? "Loading..." : "Load"}</button>
      </header>

      <main>
        <aside className="panel left">
          <h3>File map {repo && `· ${repo}`}</h3>
          <Tree nodes={tree} onOpen={(p) => openFile(p)} glow={glow} active={file.path} />
        </aside>

        <section className="panel middle">
          <h3>{file.path || "Code viewer"}</h3>
          <Editor
            height="calc(100vh - 100px)"
            theme="vs-dark"
            path={file.path}
            value={file.content}
            options={{ readOnly: true, minimap: { enabled: false }, fontSize: 13 }}
            onMount={(editor, monaco) => { editorRef.current = editor; monacoRef.current = monaco; }}
          />
        </section>

        <aside className="panel right">
          <h3>Chat with Cairn</h3>
          <div className="messages">
            {messages.map((m, i) => (
              <div key={i} className={"msg " + m.role}>
                <div className="text">{m.text}</div>
                {m.sources && (
                  <div className="sources">
                    {m.sources.map((s, j) => (
                      <button key={j} onClick={() => openFile(s.file, [s.start_line, s.end_line])}>
                        {s.file.split("/").pop()}:{s.start_line}-{s.end_line}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {thinking && <div className="msg cairn">Thinking...</div>}
          </div>
          <div className="ask">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendQuestion()}
              placeholder={repo ? "Ask about the code..." : "Load a repo first"}
            />
            <button onClick={sendQuestion} disabled={thinking}>Ask</button>
          </div>
        </aside>
      </main>
    </div>
  );
}