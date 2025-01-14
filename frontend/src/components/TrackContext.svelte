<script lang="ts">
  interface Insight {
    type: "success" | "suggestion" | "warning";
    message: string;
    details?: string;
  }

  export let insights: Insight[] = [];

  function getInsightColor(type: Insight["type"]): string {
    switch (type) {
      case "success":
        return "text-green-400";
      case "suggestion":
        return "text-blue-400";
      case "warning":
        return "text-yellow-400";
    }
  }

  function getInsightIcon(type: Insight["type"]): string {
    switch (type) {
      case "success":
        return "✓";
      case "suggestion":
        return "💡";
      case "warning":
        return "⚠";
    }
  }
</script>

<div class="bg-gray-800/50 rounded-lg p-4 text-sm">
  <h3 class="font-medium text-purple-300 mb-3 text-left">Insights</h3>

  {#if insights.length > 0}
    <ul class="space-y-2 text-left">
      {#each insights as insight}
        <li class="flex items-start gap-2">
          <span class={getInsightColor(insight.type)}>
            {getInsightIcon(insight.type)}
          </span>
          <div class="flex-1">
            <div class="text-gray-200">{insight.message}</div>
            {#if insight.details}
              <div class="text-gray-400 text-xs mt-0.5">
                {insight.details}
              </div>
            {/if}
          </div>
        </li>
      {/each}
    </ul>
  {:else}
    <p class="text-gray-400 italic">
      No insights available yet. Try getting feedback or matching the genre
      style.
    </p>
  {/if}
</div>
