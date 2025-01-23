<script lang="ts">
  import { onMount } from "svelte";
  import { setGenre, generateRandomGenre, fetchGenres } from "../lib/apiCalls";
  import { genres } from "../lib/state.svelte";

  let { isConnected } = $props<{
    isConnected: boolean;
  }>();

  async function handleRandomGenre() {
    try {
      const newGenre = await generateRandomGenre();
      await setGenre(newGenre);
      genres.availableGenres.push(newGenre);
      genres.activeGenre = newGenre;
    } catch (error) {
      console.error("Error generating random genre:", error);
    }
  }

  onMount(async () => {
    const genreResponse = await fetchGenres();
    genres.availableGenres = genreResponse.genres;
    genres.activeGenre =
      genreResponse.defaultGenre || genreResponse.currentGenre || "";
  });
</script>

<div class="border-b border-gray-800 p-3 flex gap-4 w-full items-center">
  <div class="flex flex-wrap gap-2 flex-1 justify-center">
    {#each genres.availableGenres as genre}
      <button
        onclick={async () => {
          try {
            await setGenre(genre);
          } catch (e) {
            console.error(e);
          }
          genres.activeGenre = genre;
        }}
        class={`px-3 py-1 rounded-full text-xs disabled:cursor-not-allowed  cursor-pointer ${
          genres.activeGenre === genre
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
      onclick={handleRandomGenre}
      class="px-2 py-1.5 rounded-sm text-xs font-medium disabled:cursor-not-allowed cursor-pointer bg-gradient-to-r from-indigo-500/20 via-purple-500/20 to-pink-500/20 hover:from-indigo-500/30 hover:via-purple-500/30 hover:to-pink-500/30 text-white border border-white/10 hover:border-white/20 hover:shadow-lg hover:shadow-purple-500/10"
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
