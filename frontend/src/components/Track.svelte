<script lang="ts">
  import TrackContext from "./TrackContext.svelte";
  import { trackChats, initializeTrackChat } from "../lib/chatStore";
  import { wsStore } from "../lib/wsStore";

  let {
    trackId,
    trackName,
    devices,
    isCollapsed = true,
    activeGenre,
  } = $props<{
    trackId: number;
    trackName: string;
    devices: Array<{ name: string }>;
    isCollapsed?: boolean;
    activeGenre: string | null;
  }>();

  const insights = $state([
    {
      type: "success" as const,
      message: "Sidechained to kick",
      details: "Good pumping effect that matches the genre",
    },
    {
      type: "suggestion" as const,
      message: `Try typical ${activeGenre} processing`,
      details:
        "Add some saturation and compression to match the genre's character",
    },
    {
      type: "warning" as const,
      message: "Frequency masking with lead synth",
      details: "Consider EQ adjustments around 2-4kHz",
    },
  ]);

  // Initialize chat for this track
  initializeTrackChat(trackName);

  // Subscribe to track-specific messages
  const trackMessages = $derived($trackChats[trackName] || []);

  // Make quickActions reactive to activeGenre changes
  const quickActions = $derived([
    `Match ${activeGenre} Style`,
    "Get Insights",
    "Explain Production",
  ]);

  function toggleCollapse() {
    isCollapsed = !isCollapsed;
  }

  function handleQuickAction(action: string) {
    const payload = {
      text: action,
      isUser: true,
      type: "text",
      trackId: trackId,
    };
    wsStore.sendMessage(JSON.stringify(payload));
  }
</script>

<div
  class="rounded-lg mb-4 transition-all duration-200 border border-gray-800 bg-gray-900/50"
>
  <div class="flex">
    <!-- Left Side: Track Info & Actions -->
    <div class="w-1/2 border-r border-gray-800">
      <!-- Header -->
      <div>
        <button
          class="w-full p-4 flex items-center gap-4 hover:bg-gray-800/50 text-left border-b border-gray-800"
          onclick={toggleCollapse}
          onkeydown={(e) => e.key === "Enter" && toggleCollapse()}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-4 w-4 transform transition-transform {isCollapsed
              ? '-rotate-90'
              : ''}"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fill-rule="evenodd"
              d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
              clip-rule="evenodd"
            />
          </svg>
          <div>
            <h3 class="text-lg font-medium">{trackName}</h3>
            <div class="flex items-center gap-2 mt-1 flex-wrap">
              {#each devices as device, i}
                <span
                  class="text-xs bg-gray-800/80 px-2 py-0.5 rounded text-gray-400"
                >
                  {device.name}
                </span>
                {#if i < devices.length - 1}
                  <span class="text-gray-600">→</span>
                {/if}
              {/each}
            </div>
          </div>
        </button>
      </div>

      {#if !isCollapsed}
        <div class="px-4 pb-4">
          <div class="space-y-4">
            <!-- Quick Actions -->
            <div class="space-y-2 mt-3 text-left">
              <div class="flex flex-wrap gap-2">
                {#each quickActions as action}
                  <button
                    onclick={() => handleQuickAction(action)}
                    class="text-sm bg-blue-500/20 text-blue-300 px-3 py-1 rounded-full hover:bg-blue-500/30 transition-colors"
                  >
                    {action}
                  </button>
                {/each}
              </div>
            </div>
          </div>
        </div>
      {/if}
    </div>

    <!-- Right Side: Insights -->
    {#if !isCollapsed}
      <div class="w-1/2 p-4">
        <TrackContext {insights} />
      </div>
    {/if}
  </div>
</div>
