<!-- The rail: the ledger's badge (its menu, and a dot for its check), then, in the order the user drags them to and
     without the ones hidden by right-click (rail.js), Inbox, Overview and its views, the pinned views
     (right-click: rename or unpin; past PINS_ON_RAIL in a "…" menu), Reports (once the ledger has one,
     or while they show), Fava, the agent's sidebar, Settings and History. A button shows its panel, and one that was closed comes back; it is "on" while its panel shows. -->
<script>
  import { app } from "./app.svelte.js";
  import { closeHistory, showHistory } from "./history.js";
  import { t } from "./i18n.js";
  import { badgeOf, basename, closeMenu, showMenu } from "./ledger.js";
  import { moveRail, pane, PINS_ON_RAIL, RAIL_LABELS, railHidden, railKey, railOrder, showView } from "./rail.js";

  const badge = $derived(app.current ? badgeOf(app.current) : { text: "K", color: "" });
  const state = $derived(app.check === null ? "" : app.check === "" ? "ok" : "bad");
  const switchTitle = $derived(
    app.current
      ? `${app.current}\n${app.check === null ? t("checking") : app.check === "" ? t("ledgerOk") : t("problems")}`
      : t("switchLedger"),
  );
  const waiting = $derived(app.waiting.length);
  // a pin's icon: its kind of view's, as railKey names it (a report or an account other than an expense: a star)
  const PIN_ICONS = { txns: "receipt-text", spending: "chart-pie", runway: "hourglass", overview: "star" };
  const pinned = $derived(app.pins.findIndex((p) => JSON.stringify(p.view) === app.overview.view)); // the pin that shows
  // the items that show: not hidden, and not empty
  const items = $derived(
    railOrder().filter(
      (k) =>
        !railHidden().includes(k) &&
        (k !== "pins" || app.pins.length) &&
        (k !== "reports" || app.reports || app.shown.reports),
    ),
  );
  const VIEW_ICONS = { overview: "layout-grid", txns: "receipt-text", spending: "chart-pie", runway: "hourglass" };
  // a drag of a rail item: pointer events, as Tauri's file drop takes HTML5 drags (panels.js)
  let drag = $state(null); // { key, y, moved, over, after }
  function startDrag(e, key) {
    if (e.button !== 0) return;
    drag = { key, y: e.clientY, moved: false };
    const move = (e) => {
      drag.moved ||= Math.abs(e.clientY - drag.y) > 6;
      if (!drag.moved) return;
      const el = [...document.querySelectorAll("#rail .rail-item")].find((el) => {
        const r = el.getBoundingClientRect();
        return e.clientY >= r.top - 3 && e.clientY < r.bottom + 3;
      });
      const r = el?.getBoundingClientRect();
      Object.assign(drag, { over: el?.dataset.rail, after: r && e.clientY > r.top + r.height / 2 });
    };
    const up = () => {
      removeEventListener("pointermove", move);
      removeEventListener("pointerup", up);
      if (drag.moved) {
        // the click that ends a drag does not press the button
        const stop = (e) => e.stopPropagation();
        addEventListener("click", stop, { capture: true, once: true });
        setTimeout(() => removeEventListener("click", stop, true), 0); // no click came: the pointer left the button
        if (drag.over && drag.over !== drag.key) moveRail(drag.key, drag.over, drag.after);
      }
      drag = null;
    };
    addEventListener("pointermove", move);
    addEventListener("pointerup", up);
  }
  const menu = (e, popup) => {
    e.preventDefault();
    e.stopPropagation();
    app.popup = { ...popup, x: e.clientX, y: e.clientY };
  };
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
{#snippet item(key)}
  {#if key === "inbox"}
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
  {:else if key in VIEW_ICONS}
    <button
      id={key === "overview" ? "show-dashboard" : `show-${key}`}
      class="pane"
      class:on={app.shown.overview && app.overview.key === key && pinned < 0}
      title={t(`${key}Rail`)}
      onclick={(e) => showView(key, e.metaKey)}
    >
      <wa-icon name={VIEW_ICONS[key]}></wa-icon>
      <span>{t(RAIL_LABELS[key])}</span>
    </button>
  {:else if key === "pins"}
    {#each app.pins.slice(0, PINS_ON_RAIL) as pin, i (i)}
      <button
        class="pane pin"
        class:on={app.shown.overview && pinned === i}
        title={`${pin.label} (⌘${7 + i}; ${t("pinRail")})`}
        onclick={(e) => showView(pin.view, e.metaKey)}
        oncontextmenu={(e) => menu(e, { kind: "pin", i })}
      >
        <wa-icon name={PIN_ICONS[railKey(pin.view)]}></wa-icon>
        <span>{pin.label}</span>
      </button>
    {/each}
    {#if app.pins.length > PINS_ON_RAIL}
      <button
        id="more-pins"
        class="pane"
        class:on={app.shown.overview && pinned >= PINS_ON_RAIL}
        title={t("morePins")}
        onclick={(e) => menu(e, { kind: "pins" })}
      >
        <wa-icon name="ellipsis"></wa-icon>
      </button>
    {/if}
  {:else if key === "reports"}
    {#if app.reports || app.shown.reports}
      <button id="show-reports" class="pane" class:on={app.shown.reports} title={t("reportsTitle")} onclick={() => pane("reports")}>
        <wa-icon name="chart-column-big"></wa-icon>
        <span>{t("reports")}</span>
      </button>
    {/if}
  {:else if key === "fava"}
    <button id="show-fava" class="pane" class:on={app.shown.fava} title={t("favaTitle")} onclick={() => pane("fava")}>
      <wa-icon name="chart-column"></wa-icon>
      <span>{t("fava")}</span>
    </button>
  {:else if key === "side"}
    <button id="toggle" class="pane" class:on={app.sidebar.open && !app.cover} title={t("agentTitle")} onclick={() => pane("side")}>
      <wa-icon name="square-terminal"></wa-icon>
      <span>{t("agent")}</span>
    </button>
  {/if}
{/snippet}
<!-- a rail item moves when dragged; right-click hides it (pinned views have their own menu) -->
{#each items as key (key)}
  <div
    class="rail-item"
    class:dragged={drag?.moved && drag.key === key}
    class:drop-before={drag?.moved && drag.over === key && !drag.after}
    class:drop-after={drag?.moved && drag.over === key && drag.after}
    data-rail={key}
    role="presentation"
    onpointerdown={(e) => startDrag(e, key)}
    oncontextmenu={(e) => key !== "pins" && menu(e, { kind: "rail", key })}
  >
    {@render item(key)}
  </div>
{/each}
{#if railHidden().length}
  <button id="rail-add" class="pane" title={t("railShow")} onclick={(e) => menu(e, { kind: "rail-add" })}>
    <wa-icon name="plus"></wa-icon>
  </button>
{/if}
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
