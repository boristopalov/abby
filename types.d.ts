export interface WebSocketMessage {
  type:
    | "text"
    | "tool"
    | "end_message"
    | "confirmation"
    | "error"
    | "loading_progress";
  content: string | number;
}

// Extend the WebSocket type
interface CustomWebSocket extends WebSocket {
  sendMessage(message: WebSocketMessage): void;
}
