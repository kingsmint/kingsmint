<!-- Tags as chips (wa-tag), and a field that adds one: Enter adds what was typed, the ledger's tags are suggested (a datalist).
     × removes a tag; a click on its name opens it (`open`). The server turns what was typed into a tag Beancount
     takes (edit.tag_slug: "Záloha plot" -> zaloha-plot). -->
<script>
  import { t } from "./i18n.js";

  let { tags = [], known = [], add, remove, open = null, disabled = false } = $props();
  const list = `tags-${Math.random().toString(36).slice(2)}`; // the datalist's id, one per field
  let text = $state("");

  function submit() {
    add(text.trim());
    text = "";
  }
  function key(e) {
    if (e.key === "Enter" && text.trim()) {
      e.preventDefault();
      submit();
    } else if (e.key === "Escape") {
      e.stopPropagation(); // not the overview's Esc, which goes one level up
      text = "";
    }
  }
</script>

<span class="tags">
  {#each tags as tag (tag)}
    <!-- Web Awesome's chip, the one wa-tag-input draws: wa-tag-input has no suggestions and no click on a tag -->
    <wa-tag size="small" pill with-remove={remove && !disabled ? true : undefined} onwa-remove={() => remove(tag)}>
      {#if open}
        <button type="button" class="name" title={t("openTag")} onclick={() => open(tag)}>#{tag}</button>
      {:else}#{tag}{/if}
    </wa-tag>
  {/each}
  {#if add}
    <input type="text" list={list} placeholder={t("addTag")} aria-label={t("addTag")} bind:value={text} {disabled}
      onkeydown={key} />
    <wa-button size="small" appearance="filled" pill disabled={disabled || !text.trim()} onclick={submit}>{t("add")}</wa-button>
    <datalist id={list}>
      {#each known.filter((k) => !tags.includes(k)) as k}<option value={k}></option>{/each}
    </datalist>
  {/if}
</span>

<style>
  .tags {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4em;
    margin-bottom: 0.75em;
  }
  .name {
    padding: 0;
    border: 0;
    background: none;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  input {
    width: 10em;
    padding: 0.2em 0.6em;
    border: 1px solid var(--wa-color-surface-border);
    border-radius: 999px;
    background: none;
    color: inherit;
    font: inherit;
  }
</style>
