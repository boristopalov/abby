<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { sessionStorage, activeSessionId } from "./lib/stores";
  import {
    fetchGenres,
    getRecentParameterChanges,
    getSessionMessages,
  } from "./lib/apiCalls";
  import { writable } from "svelte/store";
  import type { ChatMessage, ParameterChange, Track } from "./types";
  import ConnectionStatus from "./components/ConnectionStatus.svelte";
  import LoadingProgress from "./components/LoadingProgress.svelte";
  import GenreSelector from "./components/GenreSelector.svelte";
  import ParameterPanel from "./components/ParameterPanel.svelte";
  import TrackList from "./components/TrackList.svelte";

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

  let inputMessage = $state("");
  let ws: WebSocket;
  let currentMessage = $state("");
  let isConnected = $state(false);
  let availableGenres: string[] = $state([]);
  let activeGenre: string | null = $state(null);
  let loadingProgress: number = $state(0);
  let isLoading: boolean = $derived(loadingProgress !== 100);
  let tracks: Track[] = $state([]);

  let showParameterPanel = $state(true);
  let isModelThinking = $state(false);
  let intervalId: number = $state(0);

  const parameterChanges = writable<ParameterChange[]>([]);
  const messages = writable<ChatMessage[]>([]);

  onMount(async () => {
    void connectWebSocket();

    // Poll every minute
    intervalId = setInterval(async () => {
      const changes = await getRecentParameterChanges();
      if (changes) {
        parameterChanges.set(changes);
      }
    }, 60000);

    const genreResponse = await fetchGenres();
    availableGenres = genreResponse.genres;
    activeGenre = genreResponse.defaultGenre;
  });
  onDestroy(() => {
    clearInterval(intervalId);
    if (ws) {
      ws.close();
    }
  });

  async function connectWebSocket() {
    ws = new WebSocket(`ws://localhost:8000/ws?sessionId=${$activeSessionId}`);

    ws.onopen = async () => {
      try {
        const msgs = await getSessionMessages($activeSessionId);
        messages.set(msgs);
      } catch (e) {
        console.error("Error fetching session messages:", e);
      }
      isConnected = true;
      console.log(
        "Connected to WebSocket server with session:",
        $activeSessionId
      );
    };

    ws.onclose = () => {
      isConnected = false;
      console.log("Disconnected from WebSocket server");
      setTimeout(connectWebSocket, 1000);
    };

    ws.onmessage = (event) => {
      const data: WebSocketMessage = JSON.parse(event.data);
      console.log("DATA:", data);
      handleWebSocketMessage(data);
    };
  }

  async function resetProject() {
    if (ws) {
      ws.onclose = null;
      ws.close();
      isConnected = false;
    }
    // Reset UI state
    messages.set([]);
    currentMessage = "";
    parameterChanges.set([]);
    loadingProgress = 0;
    isModelThinking = false;

    // Create new WebSocket connection with resetProject flag
    ws = new WebSocket(
      `ws://localhost:8000/ws?sessionId=${$activeSessionId}&resetProject=true`
    );

    ws.onopen = async () => {
      isConnected = true;
      console.log("Connected to WebSocket server with reset flag");
    };

    ws.onclose = () => {
      isConnected = false;
      console.log("Disconnected from WebSocket server");
      setTimeout(connectWebSocket, 1000);
    };

    ws.onmessage = (event) => {
      const data: WebSocketMessage = JSON.parse(event.data);
      console.log("DATA:", data);
      handleWebSocketMessage(data);
    };
  }

  function sendMessage() {
    if (!inputMessage.trim() || !ws) return;

    isModelThinking = true;
    messages.update((msgs) => [
      ...msgs,
      {
        text: inputMessage,
        isUser: true,
        type: "text",
      },
    ]);

    ws.send(
      JSON.stringify({
        message: inputMessage,
      })
    );
    inputMessage = "";
  }

  function handleKeyPress(event: KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  function requestParameterChanges() {
    if (ws) {
      isModelThinking = true;
      ws.send(
        JSON.stringify({
          message: "get-param-changes",
        })
      );
    }
  }

  function startNewSession() {
    sessionStorage.createSession();
    if (ws) {
      ws.close(4000, "reset"); // This will trigger reconnection with new sessionId
    }
  }

  // Add these helper functions at the top of your script section
  function formatMessage(text: string): string {
    return (
      text
        .trim()
        // Replace newlines with <br> tags
        .replace(/\n/g, "<br>")
        // Preserve consecutive spaces
        .replace(/ {2,}/g, (match) => "&nbsp;".repeat(match.length))
        // Preserve tabs
        .replace(/\t/g, "&nbsp;&nbsp;&nbsp;&nbsp;")
    );
  }

  function handleWebSocketMessage(data: WebSocketMessage) {
    isModelThinking = false;
    console.log(isModelThinking);
    switch (data.type) {
      case "tracks":
        tracks = data.content as Track[];
        break;
      case "track":
        tracks.push(data.content as Track);

      case "end_message":
        if (currentMessage) {
          messages.update((msgs) => [
            ...msgs,
            {
              text: formatMessage(currentMessage),
              isUser: false,
              type: "text",
            },
          ]);
          currentMessage = "";
        }
        break;

      case "text":
        currentMessage += data.content;
        break;

      case "loading_progress":
        loadingProgress = data.content as number;
        break;

      case "parameter_change":
        parameterChanges.update((changes) => [
          ...changes,
          data.content as ParameterChange,
        ]);
        break;

      case "function_call":
        isModelThinking = true;
        messages.update((msgs) => [
          ...msgs,
          {
            text: formatMessage(data.content as string),
            isUser: false,
            type: "function_call",
          },
        ]);
        break;

      case "error":
        messages.update((msgs) => [
          ...msgs,
          {
            text: formatMessage(data.content as string),
            isUser: false,
            type: "error",
          },
        ]);
        break;

      case "confirmation":
        // Handle confirmation messages if needed
        break;
    }
  }
</script>

<main class="h-screen flex flex-col bg-gray-900 text-gray-100">
  <div class="border-b border-gray-800 p-3 flex justify-between items-center">
    <h1 class="text-xl font-semibold">Abby</h1>
    <div class="flex items-center gap-4">
      <button
        onclick={startNewSession}
        hidden={!isConnected}
        disabled={isLoading || !isConnected}
        class="px-3 py-1 rounded-lg text-sm bg-blue-500/20 text-blue-300 hover:bg-blue-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        Start New Chat
      </button>
      <button
        onclick={resetProject}
        hidden={!isConnected}
        disabled={isLoading || !isConnected}
        class="px-3 py-1 rounded-lg text-sm bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        Reset Project
      </button>
      <ConnectionStatus {isConnected} />
    </div>
  </div>
  {#if isLoading}
    <LoadingProgress {loadingProgress} />
  {:else}
    <div class="flex flex-1 min-h-0 relative">
      <div class="flex-1 flex flex-col">
        <GenreSelector {availableGenres} {activeGenre} {isConnected} />
        <TrackList {tracks} />
      </div>

      <ParameterPanel
        parameterChanges={$parameterChanges}
        {showParameterPanel}
        onToggle={() => (showParameterPanel = !showParameterPanel)}
      />
    </div>
  {/if}
</main>

<style>
  :global(body) {
    margin: 0;
  }
</style>
