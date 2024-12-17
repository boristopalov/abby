<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { messageStorage, activeSession } from "./lib/messageStorage";
  import "./app.css";
  import { fetchGenres, setGenre } from "./lib/apiCalls";
  interface WebSocketMessage {
    type:
      | "text"
      | "tool"
      | "end_message"
      | "confirmation"
      | "error"
      | "loading_progress";
    content: string | number;
  }

  let inputMessage = "";
  let ws: WebSocket;
  let currentMessage = "";
  let isConnected = false;
  let availableGenres: string[] = [];
  let activeGenre: string | null = null;
  let loadingProgress: number = 0;
  let isLoading: boolean = true;

  onMount(async () => {
    connectWebSocket();
    const genreResponse = await fetchGenres();
    availableGenres = genreResponse.genres;
    activeGenre = genreResponse.defaultGenre;
  });

  onDestroy(() => {
    if (ws) {
      ws.close();
    }
  });

  function connectWebSocket() {
    ws = new WebSocket(`ws://localhost:8000?sessionId=${$activeSession.id}`);

    ws.onopen = () => {
      isConnected = true;
      console.log(
        "Connected to WebSocket server with session:",
        $activeSession.id
      );
    };

    ws.onclose = () => {
      isConnected = false;
      console.log("Disconnected from WebSocket server");
      setTimeout(connectWebSocket, 100);
    };

    ws.onmessage = (event) => {
      const data: WebSocketMessage = JSON.parse(event.data);
      handleWebSocketMessage(data);
    };
  }

  function sendMessage() {
    if (!inputMessage.trim() || !ws) return;

    messageStorage.addMessage({
      text: inputMessage,
      isUser: true,
      type: "text",
    });

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
      ws.send(
        JSON.stringify({
          message: "get-param-changes",
        })
      );
    }
  }

  function startNewSession() {
    messageStorage.deleteActiveSession();
    if (ws) {
      ws.close(); // This will trigger reconnection with new sessionId
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
    switch (data.type) {
      case "end_message":
        if (currentMessage) {
          messageStorage.addMessage({
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
        loadingProgress = data.content as number;
        if (loadingProgress === 100) {
          isLoading = false;
        }
        break;

      case "tool":
        messageStorage.addMessage({
          text: formatMessage(data.content as string),
          isUser: false,
          type: "tool",
        });
        break;

      case "error":
        messageStorage.addMessage({
          text: formatMessage(data.content as string),
          isUser: false,
          type: "error",
        });
        break;

      case "confirmation":
        // Handle confirmation messages if needed
        break;
    }
  }
</script>

<main class="h-screen flex flex-col bg-gray-900 text-gray-100">
  <div class="border-b border-gray-800 p-4 flex justify-between items-center">
    <h1 class="text-xl font-semibold">Abby</h1>
    <div class="flex items-center gap-4">
      <button
        on:click={startNewSession}
        disabled={isLoading}
        class="px-3 py-1 rounded-full text-sm bg-blue-500/20 text-blue-400 hover:bg-blue-500/30"
      >
        Start New Chat
      </button>
      <div
        class={`px-3 py-1 rounded-full text-sm ${
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
    <div
      class="border-b border-gray-800 p-4 flex flex-wrap gap-2 w-full justify-center"
    >
      {#each availableGenres as genre}
        <button
          on:click={() => {
            setGenre(genre);
            activeGenre = genre;
          }}
          class={`px-3 py-1 rounded-full text-sm transition-colors cursor-pointer ${
            activeGenre === genre
              ? "bg-purple-700/80 text-purple-200"
              : "bg-purple-500/20 text-purple-300 hover:bg-purple-500/30"
          }`}
        >
          {genre}
        </button>
      {/each}
    </div>

    <!-- <div class="flex-1 flex flex-col h-full max-w-4xl mx-auto w-full p-4 text-sm"> -->
    <div
      class="flex-1 flex flex-col min-h-0 max-w-4xl mx-auto w-full p-4 text-sm"
    >
      <div class="flex-1 overflow-y-auto space-y-4 mb-4">
        {#each $activeSession.messages as message}
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
                <div class="whitespace-pre-wrap break-words leading-relaxed">
                  {@html message.text}
                </div>
              </div>
            </div>
          </div>
        {/each}
        {#if currentMessage}
          <div class="flex justify-start">
            <div class="max-w-[80%] rounded-lg p-3 bg-gray-800 text-gray-100">
              <div class="whitespace-pre-wrap break-words leading-relaxed">
                {@html formatMessage(currentMessage)}
              </div>
            </div>
          </div>
        {/if}
      </div>

      <div class="border-t border-gray-800 pt-4">
        <button
          on:click={requestParameterChanges}
          disabled={!isConnected}
          class="w-full mb-4 bg-gradient-to-r from-purple-600/20 via-blue-600/20 to-purple-600/20 hover:from-purple-600/30 hover:via-blue-600/30 hover:to-purple-600/30 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg p-3 flex items-center justify-center gap-2 transition-all duration-300 group relative overflow-hidden before:absolute before:inset-0 before:bg-gradient-to-r before:from-transparent before:via-white/5 before:to-transparent before:-translate-x-full hover:before:translate-x-full before:transition-transform before:duration-700 before:ease-in-out active:scale-[0.98] disabled:before:hidden"
        >
          <span class="font-semibold"
            >✨ 🤗 Suggest Parameter Changes 🤗 ✨</span
          >
        </button>

        <div class="relative gap-2">
          <textarea
            bind:value={inputMessage}
            on:keypress={handleKeyPress}
            placeholder="Type a message..."
            rows="3"
            disabled={!isConnected}
            class="w-full bg-gray-800 rounded-lg p-3 pr-12 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          ></textarea>
          <button
            aria-label="Send message"
            on:click={sendMessage}
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
  {/if}
</main>

<style>
  /* Remove existing styles as we're using Tailwind */
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
