<!-- A ledger in a list: its badge, its folder's name and path. -->
<script>
  import { basename, badgeOf, tilde } from "./ledger.js";

  let { dir, onclick } = $props();
  const b = $derived(badgeOf(dir));
</script>

<button type="button" class="ledger" {onclick}>
  <span class="badge" style:background={b.color}>{b.text}</span>
  <div><b>{basename(dir)}</b><small>{tilde(dir)}</small></div>
</button>
