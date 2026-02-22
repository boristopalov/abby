<script lang="ts">
import { slide } from "svelte/transition";
import type { ParameterChange } from "../types";

  export let parameterChanges: ParameterChange[];
  export let showParameterPanel: boolean;
  export let onToggle: () => void;
</script>

{#if showParameterPanel}
  <aside
    class="param-panel"
    in:slide={{ axis: "x" }}
    out:slide={{ axis: "x" }}
  >
    <div class="param-header">
      <h2 class="param-title">Changes</h2>
    </div>
    <div class="param-list">
      {#each parameterChanges as change}
        <div class="param-change">
          <div class="param-location">{change.trackName} / {change.deviceName}</div>
          <div class="param-name">{change.paramName}</div>
          <div class="param-values">
            <span class="param-val">{change.oldValue.toFixed(2)}</span>
            <span class="param-arrow">→</span>
            <span class="param-val param-val--new">{change.newValue.toFixed(2)}</span>
          </div>
          <div class="param-time">{new Date(change.timestamp).toLocaleTimeString()}</div>
        </div>
      {/each}
    </div>
  </aside>
{/if}

<button
  on:click={onToggle}
  class="panel-toggle"
  aria-label={showParameterPanel ? "hide parameter changes" : "show parameter changes"}
>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    class="h-4 w-4"
    viewBox="0 0 20 20"
    fill="currentColor"
  >
    <path
      fill-rule="evenodd"
      d={showParameterPanel
        ? "M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
        : "M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"}
      clip-rule="evenodd"
    />
  </svg>
</button>

<style>
  /* ── Panel ── */
  .param-panel {
    width: 216px;
    flex-shrink: 0;
    border-left: 1px solid var(--border);
    background: var(--surface);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .param-header {
    padding: 0.875rem 1rem;
    border-bottom: 1px solid var(--border-light);
    flex-shrink: 0;
  }

  .param-title {
    font-family: var(--font-serif);
    font-size: 0.8rem;
    font-weight: 400;
    font-style: italic;
    color: var(--ink-2);
    margin: 0;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  /* ── Change entries — marginalia style ── */
  .param-list {
    flex: 1;
    overflow-y: auto;
    padding: 0.25rem 0;
  }

  .param-change {
    border-left: 2px solid transparent;
    padding: 0.575rem 0.875rem 0.575rem 0.75rem;
    position: relative;
    transition: border-color 0.15s;
  }
  .param-change:not(:last-child)::after {
    content: '';
    display: block;
    position: absolute;
    bottom: 0;
    left: 0.875rem;
    right: 0.875rem;
    height: 1px;
    background: var(--border-light);
  }
  .param-change:hover {
    border-left-color: var(--accent);
  }

  .param-location {
    font-size: 0.66rem;
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.2rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .param-name {
    font-family: var(--font-body);
    font-size: 0.8rem;
    color: var(--ink);
    margin-bottom: 0.3rem;
    line-height: 1.3;
  }

  .param-values {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    margin-bottom: 0.25rem;
  }

  .param-val {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--ink-2);
    background: var(--bg);
    border: 1px solid var(--border-light);
    border-radius: 3px;
    padding: 0.05rem 0.3rem;
  }
  .param-val--new {
    color: var(--accent);
    border-color: rgba(196, 113, 74, 0.25);
  }

  .param-arrow {
    font-size: 0.62rem;
    color: var(--ink-3);
  }

  .param-time {
    font-family: var(--font-mono);
    font-size: 0.63rem;
    color: var(--ink-3);
  }

  /* ── Toggle tab on right edge ── */
  .panel-toggle {
    position: fixed;
    right: 0;
    top: 50%;
    transform: translateY(-50%);
    background: var(--surface);
    border: 1px solid var(--border);
    border-right: none;
    border-radius: var(--radius) 0 0 var(--radius);
    padding: 0.5rem 0.35rem;
    color: var(--ink-3);
    cursor: pointer;
    transition: color 0.15s, background 0.15s;
    box-shadow: var(--shadow-sm);
  }
  .panel-toggle:hover {
    color: var(--accent);
    background: var(--bg);
  }
</style>
