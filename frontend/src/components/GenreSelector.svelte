<script lang="ts">
  import { setGenre, generateRandomGenre } from "../lib/apiCalls";

  export let availableGenres: string[];
  export let activeGenre: string | null;
  export let isConnected: boolean;

  async function handleRandomGenre() {
    try {
      const newGenre = await generateRandomGenre();
      setGenre(newGenre);
      activeGenre = newGenre;
      availableGenres = [...availableGenres, newGenre];
    } catch (error) {
      console.error("Error generating random genre:", error);
    }
  }
</script>

<div class="border-b border-gray-800 p-3 flex gap-4 w-full items-center">
  <div class="flex flex-wrap gap-2 flex-1 justify-center">
    {#each availableGenres as genre}
      <button
        on:click={() => {
          setGenre(genre);
          activeGenre = genre;
        }}
        class={`px-3 py-1 rounded-full text-xs disabled:cursor-not-allowed transition-colors cursor-pointer ${
          activeGenre === genre
            ? "bg-purple-700/80 text-purple-200"
            : "bg-purple-500/20 text-purple-300 hover:bg-purple-500/30"
        }`}
        disabled={!isConnected}
      >
        {genre}
      </button>
    {/each}
  </div>

  <div class="border-l border-gray-800 pl-4">
    <button
      on:click={handleRandomGenre}
      class="px-2 py-1.5 rounded-sm text-xs font-medium disabled:cursor-not-allowed transition-all duration-300 cursor-pointer bg-gradient-to-r from-indigo-500/20 via-purple-500/20 to-pink-500/20 hover:from-indigo-500/30 hover:via-purple-500/30 hover:to-pink-500/30 text-white border border-white/10 hover:border-white/20 hover:shadow-lg hover:shadow-purple-500/10 hover:-translate-y-0.5 active:translate-y-0"
      disabled={!isConnected}
    >
      <span
        class="bg-gradient-to-r from-indigo-200 via-purple-200 to-pink-200 bg-clip-text"
      >
        🎲 🎲
      </span>
    </button>
  </div>
</div>
