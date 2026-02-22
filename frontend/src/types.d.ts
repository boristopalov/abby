export interface ChatMessage {
  text: string;
  isUser: boolean;
  timestamp?: number;
  type?: "text" | "function_call" | "function_result" | "error";
  arguments?: Record<string, unknown>;
  tool_call_id?: string;
  result?: string;
  trackId?: number;
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

export interface Track {
  id: string;
  name: string;
  devices: Array<{
    name: string;
  }>;
}

export interface ChatSession {
  id: string;
  name: string;
  createdAt: number;
}

export interface Project {
  id: number;
  name: string;
  indexedAt: number | null;
}
