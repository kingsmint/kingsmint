<!-- The rail: the ledger's badge (its menu, and a dot for its check), Inbox, Overview, Reports (once the ledger has one,
     or while they show), Fava, the agent's sidebar, Settings and History. A button shows its panel, and one that was closed comes back; it is "on" while its panel shows. -->
<script>
  import { app } from "./app.svelte.js";
  import { closeHistory, showHistory } from "./history.js";
  import { t } from "./i18n.js";
  import { badgeOf, basename, closeMenu, showMenu } from "./ledger.js";
  import { pane, showView } from "./rail.js";

  const badge = $derived(app.current ? badgeOf(app.current) : { text: "K", color: "" });
  const state = $derived(app.check === null ? "" : app.check === "" ? "ok" : "bad");
  const switchTitle = $derived(
    app.current
      ? `${app.current}\n${app.check === null ? t("checking") : app.check === "" ? t("ledgerOk") : t("problems")}`
      : t("switchLedger"),
  );
  const waiting = $derived(app.waiting.length);
</script>

<!-- room for the traffic lights: only macOS hides the title bar (main.rs); elsewhere the system draws it -->
<div id="lights" data-tauri-drag-region style:height={navigator.userAgent.includes("Mac") ? null : "8px"}></div>
<button
  id="switch"
  class:active={app.menuOpen}
  data-state={state}
  title={switchTitle}
  onclick={(e) => {
    e.stopPropagation();
    app.menuOpen ? closeMenu() : showMenu();
  }}
>
  <span id="badge" class="badge" style:background={badge.color}>{badge.text}</span>
  <span id="badge-name"
    ><span id="badge-text">{app.current ? basename(app.current) : t("ledgers")}</span><wa-icon class="chevron" name="chevron-down"></wa-icon></span
  >
</button>
<hr id="rail-line" />
<button
  id="show-inbox"
  class="pane"
  class:on={app.shown.inbox}
  title={waiting ? `${t("inboxTitle")}\n${app.waiting.join("\n")}` : t("inboxTitle")}
  onclick={() => pane("inbox")}
>
  <wa-icon name="inbox"></wa-icon>
  <span>{t("inbox")}</span>{#if waiting}<b id="inbox-badge" class="count">{waiting}</b>{/if}
</button>
{#each [["overview", "layout-grid", "overview"], ["txns", "receipt-text", "transactions"], ["spending", "chart-pie", "expenses"], ["runway", "hourglass", "runway"]] as [key, icon, label] (key)}
  <button
    id={key === "overview" ? "show-dashboard" : `show-${key}`}
    class="pane"
    class:on={app.shown.overview && app.overview.key === key}
    title={t(`${key}Rail`)}
    onclick={(e) => showView(key, e.metaKey)}
  >
    <wa-icon name={icon}></wa-icon>
    <span>{t(label)}</span>
  </button>
{/each}
{#if app.reports || app.shown.reports}
  <button id="show-reports" class="pane" class:on={app.shown.reports} title={t("reportsTitle")} onclick={() => pane("reports")}>
    <wa-icon name="chart-column-big"></wa-icon>
    <span>{t("reports")}</span>
  </button>
{/if}
<button id="show-fava" class="pane" class:on={app.shown.fava} title={t("favaTitle")} onclick={() => pane("fava")}>
  <wa-icon name="chart-column"></wa-icon>
  <span>{t("fava")}</span>
</button>
<button id="toggle" class="pane" class:on={app.sidebar.open && !app.cover} title={t("agentTitle")} onclick={() => pane("side")}>
  <wa-icon name="square-terminal"></wa-icon>
  <span>{t("agent")}</span>
</button>
<button
  id="show-settings"
  class="pane bottom"
  class:on={app.shown.settings}
  title={t("settings")}
  onclick={() => pane("settings")}
>
  <wa-icon name="settings"></wa-icon>
  <span>{t("settings")}</span>
</button>
<button
  id="show-history"
  class:active={app.historyOpen}
  title={t("historyTitle")}
  onclick={(e) => {
    e.stopPropagation();
    app.historyOpen ? closeHistory() : showHistory();
  }}
>
  <wa-icon name="history"></wa-icon>
  <span>{t("history")}</span>
</button>
