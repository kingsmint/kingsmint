<!-- The rail: the ledger's badge (its menu, and a dot for its check), Inbox, Reports, Fava, the agent, Settings and
     History. A button shows its panel, and one that was closed comes back; it is "on" while its panel shows. -->
<script>
  import { app } from "./app.svelte.js";
  import { closeHistory, showHistory } from "./history.js";
  import { t } from "./i18n.js";
  import { badgeOf, basename, closeMenu, showMenu } from "./ledger.js";
  import { pane } from "./rail.js";

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
    ><span id="badge-text">{app.current ? basename(app.current) : t("ledgers")}</span><svg
      class="chevron"
      viewBox="0 0 10 10"><path d="M2 3.5l3 3 3-3" /></svg
    ></span
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
  <svg viewBox="0 0 24 24">
    <path
      d="M4 13l2.2-7.4A1.5 1.5 0 0 1 7.6 4.5h8.8a1.5 1.5 0 0 1 1.4 1.1L20 13v5.5A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5zM4 13h4.5l1.5 2.5h4l1.5-2.5H20"
    />
  </svg>
  <span>{t("inbox")}</span>{#if waiting}<b id="inbox-badge" class="count">{waiting}</b>{/if}
</button>
<button id="show-reports" class="pane" class:on={app.shown.reports} title={t("reportsTitle")} onclick={() => pane("reports")}>
  <svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="1.5" /><path d="M8 16v-4M12 16V8M16 16v-6" /></svg>
  <span>{t("reports")}</span>
</button>
<button id="show-fava" class="pane" class:on={app.shown.fava} title={t("favaTitle")} onclick={() => pane("fava")}>
  <svg viewBox="0 0 24 24"><path d="M4 20V4M4 20h16M8 16v-5M12 16V8M16 16v-3" /></svg>
  <span>{t("fava")}</span>
</button>
<button id="toggle" class="pane" class:on={app.shown.side} title={t("agentTitle")} onclick={() => pane("side")}>
  <svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="1.5" /><path d="M7 10l3 2-3 2M12 15h5" /></svg>
  <span>{t("agent")}</span>
</button>
<button
  id="show-settings"
  class="pane bottom"
  class:on={app.shown.settings}
  title={t("settings")}
  onclick={() => pane("settings")}
>
  <svg viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1" />
  </svg>
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
  <svg viewBox="0 0 24 24"><path d="M3.5 12a8.5 8.5 0 1 0 2.5-6M3.5 4v4h4M12 7.5V12l3 2" /></svg>
  <span>{t("history")}</span>
</button>
