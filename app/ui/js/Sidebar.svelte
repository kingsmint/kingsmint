<!-- The agent's sidebar, right of the panels: the terminals as tabs (a second Dockview, panels.js). Pinned, it takes
     its width from the panels; floating, it lies over them and hides on a click elsewhere (also into Fava's frame);
     wide, it covers the panels. Its left edge drags its width. Hidden on the start screen and while a ledger opens. -->
<script>
  import { app } from "./app.svelte.js";
  import { saveSoon } from "./panels.js";

  const s = app.sidebar;
  let aside;

  // the state goes with the ledger's layout
  $effect(() => {
    [s.open, s.pinned, s.width];
    saveSoon();
  });

  // floating: a click outside hides it; not the rail's agent button (it toggles) nor a menu of the sidebar's
  $effect(() => {
    const hide = () => !s.pinned && s.open && (s.open = s.wide = false);
    const down = (e) => !aside.contains(e.target) && !e.target.closest("#toggle, #popups") && hide();
    const blur = () => setTimeout(() => document.activeElement?.tagName === "IFRAME" && hide());
    addEventListener("pointerdown", down, true);
    addEventListener("blur", blur);
    return () => {
      removeEventListener("pointerdown", down, true);
      removeEventListener("blur", blur);
    };
  });

  function drag(e) {
    e.preventDefault();
    const right = aside.getBoundingClientRect().right;
    const move = (m) => (s.width = Math.round(Math.min(Math.max(right - m.clientX, 280), innerWidth * 0.7)));
    const up = () => {
      removeEventListener("pointermove", move);
      removeEventListener("pointerup", up);
      document.body.classList.remove("resizing");
    };
    document.body.classList.add("resizing"); // Fava's frame does not take the pointer while the edge moves
    addEventListener("pointermove", move);
    addEventListener("pointerup", up);
  }
</script>

<aside
  id="side"
  bind:this={aside}
  hidden={!s.open || !!app.cover}
  class:floating={!s.pinned}
  class:wide={s.wide}
  style:width={s.wide ? null : `${s.width}px`}
>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="grip" onpointerdown={drag}></div>
  <div id="side-dock"></div>
</aside>
