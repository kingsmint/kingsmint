<!-- A cash payment (server/edit.py add_cash): written to cash.beancount, where it moves the amount from Expenses:Cash
     to its category; a receipt goes to documents/. The receipt comes from a file, a paste (⌘V), or the iPhone's camera:
     on a Mac, a right click in its field offers "Import from iPhone" (Continuity Camera), which pastes a photo or a
     scan there. A photo is made smaller here (a phone's photo has megabytes; the ledger keeps each in its versions). -->
<script>
  import { tick } from "svelte";
  import CategoryPicker from "./CategoryPicker.svelte";
  import { t } from "./i18n.js";
  import { invoke, rpc } from "./util.js";

  // accounts: the open accounts to pick from; done(r): after a save, what rpc("cash_save") gave and the payment's
  // date; after a cancel, null
  let { accounts, done } = $props();

  const today = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  let date = $state(today);
  let amount = $state(null);
  let account = $state("");
  let payee = $state("");
  let receipt = $state(null); // {name, blob}: the file as it will be saved
  let reading = $state(false);
  let zone = $state(); // the field a receipt is pasted into
  let fileInput = $state();
  let picking = $state(false);
  let payeeInput;
  let busy = $state(false);
  let error = $state("");
  const categories = $derived(accounts.filter((a) => a.startsWith("Expenses:") && a !== "Expenses:Cash"));
  const bad = $derived(/["\\]/.test(payee) ? t("cashPayeeChars") : "");
  const ok = $derived(date && Number(amount) > 0 && account && payee.trim() && !bad);

  const SIDE = 2000; // px of a photo's longer side: the text of a receipt stays sharp
  const MAX = 10 * 1024 * 1024; // as the server takes (edit.RECEIPT_MAX)
  // a photo as a JPEG with its longer side at most SIDE; `img`: a loaded image
  function smaller(img) {
    const k = Math.min(1, SIDE / Math.max(img.naturalWidth, img.naturalHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.naturalWidth * k);
    canvas.height = Math.round(img.naturalHeight * k);
    canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
    return new Promise((done) => canvas.toBlob(done, "image/jpeg", 0.8));
  }
  // a file, pasted or chosen: a PDF as it is, an image made smaller (HEIC too, where WebKit reads it)
  async function take(file) {
    error = "";
    reading = true;
    try {
      if (file.type === "application/pdf" || /\.pdf$/i.test(file.name)) {
        if (file.size > MAX) throw new Error(t("cashReceiptBig"));
        receipt = { name: "receipt.pdf", blob: file };
      } else {
        const url = URL.createObjectURL(file);
        const img = new Image();
        img.src = url;
        try {
          await img.decode();
          receipt = { name: "receipt.jpg", blob: await smaller(img) };
        } catch {
          throw new Error(t("cashReceiptUnreadable"));
        } finally {
          URL.revokeObjectURL(url);
        }
      }
    } catch (e) {
      error = e.message;
    }
    reading = false;
  }
  function pasted(e) {
    const file = [...(e.clipboardData?.files ?? [])][0];
    invoke("log", { message: `cash receipt paste: ${[...(e.clipboardData?.types ?? [])].join(", ")}` });
    if (!file) return; // what WebKit inserts instead goes to inserted()
    e.preventDefault();
    take(file);
  }
  // Continuity Camera may insert the photo as an image into the field, not as a paste event: its image, made smaller
  async function inserted() {
    invoke("log", { message: `cash receipt inserted: ${zone.innerHTML.slice(0, 300)}` });
    const img = zone.querySelector("img");
    zone.textContent = "";
    if (!img) return;
    try {
      const blob = await fetch(img.src).then((r) => r.blob());
      return take(new File([blob], "receipt", { type: blob.type }));
    } catch {} // a source the page cannot fetch: the image WebKit drew already
    try {
      if (!img.complete) await img.decode();
      receipt = { name: "receipt.jpg", blob: await smaller(img) };
    } catch (e) {
      invoke("log", { message: `cash receipt: ${e}` });
      error = t("cashReceiptUnreadable");
    }
  }
  const base64 = (blob) =>
    new Promise((done, fail) => {
      const reader = new FileReader();
      reader.onload = () => done(reader.result.split(",")[1]);
      reader.onerror = () => fail(reader.error);
      reader.readAsDataURL(blob);
    });
  async function submit() {
    busy = true;
    const r = await (async () => {
      const file = receipt && { name: receipt.name, data: await base64(receipt.blob) };
      return rpc("cash_save", { date, amount: String(amount), account, payee, receipt: file });
    })().catch((e) => ({ error: String(e) }));
    busy = false;
    // an error of the version leaves the payment written: the page says so, the form closes
    if (r.saved) done({ ...r, date });
    else error = r.error;
  }
  const focus = (el) => el.focus();
  // a category picked: on to the payee, as a form goes on by the keyboard
  async function pick(a) {
    account = a;
    picking = false;
    await tick();
    payeeInput.focus();
  }
</script>

<!-- a row of fields as the transactions' columns, then the receipt and the buttons -->
<section class="cash-entry">
  <h2>{t("cashNew")}</h2>
  <div class="fields">
    <label class="date"><span>{t("cashDate")}</span><input type="date" bind:value={date} max={today} /></label>
    <label class="amount">
      <span>{t("amount")}</span><input type="number" min="0.01" step="0.01" bind:value={amount} use:focus />
    </label>
    <div class="category">
      <span>{t("category")}</span>
      {#if picking}
        <CategoryPicker accounts={categories} value={account} {pick} cancel={() => (picking = false)} />
      {:else}
        <!-- a field, not a button: WebKit's Tab skips buttons (unless the Mac's settings say otherwise) -->
        <input type="text" class="cat" readonly value={account} placeholder={t("pickCategory")}
          onfocus={() => (picking = true)} onclick={() => (picking = true)} />
      {/if}
    </div>
    <label class="payee">
      <span>{t("payee")}</span>
      <input type="text" bind:this={payeeInput} bind:value={payee} placeholder={t("cashPayeeHint")}
        onkeydown={(e) => e.key === "Enter" && ok && !busy && submit()} />
    </label>
  </div>
  <div class="foot">
    <div class="receipt">
      <span>{t("cashReceipt")}</span>
      {#if receipt}
        <span class="file">
          {receipt.name.endsWith(".pdf") ? "PDF" : "JPEG"}, {Math.ceil(receipt.blob.size / 1024)} kB
          <button type="button" class="more" title={t("cashReceiptRemove")} onclick={() => (receipt = null)}>×</button>
        </span>
      {:else if reading}
        <span class="muted">{t("loading")}</span>
      {:else}
        <div class="drop" contenteditable="true" role="textbox" tabindex="0" aria-label={t("cashReceipt")}
          data-hint={t("cashReceiptHint")} bind:this={zone} onpaste={pasted} oninput={inserted}></div>
        <button type="button" class="more" onclick={() => fileInput.click()}>{t("cashReceiptAdd")}</button>
        <input type="file" hidden accept=".pdf,image/*" bind:this={fileInput}
          onchange={(e) => e.target.files[0] && take(e.target.files[0])} />
      {/if}
    </div>
    <div class="buttons">
      <wa-button size="small" appearance="filled" onclick={() => done(null)}>{t("cancel")}</wa-button>
      <wa-button size="small" variant="brand" disabled={busy || reading || !ok} onclick={submit}>{t("save")}</wa-button>
    </div>
  </div>
  {#if bad || error}<p class="error">{bad || error}</p>{/if}
</section>
