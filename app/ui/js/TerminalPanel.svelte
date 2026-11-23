<!-- The content of a terminal panel: xterm.js on a PTY of the app (terminal.js). Closing the panel ends its program. -->
<script>
  import { untrack } from "svelte";
  import { closeTab, makeTab } from "./terminal.js";

  let { api, params } = $props();
  let el;

  // once: makeTab reads the app's state (the font size), which must not start the terminal again when it changes
  $effect(() => {
    const tab = untrack(() => makeTab(api, params ?? {}, el));
    return () => closeTab(tab);
  });
</script>

<div class="term" bind:this={el}></div>
