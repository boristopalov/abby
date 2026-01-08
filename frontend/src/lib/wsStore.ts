import { writable, get } from "svelte/store";
import { activeSessionId } from "./sessionStore.ts";
import {
  globalMessages,
  addGlobalMessage,
  clearAllMessages,
} from "./chatStore.ts";
import { getSessionMessages } from "./apiCalls.ts";
import { loading, parameterChanges, tracks, projectState } from "./state.svelte.ts";
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
    | "end_message"
    | "confirmation"
    | "error"
    | "loading_progress"
    | "parameter_change"
    | "tracks"
    | "track";
  content: string | number | ParameterChange | Track[] | object;
}

const createWebSocketStore = () => {
  const { subscribe, update } = writable<WebSocketState>({
    ws: null,
    isConnected: false,
    isModelThinking: false,
  });

  let currentMessage = "";

  function formatMessage(text: string): string {
    return text
      .trim()
      .replace(/\n/g, "<br>")
      .replace(/ {2,}/g, (match) => "&nbsp;".repeat(match.length))
      .replace(/\t/g, "&nbsp;&nbsp;&nbsp;&nbsp;");
  }

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
        if (currentMessage) {
          addGlobalMessage({
            text: formatMessage(currentMessage),
            isUser: false,
            type: "text",
          });
          currentMessage = "";
        }
        break;

      case "text":
        currentMessage += data.content;
        break;
      case "loading_progress":
        loading.progress = data.content as number;
        break;
      case "parameter_change":
        parameterChanges.changes.push(data.content as ParameterChange);
        break;
      case "function_call":
        update((state) => ({ ...state, isModelThinking: true }));
        addGlobalMessage({
          text: formatMessage(data.content as string),
          isUser: false,
          type: "function_call",
        });
        break;

      case "error":
        addGlobalMessage({
          text: formatMessage(data.content as string),
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
