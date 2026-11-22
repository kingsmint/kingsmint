<!-- A small chart: bars (a loss red) or a line, of values in time; the last value, the chosen month, full and the
     others fainter. A line spans at least `span` (by default a tenth of its largest value), so a small change of a
     large or a tiny amount stays flat. -->
<script>
  import { FAVA } from "./Chart.svelte";

  let { values, bars = false, span = null } = $props();
  const W = 100;
  const H = 24;
  // bars from 0; a line around its middle, at least `span` high
  const half = $derived(
    Math.max((Math.max(...values) - Math.min(...values)) / 2, (span ?? Math.max(...values.map(Math.abs)) / 10) / 2),
  );
  const mid = $derived((Math.max(...values) + Math.min(...values)) / 2);
  const lo = $derived(bars ? Math.min(0, ...values) : mid - half);
  const hi = $derived(bars ? Math.max(0, ...values) : mid + half);
  const y = (v) => H - ((v - lo) / (hi - lo || 1)) * H;
  const step = $derived(W / values.length);
</script>

<svg class="spark" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">
  {#if bars}
    {#each values as v, i}
      <rect
        x={i * step + step * 0.15}
        width={step * 0.7}
        y={Math.min(y(v), y(0))}
        height={Math.max(Math.abs(y(v) - y(0)), 0.5)}
        fill={v < 0 ? FAVA[3] : FAVA[6]}
        opacity={i === values.length - 1 ? 1 : 0.55}
      />
    {/each}
  {:else if values.length > 1}
    <polyline
      points={values.map((v, i) => `${i * (W / (values.length - 1))},${y(v)}`).join(" ")}
      fill="none"
      stroke={FAVA[0]}
      stroke-width="2"
      vector-effect="non-scaling-stroke"
    />
  {/if}
</svg>
