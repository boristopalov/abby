<script lang="ts">
  export let loadingProgress: number;
</script>

<div class="loading-screen">
  <div class="loading-card">
    <h2 class="loading-heading">Abby</h2>
    <p class="loading-sub">Indexing your Ableton project…</p>
    <div class="progress-track">
      <div class="progress-fill" style="width: {loadingProgress}%"></div>
    </div>
    <p class="loading-pct">{loadingProgress}%</p>
  </div>
</div>

<style>
  .loading-screen {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    padding: 2rem;
    background: var(--bg);
  }

  .loading-card {
    width: 100%;
    max-width: 360px;
    text-align: center;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .loading-heading {
    font-family: var(--font-serif);
    font-size: 2.2rem;
    font-weight: 600;
    color: var(--ink);
    margin: 0 0 0.25rem;
    letter-spacing: 0.02em;
  }

  .loading-sub {
    font-family: var(--font-body);
    font-size: 0.9rem;
    color: var(--ink-2);
    margin: 0;
    font-style: italic;
  }

  .progress-track {
    width: 100%;
    height: 3px;
    background: var(--border);
    border-radius: 99px;
    overflow: hidden;
    margin-top: 0.25rem;
  }

  .progress-fill {
    height: 100%;
    background: var(--accent);
    border-radius: 99px;
    transition: width 0.3s ease;
  }

  .loading-pct {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: var(--ink-3);
    margin: 0;
  }
</style>
