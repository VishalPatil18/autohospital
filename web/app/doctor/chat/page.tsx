"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth-provider";
import Nav from "@/components/nav";

interface Message {
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

interface Patient {
  user_id: string;
  first_name: string;
  last_name: string;
}

export default function DoctorChatPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState<string>("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!loading && (!user || user.role !== "doctor")) {
      router.push("/login");
    }
  }, [user, loading, router]);

  // Load care-team patients for the filter dropdown (Next BFF → FastAPI)
  useEffect(() => {
    if (!user || user.role !== "doctor") return;
    fetch("/api/doctors/me/patients", { credentials: "include" })
      .then(async (r) => {
        const data = await r.json().catch(() => null);
        if (r.ok && Array.isArray(data)) setPatients(data as Patient[]);
      })
      .catch(() => {});
  }, [user]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage() {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;

    setInput("");
    setError(null);
    setIsStreaming(true);

    // Append user message immediately
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    // Placeholder for the streaming assistant message
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", isStreaming: true },
    ]);

    const body: Record<string, unknown> = { message: trimmed };
    if (conversationId) body.conversation_id = conversationId;
    if (selectedPatientId) body.patient_id = selectedPatientId;

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch("/api/chat/doctor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        const err = (await response.json().catch(() => ({}))) as { detail?: unknown };
        const d = err?.detail;
        const detail =
          typeof d === "string"
            ? d
            : Array.isArray(d)
              ? d.map((x: { msg?: string }) => x?.msg).filter(Boolean).join(", ")
              : `HTTP ${response.status}`;
        // Drop optimistic user + empty assistant rows when the request never streamed
        setMessages((prev) => prev.slice(0, -2));
        throw new Error(detail || `HTTP ${response.status}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const json = line.slice(6).trim();
          if (!json) continue;

          let parsed: Record<string, unknown>;
          try {
            parsed = JSON.parse(json);
          } catch {
            continue;
          }

          if ("token" in parsed && typeof parsed.token === "string") {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last?.role === "assistant") {
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + parsed.token,
                };
              }
              return updated;
            });
          }

          if (parsed.done === true && typeof parsed.conversation_id === "string") {
            setConversationId(parsed.conversation_id);
          }

          if (parsed.error) {
            setError("Something went wrong. Please try again.");
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name !== "AbortError") {
        setError((err as Error).message ?? "Connection error");
      }
    } finally {
      // Mark streaming done on the last message
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last?.isStreaming) {
          updated[updated.length - 1] = { ...last, isStreaming: false };
        }
        return updated;
      });
      setIsStreaming(false);
      abortRef.current = null;
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function resetConversation() {
    abortRef.current?.abort();
    setMessages([]);
    setConversationId(null);
    setError(null);
  }

  if (loading || !user) return null;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Nav />

      <div className="flex-1 flex flex-col max-w-3xl mx-auto w-full px-4 py-6 gap-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Clinical Assistant</h1>
            <p className="text-sm text-slate-500">
              Ask questions about your patients' records. Scope is restricted to your care team.
            </p>
          </div>
          <button
            onClick={resetConversation}
            className="text-xs text-slate-400 hover:text-slate-600 underline"
          >
            New conversation
          </button>
        </div>

        {/* Patient filter */}
        <div className="bg-white border border-slate-200 rounded-lg px-4 py-3 flex items-center gap-3">
          <label className="text-sm font-medium text-slate-600 whitespace-nowrap">
            Patient scope
          </label>
          <select
            value={selectedPatientId}
            onChange={(e) => {
              setSelectedPatientId(e.target.value);
              resetConversation();
            }}
            className="flex-1 text-sm border-0 bg-transparent focus:ring-0 text-slate-900"
          >
            <option value="">All my patients</option>
            {patients.map((p) => (
              <option key={p.user_id} value={p.user_id}>
                {p.first_name} {p.last_name}
              </option>
            ))}
          </select>
        </div>

        {/* Messages */}
        <div className="flex-1 flex flex-col gap-3 overflow-y-auto min-h-0 max-h-[56vh]">
          {messages.length === 0 && (
            <div className="flex-1 flex flex-col items-center justify-center text-center text-slate-400 py-12 gap-2">
              <svg className="w-10 h-10 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
              <p className="text-sm">Ask a clinical question about your patient records.</p>
              <p className="text-xs text-slate-300">
                Examples: "What medications is Patient X on?" • "Any abnormal lab values this visit?"
              </p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-br-sm"
                    : "bg-white border border-slate-200 text-slate-800 rounded-bl-sm shadow-sm"
                }`}
              >
                {msg.content || (msg.isStreaming ? (
                  <span className="inline-flex gap-1 items-center text-slate-400">
                    <span className="animate-bounce">•</span>
                    <span className="animate-bounce [animation-delay:0.15s]">•</span>
                    <span className="animate-bounce [animation-delay:0.3s]">•</span>
                  </span>
                ) : "")}
              </div>
            </div>
          ))}

          {error && (
            <div className="text-center text-xs text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="bg-white border border-slate-200 rounded-2xl shadow-sm flex items-end gap-2 px-4 py-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
            placeholder="Ask a clinical question… (Enter to send, Shift+Enter for newline)"
            rows={2}
            className="flex-1 resize-none text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none bg-transparent"
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isStreaming}
            className="flex-shrink-0 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400 text-white rounded-xl px-4 py-2 text-sm font-medium transition-colors"
          >
            {isStreaming ? "…" : "Send"}
          </button>
        </div>

        {/* Safety notice */}
        <p className="text-center text-xs text-slate-400">
          AI-generated clinical summaries are decision support only — not a substitute for clinical judgement.
        </p>
      </div>
    </div>
  );
}
