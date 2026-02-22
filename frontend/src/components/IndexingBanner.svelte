<script lang="ts">
    let { progress }: { progress: number } = $props();
</script>

<div class="indexing-banner">
    <div class="indexing-left">
        <svg class="indexing-spinner" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
        </svg>
        <span>Indexing project… <strong>{progress}%</strong></span>
    </div>
    <span class="indexing-note">Chat is available — responses improve after indexing completes.</span>
</div>

<style>
    .indexing-banner {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        padding: 0.5rem 1.25rem;
        background: var(--sage-light);
        border-bottom: 1px solid rgba(122, 158, 126, 0.2);
        flex-shrink: 0;
    }

    .indexing-left {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-family: var(--font-body);
        font-size: 0.84rem;
        color: var(--sage);
    }
    .indexing-left strong { font-weight: 600; }

    .indexing-spinner {
        width: 1rem;
        height: 1rem;
        animation: spin 1s linear infinite;
        flex-shrink: 0;
    }
    @keyframes spin {
        from { transform: rotate(0deg); }
        to   { transform: rotate(360deg); }
    }

    .indexing-note {
        font-family: var(--font-body);
        font-size: 0.73rem;
        color: var(--ink-3);
        font-style: italic;
    }
</style>
