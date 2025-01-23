export interface ChatMessage {
  text: string;
  isUser: boolean;
  timestamp?: number;
  type?: "text" | "function_call" | "error";
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
