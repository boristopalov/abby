<script lang="ts">
    let { progress }: { progress: number } = $props();
</script>

<div class="flex items-center gap-3 px-4 py-2 bg-purple-500/10 border-b border-purple-500/20 text-sm">
    <div class="flex items-center gap-2 text-purple-300">
        <svg class="animate-spin h-4 w-4 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
        </svg>
        <span>Indexing your Ableton project... {progress}%</span>
    </div>
    <span class="text-gray-500 text-xs">Chat is available now — responses improve after indexing completes.</span>
</div>
