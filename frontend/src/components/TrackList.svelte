<script lang="ts">
  import Track from "./Track.svelte";
  import type { Track as TrackType } from "../types";

  let { tracks, activeGenre } = $props<{
    tracks: TrackType[];
    activeGenre?: string;
  }>();

  let activeTrackId: string | null = null;

  function setActiveTrack(trackId: string) {
    activeTrackId = activeTrackId === trackId ? null : trackId;
  }
</script>

<div class="flex-1 overflow-y-auto px-4 py-2">
  {#each tracks as track (track.id)}
    <button
      type="button"
      class="w-full"
      onclick={() => setActiveTrack(track.id)}
      onkeydown={(e) => e.key === "Enter" && setActiveTrack(track.id)}
    >
      <Track trackName={track.name} devices={track.devices} {activeGenre} />
    </button>
  {/each}
</div>

<style>
  div {
    scrollbar-width: thin;
    scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
  }

  div::-webkit-scrollbar {
    width: 8px;
  }

  div::-webkit-scrollbar-track {
    background: transparent;
  }

  div::-webkit-scrollbar-thumb {
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
  }
</style>
