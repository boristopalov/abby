<script lang="ts">
  export let trackName: string;
  export let devices: Array<{ name: string }>;
  export let isCollapsed = false;

  function toggleCollapse() {
    isCollapsed = !isCollapsed;
  }
</script>

<div class="border border-gray-800 rounded-lg mb-4 bg-gray-900/50">
  <div
    class="p-4 flex items-center justify-between cursor-pointer hover:bg-gray-800/50"
    on:click={toggleCollapse}
  >
    <div class="flex items-center gap-4">
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
      <h3 class="text-lg font-medium">{trackName}</h3>
    </div>
    <div class="text-sm text-gray-400">
      {devices.length}
      {devices.length === 1 ? "device" : "devices"}
    </div>
  </div>

  {#if !isCollapsed}
    <div class="px-4 pb-4">
      <div class="mb-4">
        <h4 class="text-sm font-medium text-gray-400 mb-2">Devices</h4>
        <div class="space-y-1">
          {#each devices as device}
            <div class="text-sm bg-gray-800/50 px-3 py-2 rounded">
              {device.name}
            </div>
          {/each}
        </div>
      </div>

      <slot />
    </div>
  {/if}
</div>
