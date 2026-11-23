// Terminals: xterm.js on a PTY of the app, with an agent or a shell; their colors, the agents' questions, the "+" menu.

import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { Terminal } from "@xterm/xterm";
import { app } from "./app.svelte.js";
import { firstFava, openLink } from "./fava.js";
import { t } from "./i18n.js";
import { active, assign, dock, restoring, tabs } from "./state.js";
import { dark, invoke, listen } from "./util.js";
import { fontSize } from "./zoom.js";

// ANSI colors readable on the light and the dark surface; the background, text and selection come from the tokens
export const THEMES = {
  light: {
    black: "#404040",
    red: "#c4161c",
    green: "#2e7d32",
    yellow: "#946300",
    blue: "#0065a3",
    magenta: "#8e3fa6",
    cyan: "#00796b",
    white: "#a6a6a6",
    brightBlack: "#666666",
    brightRed: "#e53935",
    brightGreen: "#43a047",
    brightYellow: "#b07800",
    brightBlue: "#009dff",
    brightMagenta: "#ab47bc",
    brightCyan: "#00897b",
    brightWhite: "#d9d9d9",
  },
  dark: {
    black: "#404040",
    red: "#ef5350",
    green: "#81c784",
    yellow: "#ffd54f",
    blue: "#5cc0ff",
    magenta: "#ce93d8",
    cyan: "#4dd0e1",
    white: "#cccccc",
    brightBlack: "#808080",
    brightRed: "#ff7961",
    brightGreen: "#a5d6a7",
    brightYellow: "#ffe082",
    brightBlue: "#90d5ff",
    brightMagenta: "#e1bee7",
    brightCyan: "#80deea",
    brightWhite: "#ffffff",
  },
};
export function theme() {
  const css = getComputedStyle(document.documentElement),
    token = (name) => css.getPropertyValue(`--wa-color-${name}`).trim();
  return {
    ...THEMES[dark.matches ? "dark" : "light"],
    background: token("surface-default"),
    foreground: token("text-normal"),
    cursor: token("text-normal"),
    cursorAccent: token("surface-default"),
    selectionBackground: token("brand-fill-quiet"),
  };
}
export const FONT = getComputedStyle(document.documentElement).getPropertyValue("--wa-font-family-code");

export function freeName(base) {
  const taken = new Set(tabs.map((t) => t.api.title));
  let name = base,
    n = 2;
  while (taken.has(name)) name = `${base} ${n++}`;
  return name;
}

export function makeTab(api, { agent = "", claude = null }, el) {
  // linkHandler: links the program marks (OSC 8); without it xterm.js asks with confirm() and opens a new window
  const term = new Terminal({
    fontFamily: FONT,
    fontSize: fontSize(),
    lineHeight: 1.15,
    cursorBlink: true,
    theme: theme(),
    linkHandler: { activate: openLink },
  });
  const fit = new FitAddon();
  term.loadAddon(fit);
  term.loadAddon(new WebLinksAddon(openLink));
  const tab = {
    api,
    agent,
    claude,
    resume: restoring,
    term,
    fit,
    el,
    opened: false,
    session: null,
    last: 0,
    unread: false,
  };
  term.onData((data) => tab.session && invoke("pty_write", { session: tab.session, data }));
  // xterm.js sends Enter for Shift+Enter too; an agent takes a line feed (Ctrl+J) as a new line in the message
  term.attachCustomKeyEventHandler((e) => {
    if (e.key !== "Enter" || !e.shiftKey || !tab.agent) return true;
    if (e.type === "keydown" && tab.session) invoke("pty_write", { session: tab.session, data: "\n" });
    return false;
  });
  api.onDidActiveChange((e) => {
    if (e.isActive) {
      assign({ active: tab });
      tab.unread = false;
    }
  });
  // a terminal starts its program when it first shows
  api.onDidVisibilityChange((e) => {
    if (e.isVisible) run(tab);
  });
  new ResizeObserver(() => fitTab(tab)).observe(el);
  tabs.push(tab);
  if (api.isVisible) setTimeout(() => run(tab));
  return tab;
}

