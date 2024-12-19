export interface ChatMessage {
  text: string;
  isUser: boolean;
  timestamp?: number;
  type?: "text" | "tool" | "error";
}

export interface ParameterChange {
  trackId: number;
  trackName: string;
  deviceId: number;
  deviceName: string;
  paramId: number;
  paramName: string;
  oldValue: number;
  newValue: number;
  min: number;
  max: number;
  timestamp: number;
}
