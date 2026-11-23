<!-- The reports of the ledger (reports/*.toml: name, BQL query, view): a list, and the chosen report as a chart and a
     table. They load again after the ledger's files change (ledger-changed), so an agent's new report or a new import
     shows at once. -->
<script>
  import { app } from "./app.svelte.js";
  import Chart from "./Chart.svelte";
  import { t } from "./i18n.js";
  import { listen, rpc } from "./util.js";

  let reports = $state([]);
  let chosen = $state(null); // the file of the report on the right
  let result = $state(null); // { columns, rows }, or { error }
  const report = $derived(reports.find((r) => r.file === chosen));
  const numeric = (v) => typeof v === "string" && /^-?\d+(\.\d+)?$/.test(v);

  async function run() {
    const r = reports.find((r) => r.file === chosen);
    if (!r || r.error) return (result = r?.error ? { error: r.error } : null);
    result = await rpc("query", { bql: r.query }).catch((e) => ({ error: String(e) }));
  }

  async function load() {
    try {
      reports = await rpc("reports");
      app.reports = reports.length;
    } catch {
      return; // no ledger's server yet: the start screen
    }
    if (!reports.some((r) => r.file === chosen)) chosen = reports[0]?.file ?? null;
    await run();
  }

  $effect(() => {
    load();
    const off = listen("ledger-changed", load);
    document.addEventListener("km-ledger", load);
    return () => {
      off.then((unlisten) => unlisten());
      document.removeEventListener("km-ledger", load);
    };
  });
</script>

<div class="reports">
  <nav>
    <h2>{t("reports")}</h2>
    {#each reports as r (r.file)}
      <button
        type="button"
        class:on={r.file === chosen}
        class:broken={r.error}
        onclick={() => {
          chosen = r.file;
          run();
        }}>{r.name ?? r.file}</button
      >
    {:else}
      <p class="muted">{t("noReports")}</p>
    {/each}
  </nav>
  <section>
    {#if report}
      <h1>{report.name ?? report.file}</h1>
      {#if result?.error}
        <p class="error">{result.error}</p>
      {:else if result}
        {#if report.view === "bar" || report.view === "line"}
          <Chart type={report.view} columns={result.columns} rows={result.rows} />
        {/if}
        <table>
          <thead>
            <tr>
              {#each result.columns as c}<th>{c}</th>{/each}
            </tr>
          </thead>
          <tbody>
            {#each result.rows as row}
              <tr>
                {#each row as v}<td class:num={numeric(v)}>{v ?? ""}</td>{/each}
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    {/if}
  </section>
</div>
