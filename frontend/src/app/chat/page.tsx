import { Suspense } from "react";

import { ChatScreen } from "@/features/chat/ChatScreen";

export default function ChatPage() {
  return (
    <Suspense fallback={null}>
      <ChatScreen />
    </Suspense>
  );
}
