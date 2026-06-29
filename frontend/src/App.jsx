import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./App.css";

const API_URL = "http://localhost:5000/chat";

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const messagesRef = useRef(null);

  // keep the latest message in view as content streams in
  useEffect(() => {
    const el = messagesRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  // update the in-flight assistant message (always the last one)
  const updateLast = (updater) => {
    setMessages((prev) => {
      const next = prev.slice();
      next[next.length - 1] = updater(next[next.length - 1]);
      return next;
    });
  };

  const handleEvent = (evt) => {
    if (evt.type === "token") {
      updateLast((m) => ({ ...m, content: m.content + evt.content }));
    } else if (evt.type === "tool") {
      if (evt.status === "start") {
        updateLast((m) => ({
          ...m,
          tools: [
            ...m.tools,
            { name: evt.name, label: evt.label, status: "running" },
          ],
        }));
      } else {
        updateLast((m) => ({
          ...m,
          tools: m.tools.map((t) =>
            t.status === "running" && t.name === evt.name
              ? { ...t, status: "done" }
              : t
          ),
        }));
      }
    } else if (evt.type === "done") {
      updateLast((m) => ({ ...m, pending: false }));
    } else if (evt.type === "error") {
      updateLast((m) => ({
        ...m,
        pending: false,
        error: true,
        content: (m.content ? m.content + "\n\n" : "") + `Error: ${evt.message}`,
      }));
    }
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || busy) return;

    setInput("");
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: "", tools: [], pending: true },
    ]);

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      if (!res.ok || !res.body) throw new Error(`Server error (${res.status})`);

      // read the NDJSON stream line by line
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let nl;
        while ((nl = buffer.indexOf("\n")) >= 0) {
          const line = buffer.slice(0, nl).trim();
          buffer = buffer.slice(nl + 1);
          if (line) handleEvent(JSON.parse(line));
        }
      }
    } catch (err) {
      updateLast((m) => ({
        ...m,
        pending: false,
        error: true,
        content: `Error: ${err.message}. Is the backend running on port 5000?`,
      }));
    } finally {
      setBusy(false);
    }
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-title">Schedule Guru</div>
      </header>

      <div className="chat-container">
        <div className="messages" ref={messagesRef}>
          {messages.length === 0 && (
            <div className="empty-state">
              Ask me to check your schedule, create events, or move things
              around.
            </div>
          )}

          {messages.map((m, i) => (
            <Message key={i} message={m} />
          ))}
        </div>

        <div className="input-area">
          <div className="input-inner">
            <textarea
              rows={1}
              value={input}
              placeholder="Type your message…"
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
            />
            <button onClick={sendMessage} disabled={busy || !input.trim()}>
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Message({ message }) {
  const { role, content, tools = [], pending, error } = message;

  if (role === "user") {
    return (
      <div className="message user">
        <div className="bubble">{content}</div>
      </div>
    );
  }

  // assistant: show a typing indicator until tokens/tools start arriving
  const anyRunning = tools.some((t) => t.status === "running");
  const showTyping = pending && !content && !anyRunning;

  return (
    <div className="message assistant">
      <div className={`bubble ${error ? "error" : ""}`}>
        {tools.length > 0 && (
          <div className="tools">
            {tools.map((t, i) => (
              <ToolChip key={i} tool={t} />
            ))}
          </div>
        )}

        {showTyping && <TypingDots />}

        {content && (
          <div className="markdown">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: (props) => (
                  <a target="_blank" rel="noreferrer" {...props} />
                ),
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}

function ToolChip({ tool }) {
  const running = tool.status === "running";
  return (
    <div className={`tool-chip ${running ? "running" : "done"}`}>
      <span className={running ? "spinner" : "check"} aria-hidden="true" />
      <span>
        {tool.label}
        {running ? "…" : ""}
      </span>
    </div>
  );
}

function TypingDots() {
  return (
    <div className="typing" aria-label="Assistant is thinking">
      <span />
      <span />
      <span />
    </div>
  );
}

export default App;
