"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MessageSquare, Send, Trash2, X, Bot, User, Loader2, Sparkles } from "lucide-react";
import { aiApi } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ChatPanelProps {
  agentType: string;
  agentName?: string;
  externalOpen?: boolean;
  onExternalClose?: () => void;
}

export function ChatPanel({ agentType, agentName, externalOpen, onExternalClose }: ChatPanelProps) {
  const [open, setOpen] = useState(false);
  const isOpen = externalOpen ?? open;
  const handleClose = () => { setOpen(false); onExternalClose?.(); };
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastModel, setLastModel] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [open]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text, timestamp: Date.now() }]);
    setLoading(true);

    try {
      const res = await aiApi.chat(text, agentType);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.reply,
          timestamp: Date.now(),
          provider: res.provider,
          model: res.model,
        },
      ]);
      setLastModel(`${res.provider}/${res.model}`);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I'm unable to respond right now. Please try again.",
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, agentType]);

  const clearChat = async () => {
    try {
      await aiApi.clearChat(agentType);
    } catch {
      // ignore
    }
    setMessages([]);
    setLastModel(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      {/* Floating toggle button — hidden on mobile (in hamburger menu instead) */}
      {!isOpen && (
        <button
          onClick={() => setOpen(true)}
          className="hidden md:flex fixed bottom-6 right-6 z-50 h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-[#06d6a0] to-[#0ff0b3] shadow-lg shadow-[#06d6a0]/25 transition-transform hover:scale-105 active:scale-95"
          title="Open AI Assistant"
        >
          <Sparkles className="h-6 w-6 text-[#0d0d12]" />
        </button>
      )}

      {/* Panel */}
      <div
        className={cn(
          "fixed bottom-0 right-0 z-[60] flex h-[80vh] md:h-[600px] w-full md:w-[400px] flex-col rounded-t-2xl md:rounded-tl-2xl md:rounded-tr-none border border-[var(--glass-border)] backdrop-blur-xl transition-transform duration-300",
          "bg-[var(--surface)]",
          isOpen ? "translate-x-0" : "translate-x-full",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.06)] px-4 py-3">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-[#06d6a0]" />
            <div>
              <h3 className="text-sm font-semibold text-white">
                {agentName || "AI Assistant"}
              </h3>
              {lastModel && (
                <span className="text-[12px] text-[#55556a]">{lastModel}</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={clearChat}
              className="rounded-lg p-1.5 text-[#55556a] transition-colors hover:bg-[rgba(255,255,255,0.05)] hover:text-[#8888a0]"
              title="Clear conversation"
            >
              <Trash2 className="h-4 w-4" />
            </button>
            <button
              onClick={handleClose}
              className="rounded-lg p-1.5 text-[#55556a] transition-colors hover:bg-[rgba(255,255,255,0.05)] hover:text-[#8888a0]"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 custom-scrollbar">
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <MessageSquare className="mb-3 h-10 w-10 text-[#2a2a3a]" />
              <p className="text-sm text-[#55556a]">
                Ask me anything about your {agentType === "dashboard" ? "portfolio" : agentType}.
              </p>
              <p className="mt-1 text-xs text-[#3a3a4a]">
                I&apos;ll use live data to help you.
              </p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={cn(
                "mb-3 flex gap-2",
                msg.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              {msg.role === "assistant" && (
                <div className="mt-1 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[#06d6a0]/15">
                  <Bot className="h-3.5 w-3.5 text-[#06d6a0]" />
                </div>
              )}
              <div
                className={cn(
                  "max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed",
                  msg.role === "user"
                    ? "bg-[#06d6a0]/15 text-[#e0e0e8]"
                    : "bg-[#1a1a24] text-[#c0c0d0]",
                )}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>
                {msg.provider && (
                  <div className="mt-1 text-[12px] text-[#55556a]">
                    via {msg.provider}/{msg.model}
                  </div>
                )}
              </div>
              {msg.role === "user" && (
                <div className="mt-1 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[#2a2a3a]">
                  <User className="h-3.5 w-3.5 text-[#8888a0]" />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="mb-3 flex gap-2">
              <div className="mt-1 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[#06d6a0]/15">
                <Bot className="h-3.5 w-3.5 text-[#06d6a0]" />
              </div>
              <div className="rounded-xl bg-[#1a1a24] px-3 py-2">
                <Loader2 className="h-4 w-4 animate-spin text-[#06d6a0]" />
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t border-[rgba(255,255,255,0.06)] p-3">
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a message..."
              rows={1}
              className="flex-1 resize-none rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#14141b] px-3 py-2 text-sm text-white placeholder-[#55556a] outline-none transition-colors focus:border-[#06d6a0]/40"
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#06d6a0] to-[#0ff0b3] text-[#0d0d12] transition-opacity disabled:opacity-40"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
