<script lang="ts">
  export let isConnected: boolean;
</script>

<div class="status-pill {isConnected ? 'status-pill--connected' : 'status-pill--disconnected'}">
  <span class="status-dot"></span>
  {isConnected ? "Connected" : "Disconnected"}
</div>

<style>
  .status-pill {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.2rem 0.65rem;
    border-radius: 99px;
    font-family: var(--font-body);
    font-size: 0.73rem;
    border: 1px solid var(--border);
    letter-spacing: 0.01em;
  }

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .status-pill--connected {
    color: var(--sage);
    background: var(--sage-light);
    border-color: rgba(122, 158, 126, 0.3);
  }
  .status-pill--connected .status-dot {
    background: var(--sage);
  }

  .status-pill--disconnected {
    color: #b05050;
    background: rgba(176, 80, 80, 0.10);
    border-color: rgba(176, 80, 80, 0.25);
  }
  .status-pill--disconnected .status-dot {
    background: #b05050;
  }
</style>
