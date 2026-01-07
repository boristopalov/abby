<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { sessionStorage, activeSessionId } from "./lib/sessionStore";
  import { getRecentParameterChanges, getSessionMessages } from "./lib/apiCalls";
  import SessionList from "./components/SessionList.svelte";
  import ConnectionStatus from "./components/ConnectionStatus.svelte";
  import LoadingProgress from "./components/LoadingProgress.svelte";
  import GenreSelector from "./components/GenreSelector.svelte";
  import ParameterPanel from "./components/ParameterPanel.svelte";
  import TrackList from "./components/TrackList.svelte";
  import Chat from "./components/Chat.svelte";
  import { globalMessages, addGlobalMessage, clearAllMessages } from "./lib/chatStore";
  import { wsStore } from "./lib/wsStore";
  import {
    loading,
    tracks,
    parameterChanges,
    genres,
  } from "./lib/state.svelte";
  import type { ChatMessage } from "./types";

  let showParameterPanel = $state(true);
  let showSessionPanel = $state(false);
  let intervalId: number = $state(0);
  let isLoading: boolean = $derived(loading.progress !== 100);

  onMount(async () => {
    wsStore.connect();

    // Poll every minute
    intervalId = setInterval(async () => {
      const changes = await getRecentParameterChanges();
      if (changes) {
        parameterChanges.changes = changes;
      }
    }, 60000);
  });

  onDestroy(() => {
    clearInterval(intervalId);
    wsStore.disconnect();
  });

  function startNewSession() {
    sessionStorage.createSession();
    wsStore.disconnect(); // This will trigger reconnection with new sessionId
  }

  function resetProject() {
    wsStore.reset();
  }

  async function handleSessionSelect(sessionId: string) {
    activeSessionId.set(sessionId);
    sessionStorage.setActiveSessionId(sessionId);
    clearAllMessages();

    try {
      const msgs = await getSessionMessages(sessionId);
      globalMessages.set(msgs);
    } catch (e) {
      console.error("Error loading session messages:", e);
    }

    wsStore.disconnect();
  }
</script>

<main class="h-screen flex flex-col bg-gray-900 text-gray-100">
  <div class="border-b border-gray-800 p-3 flex justify-between items-center">
    <h1 class="text-xl font-semibold">Abby</h1>
    <div class="flex items-center gap-4">
      <button
        onclick={resetProject}
        hidden={!$wsStore.isConnected}
        disabled={isLoading || !$wsStore.isConnected}
        class="px-3 py-1 rounded-lg text-sm bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        Reset Project
      </button>
      <ConnectionStatus isConnected={$wsStore.isConnected} />
    </div>
  </div>
  {#if isLoading}
    <LoadingProgress loadingProgress={loading.progress} />
  {:else}
    <div class="flex flex-1 min-h-0 relative">
      <SessionList
        {showSessionPanel}
        onToggle={() => (showSessionPanel = !showSessionPanel)}
        onSessionSelect={handleSessionSelect}
        onNewChat={startNewSession}
      />

      <div class="flex-1 flex flex-col">
        <GenreSelector isConnected={$wsStore.isConnected} />
        <TrackList tracks={tracks.tracks} activeGenre={genres.activeGenre} />

        <!-- Global Chat Interface -->
        <div class="border-t border-gray-800 p-4">
          <Chat
            messages={$globalMessages}
            onSendMessage={(message) => {
              const msg: ChatMessage = {
                text: message,
                isUser: true,
                type: "text",
              };
              if ($wsStore.isConnected) {
                addGlobalMessage(msg);
                wsStore.sendMessage(message);
              }
            }}
            maxHeight="24rem"
          />
        </div>
      </div>

      <ParameterPanel
        parameterChanges={parameterChanges.changes}
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
