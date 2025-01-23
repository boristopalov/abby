<script lang="ts">
import { slide } from "svelte/transition";
import type { ParameterChange } from "../types";

  export let parameterChanges: ParameterChange[];
  export let showParameterPanel: boolean;
  export let onToggle: () => void;
</script>

{#if showParameterPanel}
  <div
    class="w-80 border-l border-gray-800 bg-gray-900 flex flex-col overflow-hidden shrink-0"
    in:slide={{ axis: "x" }}
    out:slide={{ axis: "x" }}
  >
    <div class="p-3 border-b border-gray-800 flex justify-between items-center">
      <h2 class="font-semibold">Parameter Changes</h2>
    </div>
    <div class="flex-1 overflow-y-auto p-4 space-y-2">
      {#each parameterChanges as change}
        <div
          class="border-l-2 border-purple-500/30 pl-3 mb-3 hover:border-purple-500/50 transition-colors"
        >
          <div class="text-xs text-gray-400 mb-1">
            {change.trackName} / {change.deviceName}
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-gray-300">{change.paramName}</span>
            <span
              class="text-xs font-mono bg-blue-500/10 text-blue-300 px-2 py-0.5 rounded"
            >
              {change.oldValue.toFixed(2)} --> {change.newValue.toFixed(2)}
            </span>
          </div>
          <div class="text-xs text-gray-500 mt-1">
            {new Date(change.timestamp).toLocaleTimeString()}
          </div>
        </div>
      {/each}
    </div>
  </div>
{/if}

<button
  on:click={onToggle}
  class="fixed right-0 top-1/2 -translate-y-1/2 bg-gray-800 p-2 rounded-l-lg text-gray-400 hover:text-gray-200 hover:bg-gray-700"
  aria-label={showParameterPanel
    ? "hide parameter changes"
    : "show parameter changes"}
>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    class="h-5 w-5"
    viewBox="0 0 20 20"
    fill="currentColor"
  >
    <path
      fill-rule="evenodd"
      d={showParameterPanel
        ? "M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
        : "M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"}
      clip-rule="evenodd"
    />
  </svg>
</button>
