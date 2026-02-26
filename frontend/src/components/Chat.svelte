<script lang="ts">
  import { marked } from "marked";
  import type { ChatMessage, Track } from "../types";
  import { tracks } from "../lib/state.svelte";
  import { wsStore } from "../lib/wsStore";
  import { updateLastPendingApproval } from "../lib/chatStore";

  function renderMarkdown(text: string): string {
    return marked.parse(text) as string;
  }

  let {
    messages = [],
    onSendMessage,
  } = $props<{
    messages: ChatMessage[];
    onSendMessage: (message: string) => void;
  }>();

  let chatInput = $state("");
  let messagesContainer: HTMLDivElement | undefined = $state(undefined);
  let isSelectingTrack = $state(false);
  let selectedTracks = $state<Track[]>([]);
  let filteredTracks = $derived(getFilteredTracks());

  function getFilteredTracks(): Track[] {
    const hashIndex = chatInput.lastIndexOf("#");
    if (hashIndex === -1) return tracks.tracks;

    const searchTerm = chatInput.slice(hashIndex + 1).toLowerCase();
    if (!searchTerm) return tracks.tracks;

    return tracks.tracks.filter((track) => {
      const name = track.name.toLowerCase();
      let searchIndex = 0;
      let trackIndex = 0;

      // Try to find all search term characters in order in the track name
      while (searchIndex < searchTerm.length && trackIndex < name.length) {
        if (searchTerm[searchIndex] === name[trackIndex]) {
          searchIndex++;
        }
        trackIndex++;
      }

      // If we found all characters, it's a match
      return searchIndex === searchTerm.length;
    });
  }

  function handleSubmit() {
    if (chatInput.trim()) {
      // Add selected tracks as context to the message
      const tracksContext = selectedTracks.map((t) => t.id).join(",");
      const messageWithContext = tracksContext
        ? `[tracks:${tracksContext}] ${chatInput}`
        : chatInput;
      onSendMessage(messageWithContext);
      chatInput = "";
      selectedTracks = [];
    }
  }

  function handleKeyPress(event: KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    } else if (event.key === "#") {
      isSelectingTrack = true;
    } else if (event.key === "Escape") {
      isSelectingTrack = false;
    }
  }

  // Track input changes to hide dropdown when # is deleted
  $effect(() => {
    if (!chatInput.includes("#")) {
      isSelectingTrack = false;
    }
  });

  function selectTrack(track: Track) {
    if (!selectedTracks.find((t) => t.id === track.id)) {
      selectedTracks = [...selectedTracks, track];
    }
    isSelectingTrack = false;

    // Replace the search term with the selected track name
    const hashIndex = chatInput.lastIndexOf("#");
    if (hashIndex !== -1) {
      const afterHash = chatInput.slice(hashIndex);
      const nextSpaceIndex = afterHash.indexOf(" ");
      const endIndex =
        nextSpaceIndex === -1 ? chatInput.length : hashIndex + nextSpaceIndex;
      chatInput = chatInput.slice(0, hashIndex) + chatInput.slice(endIndex);
    }
  }

  function removeTrack(trackId: string) {
    selectedTracks = selectedTracks.filter((t) => t.id !== trackId);
  }

  function handleApproval(message: ChatMessage, approved: boolean) {
    const approvals = Object.fromEntries(
      (message.requests ?? []).map((r) => [r.tool_call_id, approved]),
    );
    updateLastPendingApproval((msg) => ({
      ...msg,
      approvalState: approved ? "approved" : "denied",
    }));
    wsStore.sendApproval(approvals);
  }

  // Scroll to bottom when new messages arrive
  $effect(() => {
    if (messagesContainer && messages.length > 0) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  });
</script>

