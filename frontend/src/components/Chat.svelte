<script lang="ts">
  import type { ChatMessage, Track } from "../types";
  import { slide } from "svelte/transition";
  import { tracks } from "../lib/state.svelte";

  let {
    messages = [],
    onSendMessage,
    isCollapsed = true,
    maxHeight = "12rem", // default height for track chats
  } = $props<{
    messages: ChatMessage[];
    onSendMessage: (message: string) => void;
    isCollapsed?: boolean;
    maxHeight?: string;
  }>();

  let chatInput = $state("");
  let inputRef: HTMLInputElement;
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
      isCollapsed = true;
    }
  }

  // Track input changes to hide dropdown when # is deleted
  $effect(() => {
    if (!chatInput.includes("#")) {
      isSelectingTrack = false;
    }
  });

  function handleClickOutside(event: MouseEvent) {
    if (!inputRef.contains(event.target as Node)) {
      isCollapsed = true;
      isSelectingTrack = false;
    }
  }

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

  $effect(() => {
    if (!isCollapsed) {
      document.addEventListener("click", handleClickOutside);
      return () => document.removeEventListener("click", handleClickOutside);
    }
  });

  // Scroll to bottom when new messages arrive or chat opens
  $effect(() => {
    if (!isCollapsed && messagesContainer) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  });
</script>

<div class="flex flex-col">
  <div class="relative">
    <div class="relative flex-1">
      {#if !isCollapsed}
        <div class="absolute bottom-full w-full">
          <div
            bind:this={messagesContainer}
            class="bg-gray-800/100 rounded-t-lg w-full overflow-y-auto p-3 border-x border-t border-gray-700 space-y-2"
            style="max-height: {maxHeight}"
          >
            {#each messages as message}
              <div
                class="flex {message.isUser ? 'justify-end' : 'justify-start'}"
              >
                <div
                  class={`max-w-[85%] break-words ${
                    message.isUser
                      ? "bg-blue-500 text-white rounded-2xl rounded-tr-sm"
                      : "bg-gray-700 text-gray-100 rounded-2xl rounded-tl-sm"
                  } px-4 py-2 text-sm`}
                >
                  {@html message.text}
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

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
            class="absolute bottom-full left-0 right-0 bg-gray-800 border border-gray-700 rounded-t-lg shadow-lg max-h-48 overflow-y-auto {selectedTracks.length >
            0
              ? 'mb-10'
              : ''}"
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
          bind:this={inputRef}
          type="text"
          bind:value={chatInput}
          onkeydown={handleKeyPress}
          onfocus={() => (isCollapsed = false)}
          onclick={() => (isCollapsed = false)}
          placeholder="Send a message... (Use # to tag tracks)"
          class="w-full {!isCollapsed || selectedTracks.length > 0 || chatInput
            ? 'bg-gray-800 rounded-t-none border-x border-b'
            : 'bg-gray-800/50 rounded-lg'} border-gray-700 px-4 py-2 pr-12 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50"
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
</div>
