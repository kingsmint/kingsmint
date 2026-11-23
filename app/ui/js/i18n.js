// The app's texts in English and Slovak are in i18n.json (app: the app's, agent: tasks for the agent, in the ledger's
// language); Vite bundles them into the page, and the server reads the same file for its pages.
// t(key, vars) gives the text in the app's language (app.lang: a Svelte component that calls it draws again when it
// changes); {name} takes vars.name. Texts with markup (<b>, <code>) are ours, so
// data-i18n-html sets them as HTML.
import I18N from "../i18n.json";
import { app } from "./app.svelte.js";

const STRINGS = I18N.app,
  AGENT_STRINGS = I18N.agent;

const fill = (text, vars = {}) =>
  typeof text !== "string" ? text : text.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");
export const t = (key, vars) => fill(STRINGS[app.lang][key] ?? STRINGS.en[key] ?? key, vars);
export const tAgent = (key, vars) => fill(AGENT_STRINGS[app.ledgerLang][key] ?? AGENT_STRINGS.en[key], vars);
export const systemLang = () => ((navigator.language || "en").toLowerCase().startsWith("sk") ? "sk" : "en");

// Sets the static texts of the page: data-i18n (text), data-i18n-html, data-i18n-title, data-i18n-placeholder,
// data-i18n-label (a Web Awesome field's label).
export function applyLang() {
  document.documentElement.lang = app.lang;
  for (const el of document.querySelectorAll("[data-i18n]")) el.textContent = t(el.dataset.i18n);
  for (const el of document.querySelectorAll("[data-i18n-html]")) el.innerHTML = t(el.dataset.i18nHtml);
  for (const el of document.querySelectorAll("[data-i18n-title]")) el.title = t(el.dataset.i18nTitle);
  for (const el of document.querySelectorAll("[data-i18n-placeholder]")) el.placeholder = t(el.dataset.i18nPlaceholder);
  for (const el of document.querySelectorAll("[data-i18n-label]")) el.label = t(el.dataset.i18nLabel);
}
