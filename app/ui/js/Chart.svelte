<!-- A bar or line chart of a query's result: the first column on the x axis, each other numeric column a series. The
     series take Fava's colors (FAVA), or `colors` in their order; `bySign`: a bar takes the first color when it is 0 or
     more, the second when it is below 0. Numbers are in the app's language; `unit`: Intl.NumberFormat's options that give
     them a unit, e.g. { style: "currency", currency: "EUR" } or { style: "unit", unit: "percent" }. `average`: a dashed
     line at that value; `onselect(i)`: a click on the i-th point or bar. In a bar chart, the columns in `lines` are lines
     on an axis of their own (a running total over the bars), those in `dashed` grey and dashed (the period before); `lineScale`: their axis from their lowest
     value (a balance), not from 0.
     `onrange(i, j)`: a drag across the bars picks the i-th to the j-th, a click elsewhere drops it (null); `range`:
     the bars picked. -->
<script module>
  // Fava's chart colors (colors10 in its charts): d3's hcl(270 + 36 i, 45, 70), here as hex
  export const FAVA = ["#7eaefd", "#c29bee", "#eb8cc6", "#f78a94", "#e5986a", "#beaa57", "#8bb866", "#4bbf90", "#00c0c3", "#17bbec"];
</script>

<script>
  import { BarChart, LineChart } from "echarts/charts";
  import {
    BrushComponent,
    GridComponent,
    LegendComponent,
    MarkLineComponent,
    TooltipComponent,
  } from "echarts/components";
  import * as echarts from "echarts/core";
  import { CanvasRenderer } from "echarts/renderers";
  import { app } from "./app.svelte.js";
  import { dark } from "./util.js";

  echarts.use([
    BarChart,
    LineChart,
    BrushComponent,
    GridComponent,
    LegendComponent,
    MarkLineComponent,
    TooltipComponent,
    CanvasRenderer,
  ]);

  let {
    type,
    columns,
    rows,
    colors = FAVA,
    bySign = false,
    unit = {},
    average = null,
    onselect = null,
    lines = [],
    dashed = [],
    onrange = null,
    range = null,
    lineScale = false,
  } = $props();
  let el;

  $effect(() => {
    const chart = echarts.init(el, dark.matches ? "dark" : null);
    const compact = new Intl.NumberFormat(app.lang, { ...unit, notation: "compact" });
    const exact = new Intl.NumberFormat(app.lang, { ...unit, maximumFractionDigits: 2 });
    // numbers come as exact strings (Decimal); a column with a value that is not a number is not a series
    const series = columns.slice(1).flatMap((name, i) => {
      const data = rows.map((r) => (r[i + 1] == null ? null : Number(r[i + 1])));
      if (type === "bar" && lines.includes(name)) {
        const grey = dashed.includes(name);
        const color = grey ? "#999" : FAVA[1];
        const style = { color, type: grey ? "dashed" : "solid", width: grey ? 1 : 2 };
        return [{ name, type: "line", yAxisIndex: 1, data, symbol: "none", color, lineStyle: style, z: grey ? 2 : 3 }];
      }
      const sign = bySign ? { itemStyle: { color: (p) => colors[p.value < 0 ? 1 : 0] } } : {};
      const mark =
        average != null && i === 0
          ? { markLine: { silent: true, symbol: "none", data: [{ yAxis: average }], lineStyle: { type: "dashed" }, label: { show: false } } }
          : {};
      return data.every((v) => !Number.isNaN(v)) ? [{ name, type, data, ...sign, ...mark }] : [];
    });
    const axis = (o) => ({ type: "value", axisLabel: { formatter: (v) => compact.format(v) }, ...o });
    chart.setOption({
      backgroundColor: "transparent",
      color: colors,
      animation: false, // a hidden window pauses requestAnimationFrame, and the bars would stay at zero
      tooltip: { trigger: "axis", valueFormatter: (v) => exact.format(v) },
      legend: { show: series.length > 1, top: 0 },
      grid: { left: 8, right: 8, top: series.length > 1 ? 32 : 8, bottom: 8, containLabel: true },
      xAxis: { type: "category", data: rows.map((r) => String(r[0])) },
      // a line from its lowest value, so a balance's change shows; bars from 0
      yAxis: [
        axis({ scale: type === "line" }),
        ...(lines.length ? [axis({ scale: lineScale, splitLine: { show: false } })] : []),
      ],
      ...(onrange && {
        // the shaded area shows the pick: ECharts fades the wrong bars on a category axis
        brush: { xAxisIndex: 0, brushType: "lineX", brushMode: "single", outOfBrush: { colorAlpha: 1 } },
      }),
      series,
    });
    if (onrange) {
      chart.dispatchAction({ type: "takeGlobalCursor", key: "brush", brushOption: { brushType: "lineX", brushMode: "single" } });
      if (range) chart.dispatchAction({ type: "brush", areas: [{ brushType: "lineX", xAxisIndex: 0, coordRange: range }] });
      chart.on("brushEnd", (e) => {
        const r = e.areas[0]?.coordRange;
        onrange(...(r ? [Math.max(0, Math.round(r[0])), Math.min(rows.length - 1, Math.round(r[1]))] : [null]));
      });
    }
    if (onselect) chart.on("click", (p) => onselect(p.dataIndex));
    const resize = new ResizeObserver(() => chart.resize());
    resize.observe(el);
    return () => {
      resize.disconnect();
      chart.dispose();
    };
  });
</script>

<div class="chart" bind:this={el}></div>
