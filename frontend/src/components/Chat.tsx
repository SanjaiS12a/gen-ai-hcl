import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ChatResponse, Message } from "../types";
import { ErrorNotice, Loading, Meta } from "./Common";
import { usePreferences } from "../App";

const suggestions = [
  "How do I resolve this alert step by step?",
  "Is this likely a false positive?",
  "What should I check next?",
  "Summarize for my manager",
];
export default function Chat({
  id,
  messages,
  onMessages,
}: {
  id: string;
  messages: Message[];
  onMessages: (m: Message[]) => void;
}) {
  const [question, setQuestion] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [last, setLast] = useState<ChatResponse | null>(null);
  const { rulesOnly } = usePreferences();
  const active = useRef(true);
  const messagesRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const panel = messagesRef.current;
    if (panel) panel.scrollTop = panel.scrollHeight;
  }, [messages]);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  async function ask(text: string) {
    if (busy || text.trim().length < 3) return;
    setBusy(true);
    setError("");
    try {
      const response = await api<ChatResponse>(`/api/alerts/${id}/chat`, {
        question: text,
        rules_only: rulesOnly,
      });
      const history = await api<Message[]>(`/api/alerts/${id}/chat`);
      if (active.current) {
        setLast(response);
        onMessages(history);
        setQuestion("");
      }
    } catch (e) {
      if (active.current) setError((e as Error).message);
    } finally {
      if (active.current) setBusy(false);
    }
  }
  return (
    <section className="panel">
      <h2>Ask about this alert</h2>
      <p className="muted">
        This conversation is scoped to the selected alert.
      </p>
      <div className="suggestions">
        {suggestions.map((s) => (
          <button disabled={busy} key={s} onClick={() => ask(s)}>
            {s}
          </button>
        ))}
      </div>
      <div className="messages" aria-live="polite" ref={messagesRef}>
        {messages.map((m) => (
          <article className={`message ${m.role}`} key={m.id}>
            <strong>{m.role === "user" ? "You" : "Copilot"}</strong>
            <p>{m.content}</p>
            {m.role === "assistant" && (
              <small>
                {m.metadata.engine} · {m.metadata.provider} ·{" "}
                {((m.metadata.generation_ms ?? 0) / 1000).toFixed(1)} s
              </small>
            )}
          </article>
        ))}
      </div>
      {last && <Meta value={last} />}
      <ErrorNotice error={error} />
      {busy && <Loading label="Preparing scoped response" />}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask(question);
        }}
      >
        <label htmlFor="question">Follow-up question</label>
        <textarea
          id="question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={1000}
          rows={2}
          placeholder="What should I check next?"
        />
        <button
          className="primary"
          disabled={busy || question.trim().length < 3}
        >
          Ask copilot
        </button>
      </form>
    </section>
  );
}
