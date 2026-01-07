<script lang="ts">
  import { slide } from "svelte/transition";
  import { onMount } from "svelte";
  import type { ChatSession } from "../types";
  import { getSessions } from "../lib/apiCalls";
  import { activeSessionId } from "../lib/sessionStore";

  let {
    showSessionPanel,
    onToggle,
    onSessionSelect,
    onNewChat,
  } = $props<{
    showSessionPanel: boolean;
    onToggle: () => void;
    onSessionSelect: (sessionId: string) => void;
    onNewChat: () => void;
  }>();

  let sessions = $state<ChatSession[]>([]);
  let isLoading = $state(true);
  let error = $state<string | null>(null);

  async function loadSessions() {
    try {
      isLoading = true;
      error = null;
      sessions = await getSessions();
    } catch (e) {
      error = "Failed to load sessions";
      console.error("Error loading sessions:", e);
    } finally {
      isLoading = false;
    }
  }

  onMount(() => {
    loadSessions();
  });

  $effect(() => {
    if (showSessionPanel) {
      loadSessions();
    }
  });

  function formatDate(timestamp: number): string {
    return new Date(timestamp).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function handleSessionClick(sessionId: string) {
    onSessionSelect(sessionId);
  }
</script>

{#if showSessionPanel}
  <div
    class="w-72 border-r border-gray-800 bg-gray-900 flex flex-col overflow-hidden shrink-0"
    in:slide={{ axis: "x" }}
    out:slide={{ axis: "x" }}
  >
    <div class="p-3 border-b border-gray-800 flex justify-between items-center">
      <h2 class="font-semibold">Chat Sessions</h2>
      <button
        onclick={onNewChat}
        class="px-3 py-1 rounded-lg text-sm bg-blue-500/20 text-blue-300 hover:bg-blue-500/30 transition-colors"
      >
        New Chat
      </button>
    </div>

    <div class="flex-1 overflow-y-auto p-2 space-y-1">
      {#if isLoading}
        <div class="text-center text-gray-400 py-4">Loading...</div>
      {:else if error}
        <div class="text-center text-red-400 py-4">{error}</div>
      {:else if sessions.length === 0}
        <div class="text-center text-gray-400 py-4">No sessions yet</div>
      {:else}
        {#each sessions as session (session.id)}
          <button
            onclick={() => handleSessionClick(session.id)}
            class="w-full text-left p-3 rounded-lg transition-colors
              {$activeSessionId === session.id
              ? 'bg-blue-500/20 border-l-2 border-blue-500'
              : 'hover:bg-gray-800'}"
          >
            <div class="text-sm text-gray-200 truncate">{session.name}</div>
            <div class="text-xs text-gray-500 mt-1">
              {formatDate(session.createdAt)}
            </div>
          </button>
        {/each}
      {/if}
    </div>
  </div>
{/if}

<button
  onclick={onToggle}
  class="fixed left-0 top-1/2 -translate-y-1/2 bg-gray-800 p-2 rounded-r-lg text-gray-400 hover:text-gray-200 hover:bg-gray-700 z-10"
  aria-label={showSessionPanel ? "Hide chat sessions" : "Show chat sessions"}
>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    class="h-5 w-5"
    viewBox="0 0 20 20"
    fill="currentColor"
  >
    <path
      fill-rule="evenodd"
      d={showSessionPanel
        ? "M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"
        : "M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"}
      clip-rule="evenodd"
    />
  </svg>
</button>

<style>
  div::-webkit-scrollbar {
    width: 6px;
  }
  div::-webkit-scrollbar-track {
    background: transparent;
  }
  div::-webkit-scrollbar-thumb {
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 3px;
  }
</style>
