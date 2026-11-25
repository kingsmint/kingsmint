<!-- A toast's text (toast.js), with one action, such as Undo, which closes it. -->
<script>
  let { text, action = "", act = null, close } = $props();
</script>

<div class="toast-message">
  <span>{text}</span>
  {#if act}
    <wa-button size="small" appearance="filled" onclick={() => (act(), close())}>{action}</wa-button>
  {/if}
</div>
