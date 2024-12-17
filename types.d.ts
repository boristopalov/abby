export interface WebSocketMessage {
  type:
    | "text"
    | "tool"
    | "end_message"
    | "confirmation"
    | "error"
    | "loading_progress"
    | "parameter_change";
  content: string | number | object;
}

// Extend the WebSocket type
interface CustomWebSocket extends WebSocket {
  sendMessage(message: WebSocketMessage): void;
}
