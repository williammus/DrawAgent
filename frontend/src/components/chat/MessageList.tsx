import { useEffect, useRef } from "react";

import type { UIMessage } from "../../types/ui";
import { EmptyState } from "../common/EmptyState";
import { MessageBubble } from "./MessageBubble";

export function MessageList({ messages }: { messages: UIMessage[] }) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <EmptyState>
        这里会显示对话过程、阶段状态、澄清问题、最终 Prompt 和图片结果。
      </EmptyState>
    );
  }

  return (
    <div className="space-y-4">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
