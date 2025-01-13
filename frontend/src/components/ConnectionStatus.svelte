<script lang="ts">
  export let isConnected: boolean;
</script>

<div
  class={`px-3 py-1 rounded-full text-sm disabled:cursor-not-allowed ${
    isConnected
      ? "bg-green-500/10 text-green-400"
      : "bg-red-500/10 text-red-400"
  }`}
>
  {isConnected ? "Connected" : "Disconnected"}
</div>
