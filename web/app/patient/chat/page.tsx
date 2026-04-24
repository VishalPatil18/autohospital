"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth-provider";
import Nav from "@/components/nav";
import { post } from "@/lib/api";

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
}

export default function PatientChatPage() {
    const { user, loading } = useAuth();
    const router = useRouter();

    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [conversationId, setConversationId] = useState<string | null>(null);

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const eventSourceRef = useRef<EventSource | null>(null);

    useEffect(() => {
        if (!loading && !user) {
            router.push("/login");
        }
        if (!loading && user && user.role !== "patient") {
            router.push("/doctor/dashboard");
        }
    }, [user, loading, router]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const handleSendMessage = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!input.trim() || isLoading || !user) return;

        const userMessage: Message = {
            id: Date.now().toString(),
            role: "user",
            content: input,
        };

        setMessages((prev) => [...prev, userMessage]);
        setInput("");
        setIsLoading(true);
        setError(null);

        const assistantMessageId = Date.now().toString() + "_asst";
        const assistantMessage: Message = {
            id: assistantMessageId,
            role: "assistant",
            content: "",
        };
        setMessages((prev) => [...prev, assistantMessage]);

        try {
            // Send message to API with SSE stream
            const response = await fetch("http://localhost:8000/api/chat/patient", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                credentials: "include",
                body: JSON.stringify({
                    message: input,
                    conversation_id: conversationId,
                }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => null);
                throw new Error(errorData?.detail || `HTTP ${response.status}`);
            }

            const reader = response.body?.getReader();
            if (!reader) {
                throw new Error("No response body");
            }

            const decoder = new TextDecoder();
            let buffer = "";
            let newConvId = conversationId;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // Process complete SSE messages (ending with \n\n)
                const lines = buffer.split("\n\n");
                buffer = lines.pop() || ""; // Keep incomplete message in buffer

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const jsonStr = line.slice(6);
                            const event = JSON.parse(jsonStr);

                            if (event.type === "conversation_id") {
                                newConvId = event.value;
                                setConversationId(event.value);
                            } else if (event.type === "token") {
                                setMessages((prev) =>
                                    prev.map((msg) =>
                                        msg.id === assistantMessageId
                                            ? { ...msg, content: msg.content + event.value }
                                            : msg
                                    )
                                );
                            } else if (event.type === "error") {
                                setError(event.value);
                            }
                        } catch (err) {
                            console.error("Failed to parse SSE message:", err);
                        }
                    }
                }
            }
        } catch (err) {
            const message = err instanceof Error ? err.message : "Chat failed";
            setError(message);
            console.error("Chat error:", err);

            // Remove incomplete assistant message on error
            setMessages((prev) =>
                prev.filter((msg) => msg.id !== assistantMessageId)
            );
        } finally {
            setIsLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-slate-400 text-sm">Loading...</div>
            </div>
        );
    }

    if (!user) return null;

    return (
        <div className="min-h-screen bg-slate-50 flex flex-col">
            <Nav />

            <main className="flex-1 max-w-2xl w-full mx-auto px-4 py-8 flex flex-col">
                {/* Header */}
                <div className="mb-6">
                    <h1 className="text-2xl font-bold text-slate-900">Health Assistant</h1>
                    <p className="text-slate-500 mt-1">
                        Ask questions about your health documents and recent visits
                    </p>
                </div>

                {/* Messages Container */}
                <div className="flex-1 bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6 overflow-y-auto">
                    {messages.length === 0 ? (
                        <div className="h-full flex items-center justify-center text-center">
                            <div>
                                <p className="text-slate-400 text-sm">
                                    No messages yet. Start a conversation with your health assistant.
                                </p>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {messages.map((message) => (
                                <div
                                    key={message.id}
                                    className={`flex ${message.role === "user" ? "justify-end" : "justify-start"
                                        }`}
                                >
                                    <div
                                        className={`max-w-xs lg:max-w-md px-4 py-3 rounded-lg ${message.role === "user"
                                                ? "bg-blue-600 text-white rounded-br-none"
                                                : "bg-slate-100 text-slate-900 rounded-bl-none"
                                            }`}
                                    >
                                        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                                    </div>
                                </div>
                            ))}
                            {isLoading && messages[messages.length - 1]?.role === "assistant" && (
                                <div className="flex justify-start">
                                    <div className="bg-slate-100 text-slate-600 px-4 py-3 rounded-lg rounded-bl-none text-sm">
                                        <span className="inline-block animate-pulse">●</span>
                                    </div>
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>
                    )}
                </div>

                {/* Error Message */}
                {error && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4 text-red-700 text-sm">
                        {error}
                    </div>
                )}

                {/* Input Form */}
                <form onSubmit={handleSendMessage} className="flex gap-3">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Ask a question..."
                        disabled={isLoading}
                        className="flex-1 px-4 py-3 rounded-lg border border-slate-200 bg-white text-slate-900 placeholder-slate-400 disabled:bg-slate-50 disabled:text-slate-400"
                    />
                    <button
                        type="submit"
                        disabled={isLoading || !input.trim()}
                        className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition"
                    >
                        Send
                    </button>
                </form>
            </main>
        </div>
    );
}
