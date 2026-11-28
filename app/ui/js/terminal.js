// Terminals: xterm.js on a PTY of the app, with an agent or a shell; their colors, the agents' questions, the "+" menu.

import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { Terminal } from "@xterm/xterm";
import { tick } from "svelte";
import { app } from "./app.svelte.js";
import { openLink } from "./fava.js";
import { t } from "./i18n.js";
import { saveSoon } from "./panels.js";
import { active, assign, restoring, side, tabs } from "./state.js";
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
export const retheme = () => tabs.forEach((t) => (t.term.options.theme = theme()));
// A CSS color as #rrggbb, which xterm takes: a theme's token can be color-mix()
const pixel = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
const hex = (color) => {
  pixel.fillStyle = "#000";
  pixel.fillStyle = color;
  pixel.fillRect(0, 0, 1, 1);
  return `#${[...pixel.getImageData(0, 0, 1, 1).data.slice(0, 3)].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
};
export function theme() {
  const css = getComputedStyle(document.documentElement),
    token = (name) => hex(css.getPropertyValue(`--wa-color-${name}`).trim());
  const km = (name) => css.getPropertyValue(`--km-${name}`).trim(); // the app's theme (themes.css), if one
  const colors = (red, green, yellow, blue) =>
    red && { red, green, yellow, blue, brightRed: red, brightGreen: green, brightYellow: yellow, brightBlue: blue };
  return {
    ...THEMES[dark.matches ? "dark" : "light"],
    ...colors(km("danger"), km("success"), km("warning"), km("brand")),
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

// the new tabs that install their agent first (pty_start's install); not in the panel's params, which the layout keeps
const installing = new Set();

// `claude`: the conversation id in the layout of an older app, which had it for Claude Code only. A tab without a
// profile (an older layout) runs its agent's own profile.
export function makeTab(api, { agent = "", profile = null, conversation = null, claude = null }, el) {
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
    profile: profile ?? agent,
    conversation: conversation ?? claude,
    install: installing.delete(api.id),
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
  tab.started = Date.now();
  const p = profileOf(tab);
  tab.session = await invoke("pty_start", {
    agent: tab.agent,
    path: p.path || null,
    config: p.config || null,
    cols: tab.term.cols,
    rows: tab.term.rows,
    conversation: tab.conversation,
    name: tab.api.title,
    resume: tab.resume,
    install: tab.install,
  }).catch((e) => {
    tab.term.write(`${e}\r\n`);
    return null;
  });
  tab.starting = false;
  tab.resume = true; // a restart continues the conversation
  if (tab.install) {
    tab.install = false; // a restart runs the agent, not its installer again
    watchInstall(tab.agent);
  }
}

// Looks for the agent on PATH until its installer has put it there (or 10 min passed), for the "+" menu and the tasks.
async function watchInstall(agent) {
  for (let i = 0; i < 200 && !app.installed.includes(agent); i++) {
    await new Promise((r) => setTimeout(r, 3000));
    await agentMenu();
  }
}

export function fitTab(tab) {
  if (!tab.opened || !tab.el.offsetWidth) return;
  tab.fit.fit();
  if (tab.session) invoke("pty_resize", { session: tab.session, cols: tab.term.cols, rows: tab.term.rows });
}

// Shows the terminal, with the sidebar, and waits for its program.
export async function showTab(tab) {
  app.sidebar.open = true;
  await tick(); // the sidebar shows: the terminal measures its size
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

// A new terminal: a tab in the agent's sidebar.
// `profile`: its id (profiles()); it gives the agent. Without one, the agent's own profile.
export function addTab({ agent = "", profile = null, conversation = null, name, install = false } = {}) {
  const p = profileById(profile);
  if (p) agent = p.agent;
  profile = p ? p.id : agent;
  if (["claude", "pi"].includes(agent) && !conversation) conversation = crypto.randomUUID(); // Codex makes its own
  const id = `term-${crypto.randomUUID().slice(0, 8)}`;
  if (install) installing.add(id); // before addPanel, which makes the tab
  const panel = side.addPanel({
    id,
    component: "term",
    title: name || freeName(p?.name || agent || "shell"),
    params: { agent, profile, conversation },
  });
  return tabs.find((t) => t.api.id === panel.id);
}
export const newTab = (profile) => showTab(addTab({ profile }));
// a tab that runs the agent's official installer, then the agent, which asks the user to sign in
export const installAgent = (agent) => showTab(addTab({ agent, install: true }));

// The agents the app knows, with their names for the user; pty_start knows them by the same keys (AGENTS in main.rs).
export const AGENTS = { claude: "Claude Code", codex: "Codex", "cursor-agent": "Cursor", pi: "pi" };
// The profiles: one for each agent found (its id is the agent's), and the user's own from the settings, which give the
// agent's program (`path`) and its own folder (`config`: a second login, such as a private Claude Code).
export const profiles = () => [
  ...app.installed.map((a) => ({ id: a, name: AGENTS[a] ?? a, agent: a })),
  ...(app.appSettings.profiles ?? []),
];
export const profileById = (id) => (id ? profiles().find((p) => p.id === id) : null);
// a tab's profile; one removed from the settings leaves the agent as found on PATH
const profileOf = (tab) => profileById(tab.profile) ?? { agent: tab.agent };
// The profile of new tabs and of the app's tasks: the ledger's (the settings, on this computer), else the app's,
// while it exists; "" is a shell. Else the first agent found.
export function defaultProfile() {
  for (const id of [app.appSettings.ledgerProfiles?.[app.current], app.appSettings.agent]) {
    if (id === "" || profileById(id)) return id;
  }
  return profiles()[0]?.id ?? "";
}

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

// Codex makes its conversation's id when the first message is sent; the tab looks for it while Codex writes (at
// most every 2 s) and keeps it in the layout, so a restart continues the conversation.
async function findCodex(tab) {
  if (tab.looking || Date.now() - (tab.looked ?? 0) < 2000) return;
  tab.looking = true;
  tab.looked = Date.now();
  const taken = tabs.map((t) => t.conversation).filter(Boolean);
  const config = profileOf(tab).config || null;
  const id = await invoke("codex_conversation", { since: tab.started, taken, config }).catch(() => null);
  tab.looking = false;
  if (!id || tab.conversation || taken.includes(id)) return;
  tab.conversation = id;
  tab.api.updateParameters({ agent: tab.agent, profile: tab.profile, conversation: id });
  saveSoon();
}

// The terminals' output from the app, the agents' questions, the busy dots, and the theme and font.
export function initTerminal() {
  listen("pty-data", (e) => {
    const tab = tabs.find((t) => t.session === e.payload.session);
    if (!tab) return;
    tab.term.write(new Uint8Array(e.payload.data));
    tab.last = Date.now();
    if (!tab.api.isVisible) tab.unread = true;
    if (tab.agent === "codex" && !tab.conversation) findCodex(tab);
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
  dark.addEventListener("change", () => setTimeout(retheme));
  // xterm measures the font when it opens; measure again once Fira Mono is loaded
  document.fonts.load('13px "Fira Mono"').then(() =>
    tabs.forEach((t) => {
      t.term.options.fontFamily = FONT;
      fitTab(t);
    }),
  );
}
