<script lang="ts">
  import { tweened } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';

  export let confidence: number | null = null;
  export let isAnalyzing: boolean = false;

  let matrixText = '';
  
  const animatedConfidence = tweened(0, { duration: 1500, easing: cubicOut });

  $: if (isAnalyzing) {
    matrixText = 'Simulating 10,000 nodes...';
    animatedConfidence.set(Math.random() * 80 + 10);
  } else if (confidence !== null) {
    matrixText = 'Optimal path found.';
    animatedConfidence.set(confidence);
  } else {
    matrixText = 'Standing by for ignition...';
    animatedConfidence.set(0);
  }

  $: gaugeValue = confidence ?? 0;
  $: colorClass = gaugeValue > 80 ? 'high-confidence' : (gaugeValue > 50 ? 'med-confidence' : 'low-confidence');
</script>

<div class="cognition-gauge" class:analyzing={isAnalyzing}>
  <div class="cg-header">
    <span class="cg-icon">🧠</span>
    <span class="cg-title">THE COGNITION GAUGE</span>
  </div>
  
  <div class="cg-content">
    <div class="cg-status">
      {#if isAnalyzing}
        <span class="matrix-effect">{matrixText}</span>
      {:else}
        <span class="status-text">{matrixText}</span>
      {/if}
    </div>
    
    <div class="cg-confidence">
      <span class="cg-label">CONFIDENCE</span>
      <span class="cg-value {colorClass}">
          {$animatedConfidence.toFixed(1)}%
      </span>
    </div>
    
    <div class="cg-bar-wrap">
      <div class="cg-bar {colorClass}" style="width: {$animatedConfidence}%"></div>
    </div>
  </div>
</div>

<style>
  .cognition-gauge {
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    width: 280px;
    background: rgba(5, 5, 5, 0.85);
    border: 1px solid rgba(34, 211, 238, 0.3);
    border-radius: 8px;
    padding: 1rem;
    backdrop-filter: blur(10px);
    z-index: 1000;
    box-shadow: 0 0 25px rgba(34, 211, 238, 0.15);
    font-family: 'Courier New', Courier, monospace;
    transition: all 0.3s ease;
  }

  .cognition-gauge.analyzing {
    border-color: rgba(239, 68, 68, 0.6);
    box-shadow: 0 0 30px rgba(239, 68, 68, 0.2);
  }

  .cg-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.8rem;
    border-bottom: 1px solid rgba(34, 211, 238, 0.2);
    padding-bottom: 0.4rem;
  }

  .cg-icon { font-size: 1rem; }
  .cg-title {
    font-size: 0.75rem;
    font-weight: 700;
    color: #22d3ee;
    letter-spacing: 0.15em;
  }

  .cg-status {
    font-size: 0.7rem;
    color: #0891b2;
    margin-bottom: 0.8rem;
    min-height: 1.2rem;
  }

  .matrix-effect {
    color: #34d399;
    animation: blink 0.5s infinite alternate;
  }
  
  .status-text {
    color: #22d3ee;
  }

  .cg-confidence {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 0.5rem;
  }

  .cg-label {
    font-size: 0.65rem;
    color: #0891b2;
    letter-spacing: 0.1em;
  }

  .cg-value {
    font-size: 1.5rem;
    font-weight: 900;
    line-height: 1;
    text-shadow: 0 0 10px currentColor;
  }

  .high-confidence { color: #34d399; text-shadow: 0 0 15px rgba(52, 211, 153, 0.6); }
  .med-confidence { color: #facc15; text-shadow: 0 0 15px rgba(250, 204, 21, 0.6); }
  .low-confidence { color: #ef4444; text-shadow: 0 0 15px rgba(239, 68, 68, 0.6); }

  .cg-bar-wrap {
    width: 100%;
    height: 4px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 2px;
    overflow: hidden;
  }

  .cg-bar {
    height: 100%;
    transition: width 0.3s ease, background 0.3s ease;
    box-shadow: 0 0 8px currentColor;
  }

  @keyframes blink {
    0% { opacity: 0.6; }
    100% { opacity: 1; text-shadow: 0 0 10px #34d399; }
  }

  @media (max-width: 640px) {
    .cognition-gauge {
      bottom: 1rem;
      right: 1rem;
      width: 240px;
    }
  }
</style>
