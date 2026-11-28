// A task for the agent. A new agent tab gets it once the agent has started (its output went quiet), so the
// text is not lost while it loads. The Enter goes separately: an agent reads the text as typed, not as a paste.
// tasks for the agent, in the ledger's language: [task, the command in a shell without an agent, version name before]

import { app } from "./app.svelte.js";
import { tAgent } from "./i18n.js";
import { active, tabs } from "./state.js";
import { addTab, agentNote, asksTrust, defaultProfile, send, showTab } from "./terminal.js";
import { rpc } from "./util.js";

export const ACTIONS = {
  setup: () => [tAgent("setup") + tAgent("save"), "kingsmint import", tAgent("beforeSetup")],
  import: () => [tAgent("import") + tAgent("save"), "kingsmint import", tAgent("beforeImport")],
  fix: () => [tAgent("fix") + tAgent("save"), "kingsmint check", tAgent("beforeFix")],
  upgrade: () => [tAgent("upgrade"), "kingsmint upgrade", tAgent("beforeUpgrade")],
  close: () => {
    const month = lastMonth(app.ledgerLang);
    return [tAgent("close", { month }) + tAgent("save"), "kingsmint coverage", tAgent("beforeClose", { month })];
  },
};
// the last full calendar month, as "October 2026"
export const lastMonth = (l) =>
  new Intl.DateTimeFormat(l, { month: "long", year: "numeric" }).format(
    new Date(new Date().getFullYear(), new Date().getMonth(), 0),
  );
export const ask = (act) => tell(...ACTIONS[act]());
// Sends a whole message to an agent tab (or `command` to a shell when no agent is installed). The app writes the
// message, so a click is one complete message; before it, a version to return to.
export async function tell(task, command, before) {
  await rpc("versions_save", { message: before }).catch(() => {}); // a point to return to
  // the agent tab in view, else one of the profile for this ledger, else a new one of it
  const profile = defaultProfile();
  let tab = active?.agent ? active : tabs.find((t) => t.agent && t.profile === profile);
  if (!tab && profile) tab = addTab({ profile });
  tab ??= tabs.find((t) => t.agent) ?? active ?? addTab({ agent: "" }); // no agent: the command in a shell
  await showTab(tab);
  for (let i = 0; i < 100 && (!tab.last || Date.now() - tab.last < 1000); i++)
    await new Promise((r) => setTimeout(r, 200));
  if (!tab.session || (!tab.agent && !command)) return;
  if (asksTrust(tab)) return agentNote(); // the user answers it first; then the button again
  await send(tab, tab.agent ? task : command);
  setTimeout(() => send(tab, "\r"), 150);
  tab.term.focus();
}
