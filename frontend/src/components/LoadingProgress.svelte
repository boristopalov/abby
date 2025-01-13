<script lang="ts">
  export let loadingProgress: number;
</script>

<div class="flex flex-col items-center justify-center h-full p-8">
  <div
    class="w-full max-w-md bg-gray-700 rounded-full h-4 mb-4 overflow-hidden relative"
  >
    <div
      class="bg-green-500 h-4 rounded-full transition-all duration-300 ease-in-out relative"
      style="width: {loadingProgress}%"
    >
      <div class="absolute inset-0 animate-shimmer">
        <div
          class="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full"
        ></div>
      </div>
    </div>
  </div>
  <p class="text-white text-lg animate-pulse">
    Indexing Your Ableton Project... {loadingProgress}%
  </p>
</div>

<style>
  @keyframes shimmer {
    0% {
      transform: translateX(-100%);
    }
    100% {
      transform: translateX(100%);
    }
  }

  .animate-shimmer {
    animation: shimmer 2s infinite;
  }
</style>
