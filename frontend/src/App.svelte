<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { messageStorage, type ChatMessage } from "./lib/messageStorage.ts";
  import "./app.css";

  let messages: ChatMessage[] = [];
  let inputMessage = "";
  let ws: WebSocket;
  let currentMessage = "";
  let isConnected = false;

  onMount(() => {
    messages = messageStorage.getMessages();
    connectWebSocket();
  });

  onDestroy(() => {
    if (ws) {
      ws.close();
    }
  });

  function connectWebSocket() {
    ws = new WebSocket("ws://localhost:8000");

    ws.onopen = () => {
      isConnected = true;
      console.log("Connected to WebSocket server");
    };

    ws.onclose = () => {
      isConnected = false;
      console.log("Disconnected from WebSocket server");
      // Try to reconnect after 2 seconds
      setTimeout(connectWebSocket, 2000);
    };

    ws.onmessage = (event) => {
      if (event.data === "<|END_MESSAGE|>") {
        if (currentMessage) {
          messages = messageStorage.addMessage({
            text: currentMessage,
            isUser: false,
          });
          currentMessage = "";
        }
      } else {
        try {
          const data = JSON.parse(event.data);
          if (typeof data === "string") {
            currentMessage += data;
          }
        } catch (e) {
          console.error("Error parsing message:", e);
        }
      }
    };
  }

  function sendMessage() {
    if (!inputMessage.trim() || !ws) return;

    messages = messageStorage.addMessage({
      text: inputMessage,
      isUser: true,
    });

    ws.send(inputMessage);
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
      ws.send("get-param-changes");
    }
  }

  function clearHistory() {
    messageStorage.clearMessages();
    messages = [];
  }
</script>

<main class="h-screen flex flex-col bg-gray-900 text-gray-100">
  <div class="border-b border-gray-800 p-4 flex justify-between items-center">
    <h1 class="text-xl font-semibold">Abby</h1>
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

  <div class="flex-1 flex flex-col h-full max-w-4xl mx-auto w-full p-4 text-sm">
    <div class="flex-1 overflow-y-auto space-y-4 mb-4">
      {#each messages as message}
        <div class={`flex ${message.isUser ? "justify-end" : "justify-start"}`}>
          <div
            class={`max-w-[80%] rounded-lg p-3 ${
              message.isUser
                ? "bg-blue-500 text-white"
                : "bg-gray-800 text-gray-100"
            }`}
          >
            {message.text}
          </div>
        </div>
      {/each}
      {#if currentMessage}
        <div class="flex justify-start">
          <div class="max-w-[80%] rounded-lg p-3 bg-gray-800 text-gray-100">
            {currentMessage}
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
        <span class="font-semibold">✨ 🤗 Suggest Parameter Changes 🤗 ✨</span>
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
          class="absolute bottom-3 right-3 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed p-2 rounded-lg flex items-center justify-center transition-colors"
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
</main>

<style>
  /* Remove existing styles as we're using Tailwind */
  :global(body) {
    margin: 0;
  }
</style>
