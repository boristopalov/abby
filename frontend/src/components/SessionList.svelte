<script lang="ts">
    import { slide } from "svelte/transition";
    import { onMount } from "svelte";
    import type { ChatSession, Track } from "../types";
    import { getSessions } from "../lib/apiCalls";
    import { activeSessionId } from "../lib/sessionStore";

    let {
        showSessionPanel,
        onToggle,
        onSessionSelect,
        onNewChat,
        tracks = [],
    } = $props<{
        showSessionPanel: boolean;
        onToggle: () => void;
        onSessionSelect: (sessionId: string) => void;
        onNewChat: () => void;
        tracks?: Track[];
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
    <aside
        class="session-sidebar"
        in:slide={{ axis: "x" }}
        out:slide={{ axis: "x" }}
    >
        <div class="sidebar-header">
            <h2 class="sidebar-title">Sessions</h2>
            <button onclick={onNewChat} class="btn-new-chat">
                + New Chat
            </button>
        </div>

        <div class="session-list">
            {#if isLoading}
                <p class="session-state-msg">Loading…</p>
            {:else if error}
                <p class="session-state-msg session-error">{error}</p>
            {:else if sessions.length === 0}
                <p class="session-state-msg">No sessions yet</p>
            {:else}
                {#each sessions as session (session.id)}
                    <button
                        onclick={() => handleSessionClick(session.id)}
                        class="session-entry {$activeSessionId === session.id ? 'session-entry--active' : ''}"
                    >
                        <div class="session-date">{formatDate(session.createdAt)}</div>
                        <div class="session-name">{session.name}</div>
                    </button>
                {/each}
            {/if}
        </div>
    </aside>
{/if}

<button
    onclick={onToggle}
    class="sidebar-toggle"
    aria-label={showSessionPanel ? "Hide chat sessions" : "Show chat sessions"}
>
    <svg
        xmlns="http://www.w3.org/2000/svg"
        class="h-4 w-4"
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
    /* ── Sidebar panel ── */
    .session-sidebar {
        width: 252px;
        flex-shrink: 0;
        border-right: 1px solid var(--border);
        background: var(--surface);
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .sidebar-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.875rem 1rem;
        border-bottom: 1px solid var(--border-light);
        flex-shrink: 0;
    }

    .sidebar-title {
        font-family: var(--font-serif);
        font-size: 0.9rem;
        font-weight: 500;
        color: var(--ink);
        margin: 0;
        letter-spacing: 0.015em;
    }

    .btn-new-chat {
        background: none;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 0.2rem 0.6rem;
        font-family: var(--font-body);
        font-size: 0.73rem;
        color: var(--ink-2);
        cursor: pointer;
        letter-spacing: 0.01em;
        transition: border-color 0.15s, color 0.15s;
    }
    .btn-new-chat:hover {
        border-color: var(--accent);
        color: var(--accent);
    }

    /* ── Session list ── */
    .session-list {
        flex: 1;
        overflow-y: auto;
        padding: 0.25rem 0;
    }

    .session-state-msg {
        text-align: center;
        padding: 1.5rem 1rem;
        font-family: var(--font-body);
        font-size: 0.82rem;
        color: var(--ink-3);
        font-style: italic;
        margin: 0;
    }
    .session-error { color: #b05050; }

    /* ── Session entries — journal style ── */
    .session-entry {
        width: 100%;
        text-align: left;
        background: none;
        border: none;
        border-left: 3px solid transparent;
        padding: 0.6rem 1rem 0.6rem 0.875rem;
        cursor: pointer;
        transition: background 0.12s, border-color 0.12s;
        position: relative;
    }
    .session-entry:not(:last-child)::after {
        content: '';
        display: block;
        position: absolute;
        bottom: 0;
        left: 1rem;
        right: 1rem;
        height: 1px;
        background: var(--border-light);
    }
    .session-entry:hover {
        background: var(--accent-light);
    }
    .session-entry--active {
        border-left-color: var(--accent);
        background: var(--accent-light);
    }

    /* Date in small caps above the name */
    .session-date {
        font-family: var(--font-body);
        font-size: 0.66rem;
        color: var(--ink-3);
        text-transform: uppercase;
        letter-spacing: 0.07em;
        margin-bottom: 0.2rem;
    }

    .session-name {
        font-family: var(--font-body);
        font-size: 0.84rem;
        color: var(--ink);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        line-height: 1.35;
    }

    /* ── Toggle tab on left edge ── */
    .sidebar-toggle {
        position: fixed;
        left: 0;
        top: 50%;
        transform: translateY(-50%);
        background: var(--surface);
        border: 1px solid var(--border);
        border-left: none;
        border-radius: 0 var(--radius) var(--radius) 0;
        padding: 0.5rem 0.35rem;
        color: var(--ink-3);
        cursor: pointer;
        z-index: 10;
        transition: color 0.15s, background 0.15s;
        box-shadow: var(--shadow-sm);
    }
    .sidebar-toggle:hover {
        color: var(--accent);
        background: var(--bg);
    }
</style>
