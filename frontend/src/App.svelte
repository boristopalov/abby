<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { sessionStorage, activeSessionId } from "./lib/stores";
  import {
    fetchGenres,
    getRecentParameterChanges,
    setGenre,
    generateRandomGenre,
    getSessionMessages,
  } from "./lib/apiCalls";
  import { slide } from "svelte/transition";
  import { writable } from "svelte/store";
  import type { ChatMessage, ParameterChange } from "./types";

  interface WebSocketMessage {
    type:
      | "text"
      | "tool"
      | "end_message"
      | "confirmation"
      | "error"
      | "loading_progress"
      | "parameter_change";
    content: string | number | ParameterChange;
  }

  let inputMessage = $state("");
  let ws: WebSocket;
  let currentMessage = $state("");
  let isConnected = $state(false);
  let availableGenres: string[] = $state([]);
  let activeGenre: string | null = $state(null);
  let loadingProgress: number = $state(0);
  let isLoading: boolean = $derived(loadingProgress !== 100);

  let showParameterPanel = $state(true);

  let chatContainer = $state<HTMLElement | undefined>(undefined);
  let isModelThinking = $state(false);

  const parameterChanges = writable<ParameterChange[]>([]);
  const messages = writable<ChatMessage[]>([]);
  onMount(async () => {
    void connectWebSocket();

    // Poll every minute
    const intervalId = setInterval(async () => {
      const changes = await getRecentParameterChanges();
      if (changes) {
        parameterChanges.set(changes);
      }
    }, 60000);

    const genreResponse = await fetchGenres();
    availableGenres = genreResponse.genres;
    activeGenre = genreResponse.defaultGenre;

    onDestroy(() => {
      clearInterval(intervalId);
      if (ws) {
        ws.close();
      }
    });
  });

  async function connectWebSocket() {
    ws = new WebSocket(`ws://localhost:8000/ws?sessionId=${$activeSessionId}`);

    ws.onopen = async () => {
      const msgs = await getSessionMessages($activeSessionId);
      messages.set(msgs);
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

    setTimeout(() => {
      chatContainer?.scrollTo({
        top: chatContainer.scrollHeight,
        behavior: "smooth",
      });
    }, 50);
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

      setTimeout(() => {
        chatContainer?.scrollTo({
          top: chatContainer.scrollHeight,
          behavior: "smooth",
        });
      }, 50);
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
          setTimeout(() => {
            chatContainer?.scrollTo({
              top: chatContainer.scrollHeight,
              behavior: "smooth",
            });
          }, 50);
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
        showParameterPanel = true;
        break;

      case "tool":
        isModelThinking = true;
        messages.update((msgs) => [
          ...msgs,
          {
            text: formatMessage(data.content as string),
            isUser: false,
            type: "tool",
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
        class="px-3 py-1 rounded-full text-sm bg-blue-500/20 text-blue-400 hover:bg-blue-500/30"
      >
        Start New Chat
      </button>
      <div
        class={`px-3 py-1 rounded-full text-sm disabled:cursor-not-allowed ${
          isConnected
            ? "bg-green-500/10 text-green-400"
            : "bg-red-500/10 text-red-400"
        }`}
      >
        {isConnected ? "Connected" : "Disconnected"}
      </div>
    </div>
  </div>
  {#if isLoading}
    <div class="flex flex-col items-center justify-center h-full p-8">
      <div
        class="w-full max-w-md bg-gray-700 rounded-full h-4 mb-4 overflow-hidden relative"
      >
        <!-- Loading bar with shimmer effect -->
        <div
          class="bg-green-500 h-4 rounded-full transition-all duration-300 ease-in-out relative"
          style="width: {loadingProgress}%"
        >
          <!-- Shimmer animation -->
          <div class="absolute inset-0 animate-shimmer">
            <div
              class="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full"
            ></div>
          </div>
        </div>
      </div>
      <p class="text-white text-lg animate-pulse">
        Indexing Your Ableton Project... {loadingProgress}%
      </p>
    </div>
  {:else}
    <div class="flex flex-1 min-h-0 relative">
      <div class="flex-1 flex flex-col">
        <div
          class="border-b border-gray-800 p-3 flex gap-4 w-full items-center"
        >
          <div class="flex flex-wrap gap-2 flex-1 justify-center">
            {#each availableGenres as genre}
              <button
                onclick={() => {
                  setGenre(genre);
                  activeGenre = genre;
                }}
                class={`px-3 py-1 rounded-full text-xs disabled:cursor-not-allowed transition-colors cursor-pointer ${
                  activeGenre === genre
                    ? "bg-purple-700/80 text-purple-200"
                    : "bg-purple-500/20 text-purple-300 hover:bg-purple-500/30"
                }`}
                disabled={!isConnected}
              >
                {genre}
              </button>
            {/each}
          </div>

          <div class="border-l border-gray-800 pl-4">
            <button
              onclick={async () => {
                try {
                  const newGenre = await generateRandomGenre();
                  setGenre(newGenre);
                  activeGenre = newGenre;
                  availableGenres = [...availableGenres, newGenre];
                } catch (error) {
                  console.error("Error generating random genre:", error);
                }
              }}
              class="px-2 py-1.5 rounded-sm text-xs font-medium disabled:cursor-not-allowed transition-all duration-300 cursor-pointer bg-gradient-to-r from-indigo-500/20 via-purple-500/20 to-pink-500/20 hover:from-indigo-500/30 hover:via-purple-500/30 hover:to-pink-500/30 text-white border border-white/10 hover:border-white/20 hover:shadow-lg hover:shadow-purple-500/10 hover:-translate-y-0.5 active:translate-y-0"
              disabled={!isConnected}
            >
              <span
                class="bg-gradient-to-r from-indigo-200 via-purple-200 to-pink-200 bg-clip-text"
              >
                🎲 🎲
              </span>
            </button>
          </div>
        </div>

        <div
          class="flex-1 flex flex-col min-h-0 max-w-4xl mx-auto w-full p-4 text-sm"
        >
          <div
            bind:this={chatContainer}
            class="flex-1 overflow-y-auto space-y-4 mb-4"
          >
            {#each $messages as message}
              <div
                class={`flex ${message.isUser ? "justify-end" : "justify-start"}`}
              >
                <div
                  class={`max-w-[80%] rounded-lg p-3 ${
                    message.isUser
                      ? "bg-blue-500 text-white"
                      : message.type === "error"
                        ? "bg-red-500/20 text-red-200"
                        : message.type === "tool"
                          ? "bg-purple-500/20 text-purple-200"
                          : "bg-gray-800 text-gray-100"
                  }`}
                >
                  <div class="flex items-start gap-2">
                    {#if message.type === "tool"}
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        class="h-5 w-5 mt-0.5"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                      >
                        <path
                          fill-rule="evenodd"
                          d="M6 2a2 2 0 00-2 2v12a2 2 0 002 2h8a2 2 0 002-2V4a2 2 0 00-2-2H6zm1 2a1 1 0 000 2h6a1 1 0 100-2H7zm6 7a1 1 0 011 1v3a1 1 0 11-2 0v-3a1 1 0 011-1zm-3 3a1 1 0 100 2h.01a1 1 0 100-2H10z"
                          clip-rule="evenodd"
                        />
                      </svg>
                    {:else if message.type === "error"}
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        class="h-5 w-5 mt-0.5"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                      >
                        <path
                          fill-rule="evenodd"
                          d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                          clip-rule="evenodd"
                        />
                      </svg>
                    {/if}
                    <div
                      class="whitespace-pre-wrap break-words leading-relaxed"
                    >
                      {@html message.text}
                    </div>
                  </div>
                </div>
              </div>
            {/each}
            {#if currentMessage}
              <div class="flex justify-start">
                <div
                  class="max-w-[80%] rounded-lg p-3 bg-gray-800 text-gray-100"
                >
                  <div class="whitespace-pre-wrap break-words leading-relaxed">
                    {@html formatMessage(currentMessage)}
                  </div>
                </div>
              </div>
            {/if}
            {#if isModelThinking}
              <div class="flex justify-start">
                <div
                  class="max-w-[80%] rounded-lg p-3 bg-gray-800 text-gray-100"
                >
                  <div class="flex items-center gap-2">
                    <div
                      class="w-2 h-2 bg-blue-500 rounded-full animate-bounce"
                      style="animation-delay: 0ms"
                    ></div>
                    <div
                      class="w-2 h-2 bg-blue-500 rounded-full animate-bounce"
                      style="animation-delay: 150ms"
                    ></div>
                    <div
                      class="w-2 h-2 bg-blue-500 rounded-full animate-bounce"
                      style="animation-delay: 300ms"
                    ></div>
                  </div>
                </div>
              </div>
            {/if}
          </div>

          <div class="border-t border-gray-800 pt-4">
            <!-- <button
              onclick={requestParameterChanges}
              disabled={!isConnected}
              class="w-full mb-4 bg-gradient-to-r from-purple-600/20 via-blue-600/20 to-purple-600/20 hover:from-purple-600/30 hover:via-blue-600/30 hover:to-purple-600/30 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg p-3 flex items-center justify-center gap-2 transition-all duration-300 group relative overflow-hidden before:absolute before:inset-0 before:bg-gradient-to-r before:from-transparent before:via-white/5 before:to-transparent before:-translate-x-full hover:before:translate-x-full before:transition-transform before:duration-700 before:ease-in-out active:scale-[0.98] disabled:before:hidden"
            >
              <span class="font-semibold"
                >✨ 🤗 Suggest Parameter Changes 🤗 ✨</span
              >
            </button> -->

            <div class="relative gap-2">
              <textarea
                bind:value={inputMessage}
                onkeypress={handleKeyPress}
                placeholder="Type a message..."
                rows="3"
                disabled={!isConnected}
                class="w-full bg-gray-800 rounded-lg p-3 pr-12 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              ></textarea>
              <button
                aria-label="Send message"
                onclick={sendMessage}
                disabled={!isConnected || !inputMessage.trim()}
                class="absolute bottom-3 right-3 bg-blue-500/30 hover:bg-blue-500/50 disabled:opacity-50 disabled:cursor-not-allowed p-2 rounded-lg flex items-center justify-center transition-colors"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  class="w-5 h-5"
                >
                  <path
                    d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Parameter changes side panel -->
      {#if showParameterPanel}
        <div
          class="w-80 border-l border-gray-800 bg-gray-900 flex flex-col overflow-hidden shrink-0"
          in:slide={{ axis: "x" }}
          out:slide={{ axis: "x" }}
        >
          <div
            class="p-3 border-b border-gray-800 flex justify-between items-center"
          >
            <h2 class="font-semibold">Parameter Changes</h2>
          </div>
          <div class="flex-1 overflow-y-auto p-4 space-y-2">
            {#each $parameterChanges as change}
              <div
                class="border-l-2 border-purple-500/30 pl-3 mb-3 hover:border-purple-500/50 transition-colors"
              >
                <div class="text-xs text-gray-400 mb-1">
                  {change.trackName} / {change.deviceName}
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-sm text-gray-300">{change.paramName}</span>
                  <span
                    class="text-xs font-mono bg-blue-500/10 text-blue-300 px-2 py-0.5 rounded"
                  >
                    {change.oldValue.toFixed(2)} --> {change.newValue.toFixed(
                      2
                    )}
                  </span>
                </div>
                <div class="text-xs text-gray-500 mt-1">
                  {new Date(change.timestamp).toLocaleTimeString()}
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <button
        onclick={() => (showParameterPanel = !showParameterPanel)}
        class="fixed right-0 top-1/2 -translate-y-1/2 bg-gray-800 p-2 rounded-l-lg text-gray-400 hover:text-gray-200 hover:bg-gray-700"
        aria-label={showParameterPanel
          ? "hide parameter changes"
          : "show parameter changes"}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          class="h-5 w-5"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fill-rule="evenodd"
            d={showParameterPanel
              ? "M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
              : "M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"}
            clip-rule="evenodd"
          />
        </svg>
      </button>
    </div>
  {/if}
</main>

<style>
  :global(body) {
    margin: 0;
  }

  @keyframes shimmer {
    0% {
      transform: translateX(-100%);
    }
    100% {
      transform: translateX(100%);
    }
  }

  .animate-shimmer {
    animation: shimmer 2s infinite;
  }
</style>
