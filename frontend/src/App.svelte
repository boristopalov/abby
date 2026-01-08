<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { sessionStorage, activeSessionId } from "./lib/sessionStore";
  import {
    getRecentParameterChanges,
    getSessionMessages,
    getProjects,
    createProject,
    reindexProject,
  } from "./lib/apiCalls";
  import SessionList from "./components/SessionList.svelte";
  import ConnectionStatus from "./components/ConnectionStatus.svelte";
  import LoadingProgress from "./components/LoadingProgress.svelte";
  import GenreSelector from "./components/GenreSelector.svelte";
  import ParameterPanel from "./components/ParameterPanel.svelte";
  import TrackList from "./components/TrackList.svelte";
  import Chat from "./components/Chat.svelte";
  import {
    globalMessages,
    addGlobalMessage,
    clearAllMessages,
  } from "./lib/chatStore";
  import { wsStore } from "./lib/wsStore";
  import {
    loading,
    tracks,
    parameterChanges,
    genres,
    projectState,
    setActiveProject,
    loadActiveProjectFromStorage,
  } from "./lib/state.svelte";
  import type { ChatMessage, Project } from "./types";

  let showParameterPanel = $state(true);
  let showSessionPanel = $state(false);
  let intervalId: number = $state(0);
  let isLoading: boolean = $derived(
    loading.progress !== 100 && projectState.activeProjectId !== null
  );

  // Project creation state
  let newProjectName = $state("");
  let isCreatingProject = $state(false);
  let projectError = $state("");

  onMount(async () => {
    // Load projects
    try {
      projectState.projects = await getProjects();
    } catch (e) {
      console.error("Error loading projects:", e);
    }

    // Check for stored active project
    const storedProjectId = loadActiveProjectFromStorage();
    if (
      storedProjectId &&
      projectState.projects.some((p) => p.id === storedProjectId)
    ) {
      wsStore.connect();
    }

    // Poll every minute for parameter changes
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

  async function handleCreateProject() {
    if (!newProjectName.trim()) {
      projectError = "Please enter a project name";
      return;
    }

    isCreatingProject = true;
    projectError = "";

    try {
      const project = await createProject(newProjectName.trim());
      projectState.projects = [...projectState.projects, project];
      setActiveProject(project.id);
      newProjectName = "";
      wsStore.connect();
    } catch (e: any) {
      projectError = e.message || "Failed to create project";
    } finally {
      isCreatingProject = false;
    }
  }

  function selectProject(project: Project) {
    setActiveProject(project.id);
    clearAllMessages();
    loading.progress = 0;
    wsStore.disconnect();
    wsStore.connect();
  }

  async function handleReindexProject() {
    if (!projectState.activeProjectId) return;

    loading.progress = 0;
    wsStore.disconnect();

    try {
      await reindexProject(projectState.activeProjectId);
      // Refresh projects list
      projectState.projects = await getProjects();
      wsStore.connect();
    } catch (e: any) {
      projectError = e.message || "Failed to reindex project";
    }
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

  function changeProject() {
    wsStore.disconnect();
    setActiveProject(null);
    loading.progress = 0;
    tracks.tracks = [];
  }
</script>

<main class="h-screen flex flex-col bg-gray-900 text-gray-100">
  <div class="border-b border-gray-800 p-3 flex justify-between items-center">
    <h1 class="text-xl font-semibold">Abby</h1>
    <div class="flex items-center gap-4">
      {#if projectState.activeProjectId}
        <span class="text-sm text-gray-400">
          Project: {projectState.projects.find(
            (p) => p.id === projectState.activeProjectId
          )?.name || "Unknown"}
        </span>
        <button
          onclick={changeProject}
          class="px-3 py-1 rounded-lg text-sm bg-gray-700 text-gray-300 hover:bg-gray-600 transition-colors"
        >
          Change Project
        </button>
        <button
          onclick={handleReindexProject}
          disabled={isLoading || !$wsStore.isConnected}
          class="px-3 py-1 rounded-lg text-sm bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Re-index
        </button>
      {/if}
      <ConnectionStatus isConnected={$wsStore.isConnected} />
    </div>
  </div>

  {#if !projectState.activeProjectId}
    <!-- Project Selection Screen -->
    <div class="flex-1 flex items-center justify-center">
      <div class="w-full max-w-md p-6 space-y-6">
        <h2 class="text-2xl font-semibold text-center">Select a Project</h2>

        <!-- Existing Projects -->
        {#if projectState.projects.length > 0}
          <div class="space-y-2">
            <h3 class="text-sm text-gray-400 uppercase tracking-wide">
              Your Projects
            </h3>
            <div class="space-y-2">
              {#each projectState.projects as project}
                <button
                  onclick={() => selectProject(project)}
                  class="w-full p-3 rounded-lg bg-gray-800 hover:bg-gray-700 text-left transition-colors"
                >
                  <div class="font-medium">{project.name}</div>
                  <div class="text-sm text-gray-400">
                    Indexed: {new Date(project.indexedAt).toLocaleDateString()}
                  </div>
                </button>
              {/each}
            </div>
          </div>
        {/if}

        <!-- Create New Project -->
        <div class="space-y-2">
          <h3 class="text-sm text-gray-400 uppercase tracking-wide">
            Create New Project
          </h3>
          <div class="flex gap-2">
            <input
              type="text"
              bind:value={newProjectName}
              placeholder="Project name..."
              class="flex-1 px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 focus:border-purple-500 focus:outline-none"
              onkeydown={(e) => e.key === "Enter" && handleCreateProject()}
            />
            <button
              onclick={handleCreateProject}
              disabled={isCreatingProject}
              class="px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isCreatingProject ? "Creating..." : "Create"}
            </button>
          </div>
          {#if projectError}
            <p class="text-sm text-red-400">{projectError}</p>
          {/if}
          <p class="text-xs text-gray-500">
            Make sure Ableton Live is running with AbletonOSC before creating a
            project.
          </p>
        </div>
      </div>
    </div>
  {:else if isLoading}
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
