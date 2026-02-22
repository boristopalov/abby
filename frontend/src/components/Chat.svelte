<script lang="ts">
  import { marked } from "marked";
  import type { ChatMessage, Track } from "../types";
  import { tracks } from "../lib/state.svelte";

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

  // Scroll to bottom when new messages arrive
  $effect(() => {
    if (messagesContainer && messages.length > 0) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  });
</script>

<style>
  :global(.message-content p) {
    margin: 0.25rem 0;
  }
  :global(.message-content p:first-child) {
    margin-top: 0;
  }
  :global(.message-content p:last-child) {
    margin-bottom: 0;
  }
  :global(.message-content ul),
  :global(.message-content ol) {
    margin: 0.25rem 0;
    padding-left: 1.25rem;
  }
  :global(.message-content ul) {
    list-style-type: disc;
  }
  :global(.message-content ol) {
    list-style-type: decimal;
  }
  :global(.message-content li) {
    margin: 0.1rem 0;
  }
  :global(.message-content code) {
    background: rgba(0, 0, 0, 0.3);
    border-radius: 0.25rem;
    padding: 0.1rem 0.3rem;
    font-family: monospace;
    font-size: 0.85em;
  }
  :global(.message-content pre) {
    background: rgba(0, 0, 0, 0.3);
    border-radius: 0.375rem;
    padding: 0.75rem;
    margin: 0.5rem 0;
    overflow-x: auto;
  }
  :global(.message-content pre code) {
    background: none;
    padding: 0;
  }
  :global(.message-content strong) {
    font-weight: 600;
  }
  :global(.message-content em) {
    font-style: italic;
  }
  :global(.message-content h1),
  :global(.message-content h2),
  :global(.message-content h3) {
    font-weight: 600;
    margin: 0.5rem 0 0.25rem;
  }
  :global(.message-content h1) { font-size: 1.1em; }
  :global(.message-content h2) { font-size: 1.05em; }
  :global(.message-content h3) { font-size: 1em; }
  :global(.message-content a) {
    color: #93c5fd;
    text-decoration: underline;
  }
  :global(.message-content blockquote) {
    border-left: 3px solid rgba(255, 255, 255, 0.2);
    padding-left: 0.75rem;
    margin: 0.5rem 0;
    color: rgba(255, 255, 255, 0.7);
  }
</style>

<div class="flex flex-col h-full">
  <!-- Messages area -->
  <div
    bind:this={messagesContainer}
    class="flex-1 overflow-y-auto p-3 space-y-2"
  >
    {#each messages as message}
      <div
        class="flex {message.isUser ? 'justify-end' : 'justify-start'}"
      >
        {#if message.type === "function_call"}
          <div class="max-w-[85%] bg-gray-800 border border-gray-600/50 rounded-lg text-xs font-mono overflow-hidden">
            <div class="px-3 py-1.5 text-gray-400">
              <span class="text-amber-400/80">⚙</span>
              <span class="text-gray-200 ml-1">{message.text}</span>
              {#if message.arguments && Object.keys(message.arguments).length > 0}
                <span class="text-gray-500 ml-1">
                  ({Object.entries(message.arguments).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})
                </span>
              {/if}
            </div>
            {#if message.result}
              <div class="border-t border-gray-700/50 px-3 py-1.5 text-gray-500 max-h-24 overflow-y-auto whitespace-pre-wrap">
                {message.result}
              </div>
            {/if}
          </div>
        {:else}
          <div
            class={`max-w-[85%] break-words ${
              message.isUser
                ? "bg-blue-500 text-white rounded-2xl rounded-tr-sm"
                : "bg-gray-700 text-gray-100 rounded-2xl rounded-tl-sm message-content"
            } px-4 py-2 text-sm`}
          >
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

  <!-- Input area -->
  <div class="border-t border-gray-700 p-3">
    <div class="relative">
        {#if selectedTracks.length > 0}
          <div
            class="absolute bottom-full left-0 right-0 flex flex-wrap gap-1.5 p-2 bg-gray-800 border-x border-t border-gray-700 rounded-t"
          >
            {#each selectedTracks as track}
              <div
                class="bg-blue-500/30 text-blue-200 px-2.5 py-1 rounded-full text-xs flex items-center gap-1.5 border border-blue-500/20 shadow-sm"
              >
                <span class="font-medium">{track.name}</span>
                <button
                  onclick={() => removeTrack(track.id)}
                  class="hover:text-blue-100 transition-colors"
                  aria-label="Remove track"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    class="h-3.5 w-3.5"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path
                      fill-rule="evenodd"
                      d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                      clip-rule="evenodd"
                    />
                  </svg>
                </button>
              </div>
            {/each}
          </div>
        {/if}

        {#if isSelectingTrack}
        <div
          class="absolute bottom-full left-0 right-0 bg-gray-800 border border-gray-700 rounded-t-lg shadow-lg max-h-48 overflow-y-auto {selectedTracks.length > 0 ? 'mb-10' : ''}"
        >
          {#each filteredTracks as track}
            <button
              onclick={() => selectTrack(track)}
              class="w-full px-4 py-2 text-left text-sm hover:bg-gray-700 text-gray-200"
            >
              {track.name}
            </button>
          {/each}
        </div>
      {/if}

      <input
        type="text"
        bind:value={chatInput}
        onkeydown={handleKeyPress}
        placeholder="Send a message... (Use # to tag tracks)"
        class="w-full bg-gray-800 rounded-lg border border-gray-700 px-4 py-2 pr-12 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50"
      />

      <button
        onclick={handleSubmit}
        class="absolute right-2 top-1/2 -translate-y-1/2 text-blue-400 hover:text-blue-300"
        aria-label="Send message"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          class="h-5 w-5"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fill-rule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-8.707l-3-3a1 1 0 00-1.414 1.414L10.586 9H7a1 1 0 100 2h3.586l-1.293 1.293a1 1 0 101.414 1.414l3-3a1 1 0 000-1.414z"
            clip-rule="evenodd"
          />
        </svg>
      </button>
    </div>
  </div>
</div>
