<!-- A bar or line chart of a query's result: the first column on the x axis, each other numeric column a series. -->
<script>
  import { BarChart, LineChart } from "echarts/charts";
  import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
  import * as echarts from "echarts/core";
  import { CanvasRenderer } from "echarts/renderers";
  import { dark } from "./util.js";

  echarts.use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

  let { type, columns, rows } = $props();
  let el;

  $effect(() => {
    const chart = echarts.init(el, dark.matches ? "dark" : null);
    // numbers come as exact strings (Decimal); a column with a value that is not a number is not a series
    const series = columns.slice(1).flatMap((name, i) => {
      const data = rows.map((r) => Number(r[i + 1]));
      return data.every((v) => !Number.isNaN(v)) ? [{ name, type, data }] : [];
    });
    chart.setOption({
      backgroundColor: "transparent",
      animation: false, // a hidden window pauses requestAnimationFrame, and the bars would stay at zero
      tooltip: { trigger: "axis" },
      legend: { show: series.length > 1 },
      grid: { left: 8, right: 8, top: series.length > 1 ? 32 : 8, bottom: 8, containLabel: true },
      xAxis: { type: "category", data: rows.map((r) => String(r[0])) },
      yAxis: { type: "value" },
      series,
    });
    const resize = new ResizeObserver(() => chart.resize());
    resize.observe(el);
    return () => {
      resize.disconnect();
      chart.dispose();
    };
  });
</script>

<div class="chart" bind:this={el}></div>
