import React, { useState } from 'react';

interface AIAssistantWidgetProps {
  apiBase: string;
  addToast: (type: 'success' | 'error' | 'info', message: string) => void;
  commentaries: { commentary: string; timestamp: string }[];
}

export const AIAssistantWidget = React.memo(({ apiBase, addToast, commentaries }: AIAssistantWidgetProps) => {
  const [chatMessages, setChatMessages] = useState<{ sender: "operator" | "ai"; text: string }[]>([
    { sender: "ai", text: "Hello Operator. Ask me anything about arena logs or incidents." },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [isChatSending, setIsChatSending] = useState(false);

  const sendChatMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    const query = chatInput.trim();
    if (!query) return;
    setChatMessages((prev) => [...prev, { sender: "operator" as "operator", text: query }].slice(-50));
    setChatInput("");
    setIsChatSending(true);
    try {
      const res = await fetch(apiBase + "/api/v1/ai/assistant", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Requested-With": "CourtOS-Client" },
        body: JSON.stringify({ query }),
      });
      if (!res.ok) throw new Error("API failure");
      const data = await res.json();
      setChatMessages((prev) => [...prev, { sender: "ai" as "ai", text: data.reply }].slice(-50));
    } catch (err) {
      addToast("error", "AI Assistant failed to reply. Please check your credentials and connection.");
      setChatMessages((prev) => [...prev, { sender: "ai" as "ai", text: "Error: Failed to obtain response from Gemini AI. Check server logs." }].slice(-50));
    } finally {
      setIsChatSending(false);
    }
  };

  return (
    <>
      <section className="panel" style={{ gridArea: "assistant", maxHeight: "450px" }} aria-labelledby="assistant-heading">
        <div className="panel-header">
          <h2 id="assistant-heading" className="panel-title">AI Operator Assistant</h2>
          <span className="badge badge-simulated">LangGraph Router</span>
        </div>
        <div style={{ flexGrow: 1, display: "flex", flexDirection: "column", gap: "var(--space-2)", overflow: "hidden" }}>
          <div style={{ flexGrow: 1, overflowY: "auto", backgroundColor: "var(--color-surface-elevated)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-md)", padding: "var(--space-3)", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            {chatMessages.map((msg, idx) => (
              <div key={idx} style={{ alignSelf: msg.sender === "operator" ? "flex-end" : "flex-start", backgroundColor: msg.sender === "operator" ? "var(--color-focus)" : "var(--color-border)", color: msg.sender === "operator" ? "#FFFFFF" : "var(--color-text-primary)", padding: "8px 12px", borderRadius: "8px", maxWidth: "85%", fontSize: "var(--text-sm)", wordBreak: "break-word" }}>
                <p style={{ fontSize: "10px", color: msg.sender === "operator" ? "rgba(255,255,255,0.7)" : "var(--color-text-secondary)", marginBottom: "2px", fontWeight: "bold" }}>{msg.sender === "operator" ? "OPERATOR" : "AI"}</p>
                <p>{msg.text}</p>
              </div>
            ))}
          </div>
          <form onSubmit={sendChatMessage} style={{ display: "flex", gap: "var(--space-2)", marginTop: "2px" }}>
            <input type="text" className="btn" style={{ flexGrow: 1, textAlign: "left", cursor: "text" }} placeholder="Ask AI (e.g. show incident count)..." value={chatInput} onChange={(e) => setChatInput(e.target.value)} disabled={isChatSending} aria-label="Ask AI Assistant input field" />
            <button type="submit" className="btn" disabled={isChatSending || !chatInput.trim()} aria-label="Send query to AI">{isChatSending ? "..." : "Ask"}</button>
          </form>
        </div>
      </section>
      <section className="panel" style={{ gridArea: "commentary", maxHeight: "350px" }} aria-labelledby="commentary-heading">
        <div className="panel-header">
          <h2 id="commentary-heading" className="panel-title">AI Sports Commentary</h2>
          <span className="badge badge-live">Live play-by-play</span>
        </div>
        <ul className="scroll-list" style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          {commentaries.length === 0 ? (
            <li style={{ textAlign: "center", color: "var(--color-text-secondary)", padding: "var(--space-6) 0" }}>Waiting for game events to commentate...</li>
          ) : (
            commentaries.map((com, idx) => (
              <li key={idx} style={{ display: "flex", flexDirection: "column", gap: "4px", padding: "var(--space-2)", backgroundColor: "var(--color-surface-elevated)", borderLeft: "4px solid var(--color-simulated)", borderRadius: "var(--radius-sm)", fontSize: "var(--text-sm)" }} aria-label={`Commentary at ${new Date(com.timestamp).toLocaleTimeString()}: ${com.commentary}`}>
                <p style={{ fontStyle: "italic" }}>🎙️ "{com.commentary}"</p>
                <span style={{ fontSize: "10px", color: "var(--color-text-secondary)", alignSelf: "flex-end" }}>{new Date(com.timestamp).toLocaleTimeString()}</span>
              </li>
            ))
          )}
        </ul>
      </section>
    </>
  );
});