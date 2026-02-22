import { writable, get } from "svelte/store";
import { activeSessionId } from "./sessionStore.ts";
import {
  globalMessages,
  addGlobalMessage,
  updateLastGlobalMessage,
  updateGlobalMessageByToolCallId,
  clearAllMessages,
} from "./chatStore.ts";
import { getSessionMessages } from "./apiCalls.ts";
import { loading, indexing, parameterChanges, tracks, projectState } from "./state.svelte.ts";
import type { ParameterChange, Track } from "../types.d.ts";

interface WebSocketState {
  ws: WebSocket | null;
  isConnected: boolean;
  isModelThinking: boolean;
}

interface WebSocketMessage {
  type:
    | "text"
    | "function_call"
    | "function_result"
    | "end_message"
    | "confirmation"
    | "error"
    | "loading_progress"
    | "indexing_status"
    | "parameter_change"
    | "tracks"
    | "track";
  content: string | number | ParameterChange | Track[] | object;
  arguments?: Record<string, unknown>;
  tool_call_id?: string;
}

const createWebSocketStore = () => {
  const { subscribe, update } = writable<WebSocketState>({
    ws: null,
    isConnected: false,
    isModelThinking: false,
  });

  let currentMessage = "";
  let isStreaming = false;

  function handleWebSocketMessage(data: WebSocketMessage) {
    console.log("Message:", data);
    update((state) => ({ ...state, isModelThinking: false }));

    switch (data.type) {
      case "tracks":
        tracks.tracks = data.content as Track[];
        break;
      case "track":
        tracks.tracks.push(data.content as Track);
        break;
      case "end_message":
        isStreaming = false;
        currentMessage = "";
        break;

      case "text": {
        currentMessage += data.content as string;
        if (!isStreaming) {
          addGlobalMessage({
            text: currentMessage,
            isUser: false,
            type: "text",
          });
          isStreaming = true;
        } else {
          updateLastGlobalMessage((msg) => ({
            ...msg,
            text: currentMessage,
          }));
        }
        break;
      }
      case "loading_progress":
        // no-op: superseded by indexing_status
        break;
      case "indexing_status": {
        const status = data.content as { isIndexing: boolean; progress?: number };
        indexing.isIndexing = status.isIndexing;
        if (status.progress !== undefined) indexing.progress = status.progress;
        break;
      }
      case "parameter_change":
        parameterChanges.changes.push(data.content as ParameterChange);
        break;
      case "function_call":
        update((state) => ({ ...state, isModelThinking: true }));
        addGlobalMessage({
          text: data.content as string,
          isUser: false,
          type: "function_call",
          arguments: data.arguments,
          tool_call_id: data.tool_call_id,
        });
        break;

      case "function_result":
        if (data.tool_call_id) {
          updateGlobalMessageByToolCallId(data.tool_call_id, (msg) => ({
            ...msg,
            result: data.content as string,
          }));
        }
        break;

      case "error":
        addGlobalMessage({
          text: data.content as string,
          isUser: false,
          type: "error",
        });
        break;
    }
  }

  const store = {
    subscribe,
    connect: () => {
      const sessionId = get(activeSessionId);
      const projectId = projectState.activeProjectId;

      if (!projectId) {
        console.warn("No project selected, cannot connect WebSocket");
        return;
      }

      const ws = new WebSocket(
        `ws://localhost:8000/ws?sessionId=${sessionId}&projectId=${projectId}`
      );

      ws.onopen = async () => {
        try {
          const msgs = await getSessionMessages(sessionId);
          globalMessages.set(msgs);
        } catch (e) {
          console.error("Error fetching session messages:", e);
        }
        update((state) => ({ ...state, isConnected: true, ws }));
      };

      ws.onclose = () => {
        update((state) => ({ ...state, isConnected: false, ws: null }));
        // Only auto-reconnect if we have a project selected
        if (projectState.activeProjectId) {
          setTimeout(() => store.connect(), 1000);
        }
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      };
    },

    disconnect: () => {
      update((state) => {
        if (state.ws) {
          state.ws.close();
        }
        return { ...state, isConnected: false, ws: null };
      });
    },

    sendMessage: (message: string) => {
      const state = get(wsStore);
      if (state.ws && state.isConnected) {
        update((state) => ({ ...state, isModelThinking: true }));
        state.ws.send(JSON.stringify({ message }));
      }
    },
  };

  return store;
};

export const wsStore = createWebSocketStore();