<style>
  /* ── Shell ── */
  .chat-shell {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    background: var(--bg);
  }

  /* ── Messages area ── */
  .messages-outer {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .messages-column {
    width: 100%;
    max-width: 720px;
    padding: 2rem 1.5rem 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  /* ── Message rows ── */
  .message-row {
    display: flex;
    animation: msg-appear 150ms ease-out both;
  }
  .message-row--user { justify-content: flex-end; }
  .message-row--ai   { justify-content: flex-start; }
  .message-row--tool { justify-content: flex-start; }

  @keyframes msg-appear {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  /* ── User message — warm blockquote ── */
  .msg-user {
    max-width: 72%;
    background: var(--accent-light);
    border: 1px solid rgba(196, 113, 74, 0.22);
    border-radius: var(--radius-lg) var(--radius-lg) var(--radius) var(--radius-lg);
    padding: 0.75rem 1.1rem;
    font-family: var(--font-body);
    font-size: 0.9rem;
    line-height: 1.65;
    color: var(--ink);
  }

  /* ── AI message — flowing prose ── */
  .msg-ai {
    max-width: 88%;
    font-family: var(--font-body);
    font-size: 0.925rem;
    line-height: 1.8;
    color: var(--ink);
  }

  /* ── Tool call — reference card ── */
  .msg-tool {
    max-width: 90%;
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-left: 3px solid var(--accent);
    border-radius: 0 var(--radius) var(--radius) 0;
    overflow: hidden;
    box-shadow: var(--shadow-sm);
  }

  .tool-header {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    padding: 0.45rem 0.875rem;
    color: var(--ink-2);
  }

  .tool-icon {
    font-size: 0.65rem;
    color: var(--accent);
    opacity: 0.8;
    flex-shrink: 0;
  }

  .tool-name {
    font-family: var(--font-mono);
    font-size: 0.78rem;
    color: var(--ink);
  }

  .tool-args {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--ink-3);
  }

  .tool-result {
    border-top: 1px solid var(--border-light);
    padding: 0.4rem 0.875rem;
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--ink-2);
    max-height: 6rem;
    overflow-y: auto;
    white-space: pre-wrap;
    background: var(--bg);
  }

  /* ── Markdown content (global — rendered via {@html}) ── */
  :global(.message-content p) { margin: 0.35rem 0; }
  :global(.message-content p:first-child) { margin-top: 0; }
  :global(.message-content p:last-child)  { margin-bottom: 0; }
  :global(.message-content ul),
  :global(.message-content ol) { margin: 0.35rem 0; padding-left: 1.4rem; }
  :global(.message-content ul) { list-style-type: disc; }
  :global(.message-content ol) { list-style-type: decimal; }
  :global(.message-content li) { margin: 0.15rem 0; }
  :global(.message-content code) {
    background: var(--surface-warm);
    border: 1px solid var(--border-light);
    border-radius: 3px;
    padding: 0.1rem 0.3rem;
    font-family: var(--font-mono);
    font-size: 0.83em;
    color: var(--ink);
  }
  :global(.message-content pre) {
    background: var(--surface-warm);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 0 var(--radius) var(--radius) 0;
    padding: 0.75rem 1rem;
    margin: 0.6rem 0;
    overflow-x: auto;
  }
  :global(.message-content pre code) {
    background: none;
    border: none;
    padding: 0;
    font-size: 0.82em;
    color: var(--ink);
  }
  :global(.message-content strong) { font-weight: 600; color: var(--ink); }
  :global(.message-content em)     { font-style: italic; }
  :global(.message-content h1),
  :global(.message-content h2),
  :global(.message-content h3) {
    font-family: var(--font-serif);
    font-weight: 600;
    color: var(--ink);
    margin: 0.75rem 0 0.3rem;
  }
  :global(.message-content h1) { font-size: 1.15em; }
  :global(.message-content h2) { font-size: 1.07em; }
  :global(.message-content h3) { font-size: 1em; }
  :global(.message-content a) {
    color: var(--accent);
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  :global(.message-content blockquote) {
    border-left: 3px solid var(--border);
    padding-left: 0.875rem;
    margin: 0.5rem 0;
    color: var(--ink-2);
    font-style: italic;
  }

  /* ── Approval card ── */
  .msg-approval {
    max-width: 90%;
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-left: 3px solid #c0892a;
    border-radius: 0 var(--radius) var(--radius) 0;
    overflow: hidden;
    box-shadow: var(--shadow-sm);
  }

  .approval-header {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    padding: 0.45rem 0.875rem;
  }

  .approval-icon {
    font-size: 0.7rem;
    color: #c0892a;
    flex-shrink: 0;
  }

  .approval-label {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    font-weight: 600;
    color: #c0892a;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .approval-requests {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .approval-request-item {
    padding: 0.35rem 0.875rem;
    border-top: 1px solid var(--border-light);
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
  }

  .approval-tool-name {
    font-family: var(--font-mono);
    font-size: 0.78rem;
    color: var(--ink);
  }

  .approval-tool-args {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--ink-3);
  }

  .approval-actions {
    display: flex;
    gap: 0.5rem;
    padding: 0.5rem 0.875rem 0.6rem;
    border-top: 1px solid var(--border-light);
    background: var(--bg);
  }

  .approval-decided {
    padding: 0.45rem 0.875rem;
    border-top: 1px solid var(--border-light);
    background: var(--bg);
    font-family: var(--font-mono);
    font-size: 0.72rem;
  }

  .approval-decided--approved { color: #5a8a5a; }
  .approval-decided--denied   { color: #8a5a5a; }

  .btn-approve {
    background: #3a6e3a;
    color: #fff;
    border: none;
    border-radius: var(--radius);
    padding: 0.3rem 0.875rem;
    font-family: var(--font-body);
    font-size: 0.78rem;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  .btn-approve:hover { opacity: 0.85; }

  .btn-deny {
    background: none;
    color: var(--ink-2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.3rem 0.875rem;
    font-family: var(--font-body);
    font-size: 0.78rem;
    cursor: pointer;
    transition: border-color 0.15s, color 0.15s;
  }
  .btn-deny:hover { border-color: #8a3a3a; color: #8a3a3a; }

  /* ── Input area ── */
  .chat-input-area {
    border-top: 1px solid var(--border-light);
    background: var(--surface);
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0.75rem 1.5rem 1.1rem;
    flex-shrink: 0;
  }

  .input-inner {
    width: 100%;
    max-width: 720px;
    position: relative;
  }

  /* Selected track chips */
  .track-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
    padding-bottom: 0.4rem;
  }

  .track-chip {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    background: var(--accent-light);
    border: 1px solid rgba(196, 113, 74, 0.25);
    border-radius: 99px;
    padding: 0.2rem 0.6rem;
    font-family: var(--font-body);
    font-size: 0.77rem;
    color: var(--accent);
  }

  .track-chip button {
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    color: inherit;
    opacity: 0.6;
    display: flex;
    align-items: center;
  }
  .track-chip button:hover { opacity: 1; }

  /* Track dropdown */
  .track-dropdown {
    position: absolute;
    bottom: 100%;
    left: 0;
    right: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-bottom: none;
    border-radius: var(--radius) var(--radius) 0 0;
    max-height: 12rem;
    overflow-y: auto;
    box-shadow: var(--shadow-md);
    z-index: 20;
  }

  .track-option {
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    border-bottom: 1px solid var(--border-light);
    padding: 0.5rem 1rem;
    font-family: var(--font-body);
    font-size: 0.88rem;
    color: var(--ink);
    cursor: pointer;
    transition: background 0.1s;
  }
  .track-option:last-child { border-bottom: none; }
  .track-option:hover { background: var(--accent-light); }

  /* Input row */
  .input-row {
    display: flex;
    align-items: center;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--bg);
    overflow: hidden;
    transition: border-color 0.15s;
  }
  .input-row:focus-within { border-color: var(--accent); }

  .chat-input {
    flex: 1;
    background: none;
    border: none;
    outline: none;
    padding: 0.625rem 1rem;
    font-family: var(--font-body);
    font-size: 0.9rem;
    color: var(--ink);
    line-height: 1.5;
  }
  .chat-input::placeholder { color: var(--ink-3); font-style: italic; }

  .send-btn {
    background: none;
    border: none;
    border-left: 1px solid var(--border-light);
    padding: 0.5rem 0.75rem;
    cursor: pointer;
    color: var(--ink-3);
    display: flex;
    align-items: center;
    transition: color 0.15s;
    flex-shrink: 0;
  }
  .send-btn:hover { color: var(--accent); }
</style>

<div class="chat-shell">
  <!-- Messages area -->
  <div class="messages-outer" bind:this={messagesContainer}>
    <div class="messages-column">
      {#each messages as message}
        <div class="message-row {message.isUser ? 'message-row--user' : message.type === 'function_call' || message.type === 'approval_required' ? 'message-row--tool' : 'message-row--ai'}">
          {#if message.type === "function_call"}
            <!-- Reference card for tool calls -->
            <div class="msg-tool">
              <div class="tool-header">
                <span class="tool-icon">⚙</span>
                <span class="tool-name">{message.text}</span>
                {#if message.arguments && Object.keys(message.arguments).length > 0}
                  <span class="tool-args">
                    ({Object.entries(message.arguments).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})
                  </span>
                {/if}
              </div>
              {#if message.result}
                <div class="tool-result">{message.result}</div>
              {/if}
            </div>
          {:else if message.type === "approval_required"}
            <!-- Approval request card -->
            <div class="msg-approval">
              <div class="approval-header">
                <span class="approval-icon">⚠</span>
                <span class="approval-label">Approval required</span>
              </div>
              <div class="approval-requests">
                {#each message.requests ?? [] as req}
                  <div class="approval-request-item">
                    <span class="approval-tool-name">{req.tool_name}</span>
                    {#if Object.keys(req.arguments).length > 0}
                      <span class="approval-tool-args">
                        ({Object.entries(req.arguments).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})
                      </span>
                    {/if}
                  </div>
                {/each}
              </div>
              {#if message.approvalState === "pending"}
                <div class="approval-actions">
                  <button class="btn-approve" onclick={() => handleApproval(message, true)}>
                    Approve
                  </button>
                  <button class="btn-deny" onclick={() => handleApproval(message, false)}>
                    Deny
                  </button>
                </div>
              {:else}
                <div class="approval-decided approval-decided--{message.approvalState}">
                  {message.approvalState === "approved" ? "Approved" : "Denied"}
                </div>
              {/if}
            </div>
          {:else}
            <div class="{message.isUser ? 'msg-user' : 'msg-ai message-content'}">
              {#if message.isUser}
                {message.text}
              {:else}
                {@html renderMarkdown(message.text)}
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  </div>

  <!-- Input area -->
  <div class="chat-input-area">
    <div class="input-inner">
      {#if selectedTracks.length > 0}
        <div class="track-chips">
          {#each selectedTracks as track}
            <div class="track-chip">
              <span>{track.name}</span>
              <button onclick={() => removeTrack(track.id)} aria-label="Remove track">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                </svg>
              </button>
            </div>
          {/each}
        </div>
      {/if}

      {#if isSelectingTrack}
        <div class="track-dropdown">
          {#each filteredTracks as track}
            <button class="track-option" onclick={() => selectTrack(track)}>
              {track.name}
            </button>
          {/each}
        </div>
      {/if}

      <div class="input-row">
        <input
          type="text"
          class="chat-input"
          bind:value={chatInput}
          onkeydown={handleKeyPress}
          placeholder="Write a message… (use # to tag a track)"
        />
        <button class="send-btn" onclick={handleSubmit} aria-label="Send message">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-8.707l-3-3a1 1 0 00-1.414 1.414L10.586 9H7a1 1 0 100 2h3.586l-1.293 1.293a1 1 0 101.414 1.414l3-3a1 1 0 000-1.414z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</div>
