// The threshold slider of the Trends report: hides the rows without a marked change of at least that many
// percent in the chosen column (the newest by default; a click on a heading picks another), keeping the parents
// of the rows that stay. Both are kept in the address (?min=50&col=2024).
const STEPS = [0, 15, 25, 50, 100, 200, 500];

function apply(slider, col) {
  const min = STEPS[slider.value];
  const label = document.getElementById("km-min-label");
  label.textContent = min ? `≥ ${min} %` : label.dataset.all;
  const heads = [...document.querySelectorAll(".km-trends th[data-col]")];
  const i = Math.max(0, heads.findIndex(h => h.dataset.col === col));
  heads.forEach((h, j) => h.classList.toggle("km-col", j === i));
  const rows = [...document.querySelectorAll(".km-trends tbody tr")];
  const keep = new Set();
  for (const r of rows) {
    const cell = r.cells[i + 1];
    cell.parentElement.querySelectorAll("td").forEach((td, j) => td.classList.toggle("km-col", j === i + 1));
    if (!min || Number(cell.dataset.peak) >= min) {
      const parts = r.dataset.account.split(":");
      parts.forEach((_, k) => keep.add(parts.slice(0, k + 1).join(":")));
    }
  }
  rows.forEach((r, j) => r.classList.toggle("km-hidden", j > 0 && !keep.has(r.dataset.account)));
  const set = url => {
    min ? url.searchParams.set("min", min) : url.searchParams.delete("min");
    i ? url.searchParams.set("col", heads[i].dataset.col) : url.searchParams.delete("col");
    return url;
  };
  history.replaceState(history.state, "", set(new URL(location.href)));
  // the other switches keep them; a column of years means nothing among months, so a switch of view drops it
  for (const a of document.querySelectorAll(".km-controls a")) {
    const to = set(new URL(a.href));
    if (to.searchParams.get("by") !== new URL(location.href).searchParams.get("by")) to.searchParams.delete("col");
    a.href = to;
  }
}

export default {
  onExtensionPageLoad() {
    const slider = document.getElementById("km-min");
    if (!slider) return;
    const args = new URL(location.href).searchParams;
    const min = Number(args.get("min") || 0);
    let col = args.get("col");
    slider.value = Math.max(0, STEPS.findLastIndex(s => s <= min));
    slider.oninput = () => apply(slider, col);
    for (const h of document.querySelectorAll(".km-trends th[data-col]")) {
      h.onclick = () => { col = h.dataset.col; apply(slider, col); };
    }
    apply(slider, col);
  },
};
