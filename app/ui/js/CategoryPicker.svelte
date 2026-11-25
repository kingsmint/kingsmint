<!-- Picks an account by typing: the words in any order, without accents ("potr jedl" finds Expenses:Food:Groceries
     when it is named so). Empty, it offers the payee's categories, then the ones picked last. ↑ ↓ move, Enter picks,
     Esc or a click elsewhere closes. -->
<script module>
  const recent = []; // the accounts picked in this session, the last first
</script>

<script>
  import { t } from "./i18n.js";

  let { accounts, suggested = [], value = "", pick, cancel } = $props();
  let query = $state("");
  let at = $state(0);
  let input;

  const norm = (s) => s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
  const categories = $derived(accounts.filter((a) => /^(Expenses|Income):/.test(a)));
  const list = $derived.by(() => {
    const words = norm(query).split(/\s+/).filter(Boolean);
    if (!words.length) return [...new Set([...suggested, ...recent, ...categories])].filter((a) => a !== value).slice(0, 8);
    const last = (a) => norm(a.split(":").at(-1));
    return accounts
      .filter((a) => words.every((w) => norm(a).includes(w)))
      .sort((x, y) => last(y).startsWith(words[0]) - last(x).startsWith(words[0]) || x.localeCompare(y))
      .slice(0, 8);
  });
  $effect(() => {
    list;
    at = 0;
  });
  $effect(() => input.focus());

  function choose(a) {
    if (recent.includes(a)) recent.splice(recent.indexOf(a), 1);
    recent.unshift(a);
    pick(a);
  }
  function key(e) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      at = (at + (e.key === "ArrowDown" ? 1 : list.length - 1)) % Math.max(list.length, 1);
    } else if (e.key === "Enter" && list[at]) {
      e.preventDefault();
      choose(list[at]);
    } else if (e.key === "Escape") {
      e.stopPropagation(); // not the overview's Esc, which goes one level up
      cancel();
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="picker" onclick={(e) => e.stopPropagation()}>
  <input
    bind:this={input}
    bind:value={query}
    type="text"
    placeholder={value || t("pickCategory")}
    aria-label={t("pickCategory")}
    onkeydown={key}
    onblur={cancel}
  />
  <ul role="listbox">
    {#each list as a, i (a)}
      <li role="option" aria-selected={i === at} class:on={i === at} onmousedown={(e) => (e.preventDefault(), choose(a))}>
        <b>{a.split(":").at(-1)}</b> <span class="muted">{a}</span>
      </li>
    {:else}
      <li class="muted">{t("noAccount")}</li>
    {/each}
  </ul>
</div>