// Starts the terminal's program if it has none (first time, or after it ended).
export async function run(tab) {
  if (tab.session || tab.starting || !tab.el.isConnected || !tabs.includes(tab)) return;
  if (!tab.opened) {
    tab.term.open(tab.el);
    tab.opened = true;
  }
  tab.fit.fit();
  tab.starting = true;
  tab.last = 0; // a task waits for the new program's output
  tab.term.reset();
  tab.session = await invoke("pty_start", {
    agent: tab.agent,
    cols: tab.term.cols,
    rows: tab.term.rows,
    claude: tab.claude,
    name: tab.api.title,
    resume: tab.resume,
  }).catch((e) => {
    tab.term.write(`${e}\r\n`);
    return null;
  });
  tab.starting = false;
  tab.resume = true; // a restart continues the conversation
}

export function fitTab(tab) {
  if (!tab.opened || !tab.el.offsetWidth) return;
  tab.fit.fit();
  if (tab.session) invoke("pty_resize", { session: tab.session, cols: tab.term.cols, rows: tab.term.rows });
}

// Shows the terminal and waits for its program.
export async function showTab(tab) {
  tab.api.setActive();
  assign({ active: tab });
  await run(tab);
  tab.term.focus();
}

export function closeTab(tab) {
  if (!tabs.includes(tab)) return;
  if (tab.session) invoke("pty_kill", { session: tab.session });
  tab.session = null;
  tab.term.dispose();
  assign({ tabs: tabs.filter((t) => t !== tab) });
  if (active === tab) assign({ active: null });
}

// A new terminal, beside the one used last, else right of Fava.
export function addTab({ agent = "", claude = null, name, group, direction } = {}) {
  if (agent === "claude" && !claude) claude = crypto.randomUUID();
  const near = active?.api ?? tabs.at(-1)?.api;
  const position = group
    ? { referenceGroup: group, direction }
    : near
      ? { referencePanel: near.id }
      : firstFava()
        ? { referencePanel: firstFava().id, direction: "right" }
        : undefined;
  const panel = dock.addPanel({
    id: `term-${crypto.randomUUID().slice(0, 8)}`,
    component: "term",
    title: name || freeName(agent || "shell"),
    params: { agent, claude },
    position,
  });
  return tabs.find((t) => t.api.id === panel.id);
}
export const newTab = (agent, group, direction) => showTab(addTab({ agent, group, direction }));
// the agent of new tabs: the one in the settings while it is installed, else the first one found
export const defaultAgent = () =>
  app.installed.includes(app.appSettings.agent) || app.appSettings.agent === ""
    ? app.appSettings.agent
    : app.installed[0] || "";

export const TRUST = /trust (this|the) (folder|directory|workspace)|do you trust/i;
export function screen(tab) {
  const b = tab.term.buffer.active,
    lines = [];
  // the visible screen only: an answered question may stay in the scrollback
  for (let i = b.baseY; i < b.baseY + tab.term.rows; i++) lines.push(b.getLine(i)?.translateToString(true) ?? "");
  return lines.join("\n");
}
export const asksTrust = (tab) => !!tab?.agent && tab.opened && TRUST.test(screen(tab));
export function agentNote() {
  const trust = asksTrust(active);
  app.agentNote = trust ? t("trust", { agent: active.agent }) : "";
}

// the agents found on PATH, which the "+" menu (Popups.svelte) and the settings offer
export async function agentMenu() {
  assign({ installed: await invoke("agents") });
}

// The terminals' output from the app, the agents' questions, the busy dots, and the theme and font.
export function initTerminal() {
  listen("pty-data", (e) => {
    const tab = tabs.find((t) => t.session === e.payload.session);
    if (!tab) return;
    tab.term.write(new Uint8Array(e.payload.data));
    tab.last = Date.now();
    if (!tab.api.isVisible) tab.unread = true;
  });
  listen("pty-exit", (e) => {
    const tab = tabs.find((t) => t.session === e.payload);
    if (!tab) return;
    tab.session = null;
    tab.term.write(`\r\n${t("ended")}\r\n`);
  });
  // An agent's question that only the user answers: whether to trust the folder (Claude Code, Codex and Cursor ask it
  // in a new folder). The app then explains it in the bar, and sends the agent nothing: its Enter would
  // answer the question, and the default answer exits.
  setInterval(agentNote, 1000);
  // after dark.js switched the tokens
  dark.addEventListener("change", () => setTimeout(() => tabs.forEach((t) => (t.term.options.theme = theme()))));
  // xterm measures the font when it opens; measure again once Fira Mono is loaded
  document.fonts.load('13px "Fira Mono"').then(() =>
    tabs.forEach((t) => {
      t.term.options.fontFamily = FONT;
      fitTab(t);
    }),
  );
}
