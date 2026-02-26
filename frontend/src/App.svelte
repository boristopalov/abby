<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import { sessionStorage, activeSessionId } from "./lib/sessionStore";
    import {
        getSessionMessages,
        getProjects,
        createProject,
    } from "./lib/apiCalls";
    import SessionList from "./components/SessionList.svelte";
    import ConnectionStatus from "./components/ConnectionStatus.svelte";
    import IndexingBanner from "./components/IndexingBanner.svelte";
    import ParameterPanel from "./components/ParameterPanel.svelte";
    import Chat from "./components/Chat.svelte";
    import {
        globalMessages,
        addGlobalMessage,
        clearAllMessages,
    } from "./lib/chatStore";
    import { wsStore } from "./lib/wsStore";
    import {
        tracks,
        parameterChanges,
        projectState,
        setActiveProject,
        loadActiveProjectFromStorage,
    } from "./lib/state.svelte";
    import type { ChatMessage, Project } from "./types";

    let showParameterPanel = $state(true);
    let showSessionPanel = $state(false);
    let intervalId: number = $state(0);

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
        wsStore.disconnect();
        wsStore.connect();
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
        tracks.tracks = [];
    }
</script>

<main class="app-shell">
    <!-- ── Header ── -->
    <header class="app-header">
        <h1 class="app-title">Abby</h1>
        <div class="header-right">
            {#if projectState.activeProjectId}
                <span class="project-label">
                    {projectState.projects.find(
                        (p) => p.id === projectState.activeProjectId,
                    )?.name || "Unknown"}
                </span>
                <button onclick={changeProject} class="btn-subtle">
                    Change Project
                </button>
            {/if}
            <ConnectionStatus isConnected={$wsStore.isConnected} />
        </div>
    </header>

    {#if !projectState.activeProjectId}
        <!-- ── Project Selection ── -->
        <div class="project-select-screen">
            <div class="project-select-card">
                <h2 class="project-select-heading">Select a Project</h2>

                {#if projectState.projects.length > 0}
                    <div class="form-section">
                        <div class="section-label">Your Projects</div>
                        <div class="project-list">
                            {#each projectState.projects as project}
                                <button
                                    onclick={() => selectProject(project)}
                                    class="project-item"
                                >
                                    <div class="project-item-name">
                                        {project.name}
                                    </div>
                                    <div class="project-item-meta">
                                        {project.indexedAt
                                            ? `Indexed ${new Date(project.indexedAt).toLocaleDateString()}`
                                            : "Not yet indexed"}
                                    </div>
                                </button>
                            {/each}
                        </div>
                    </div>
                {/if}

                <div class="form-section">
                    <div class="section-label">Create New Project</div>
                    <div class="create-row">
                        <input
                            type="text"
                            bind:value={newProjectName}
                            placeholder="Project name…"
                            class="create-input"
                            onkeydown={(e) =>
                                e.key === "Enter" && handleCreateProject()}
                        />
                        <button
                            onclick={handleCreateProject}
                            disabled={isCreatingProject}
                            class="btn-primary"
                        >
                            {isCreatingProject ? "Creating…" : "Create"}
                        </button>
                    </div>
                    {#if projectError}
                        <p class="error-msg">{projectError}</p>
                    {/if}
                    <p class="hint-text">
                        Make sure Ableton Live is running with AbletonOSC before
                        creating a project.
                    </p>
                </div>
            </div>
        </div>
    {:else}
        <!-- ── Workspace ── -->
        <div class="workspace">
            <SessionList
                {showSessionPanel}
                onToggle={() => (showSessionPanel = !showSessionPanel)}
                onSessionSelect={handleSessionSelect}
                onNewChat={startNewSession}
                tracks={tracks.tracks}
            />

            <div class="main-column">
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
                />
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

    /* ── Shell ── */
    .app-shell {
        height: 100vh;
        display: flex;
        flex-direction: column;
        background: var(--bg);
        color: var(--ink);
        font-family: var(--font-body);
    }

    /* ── Header ── */
    .app-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.625rem 1.5rem;
        border-bottom: 1px solid var(--border);
        background: var(--surface);
        flex-shrink: 0;
        box-shadow: var(--shadow-sm);
    }

    .app-title {
        font-family: var(--font-serif);
        font-size: 1.2rem;
        font-weight: 600;
        color: var(--ink);
        letter-spacing: 0.02em;
        margin: 0;
    }

    .header-right {
        display: flex;
        align-items: center;
        gap: 0.875rem;
    }

    .project-label {
        font-family: var(--font-body);
        font-size: 0.82rem;
        color: var(--ink-2);
        font-style: italic;
    }

    .btn-subtle {
        background: none;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 0.2rem 0.7rem;
        font-family: var(--font-body);
        font-size: 0.78rem;
        color: var(--ink-2);
        cursor: pointer;
        transition:
            border-color 0.15s,
            color 0.15s;
    }
    .btn-subtle:hover {
        border-color: var(--accent);
        color: var(--accent);
    }
    .btn-subtle:disabled {
        opacity: 0.4;
        cursor: not-allowed;
    }

    /* ── Project Selection ── */
    .project-select-screen {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 2rem;
    }

    .project-select-card {
        width: 100%;
        max-width: 440px;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius-lg);
        padding: 2.5rem;
        box-shadow: var(--shadow-md);
        display: flex;
        flex-direction: column;
        gap: 2rem;
    }

    .project-select-heading {
        font-family: var(--font-serif);
        font-size: 1.55rem;
        font-weight: 600;
        color: var(--ink);
        margin: 0;
        text-align: center;
        letter-spacing: 0.01em;
    }

    .form-section {
        display: flex;
        flex-direction: column;
        gap: 0.625rem;
    }

    .section-label {
        font-family: var(--font-body);
        font-size: 0.7rem;
        font-weight: 600;
        color: var(--ink-3);
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }

    .project-list {
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
    }

    .project-item {
        width: 100%;
        text-align: left;
        background: var(--bg);
        border: 1px solid var(--border-light);
        border-radius: var(--radius);
        padding: 0.7rem 1rem;
        cursor: pointer;
        transition:
            border-color 0.15s,
            background 0.15s;
    }
    .project-item:hover {
        border-color: var(--accent);
        background: var(--accent-light);
    }

    .project-item-name {
        font-family: var(--font-body);
        font-size: 0.9rem;
        color: var(--ink);
        font-weight: 500;
    }

    .project-item-meta {
        font-size: 0.73rem;
        color: var(--ink-3);
        margin-top: 0.15rem;
    }

    .create-row {
        display: flex;
        gap: 0.5rem;
    }

    .create-input {
        flex: 1;
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 0.5rem 0.875rem;
        font-family: var(--font-body);
        font-size: 0.9rem;
        color: var(--ink);
        outline: none;
        transition: border-color 0.15s;
    }
    .create-input::placeholder {
        color: var(--ink-3);
        font-style: italic;
    }
    .create-input:focus {
        border-color: var(--accent);
    }

    .btn-primary {
        background: var(--accent);
        color: #fff;
        border: none;
        border-radius: var(--radius);
        padding: 0.5rem 1.25rem;
        font-family: var(--font-body);
        font-size: 0.85rem;
        cursor: pointer;
        transition: opacity 0.15s;
        white-space: nowrap;
    }
    .btn-primary:hover {
        opacity: 0.85;
    }
    .btn-primary:disabled {
        opacity: 0.4;
        cursor: not-allowed;
    }

    .error-msg {
        font-size: 0.8rem;
        color: #b05050;
        margin: 0;
    }

    .hint-text {
        font-size: 0.73rem;
        color: var(--ink-3);
        margin: 0;
        line-height: 1.55;
        font-style: italic;
    }

    /* ── Workspace (3-pane) ── */
    .workspace {
        flex: 1;
        display: flex;
        min-height: 0;
        position: relative;
    }

    .main-column {
        flex: 1;
        display: flex;
        flex-direction: column;
        min-height: 0;
        min-width: 0;
    }
</style>
