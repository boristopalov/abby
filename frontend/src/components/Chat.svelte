<script lang="ts">
  import type { ChatMessage } from "../types";
  import { slide } from "svelte/transition";

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

  function handleSubmit() {
    if (chatInput.trim()) {
      onSendMessage(chatInput);
      chatInput = "";
    }
  }

  function handleKeyPress(event: KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  }

  function handleClickOutside(event: MouseEvent) {
    if (!inputRef.contains(event.target as Node)) {
      isCollapsed = true;
    }
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
      <input
        bind:this={inputRef}
        type="text"
        bind:value={chatInput}
        onkeydown={handleKeyPress}
        onfocus={() => (isCollapsed = false)}
        placeholder="Send a message..."
        class="w-full bg-gray-800/50 rounded-lg {!isCollapsed
          ? 'rounded-t-none border-x border-b'
          : ''} border-gray-700 px-4 py-2 pr-12 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50"
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
