export interface ApprovalRequest {
  tool_call_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
}

export interface ChatMessage {
  text: string;
  isUser: boolean;
  timestamp?: number;
  type?: "text" | "function_call" | "function_result" | "error" | "approval_required";
  arguments?: Record<string, unknown>;
  tool_call_id?: string;
  result?: string;
  trackId?: number;
  // approval_required fields
  requests?: ApprovalRequest[];
  approvalState?: "pending" | "approved" | "denied";
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
