// An account's name as a person reads it: "Food › Groceries" for Expenses:Food:Groceries. The colon name stays where
// ledger text matters: a title tooltip, Fava, the agent's texts, errors.
// A name leaves out only what the screen already says, so that it differs from every name it can be taken for:
// accountName where all are children of one account shown there (or a breadcrumb's part), accountLabel where the
// root is clear (a heading, an optgroup, a list of one root), fullLabel where roots meet without headings. A
// sentence (a toast) has no headings: Food › Other, not Other, which Home › Other may share.
import { t } from "./i18n.js";

// a root's name in the app's language: Expenses is Výdavky
export const rootLabel = (a) => {
  const root = a.split(":")[0];
  const key = root.toLowerCase();
  return t(key) === key ? root : t(key);
};
// the account under `base`, or else under its root: Food › Groceries; `base` itself or a root by its last part
export const accountLabel = (a, base) => {
  const b = base && a.startsWith(`${base}:`) ? base : a.split(":")[0];
  return a.startsWith(`${b}:`) ? a.slice(b.length + 1).replaceAll(":", " › ") : accountName(a);
};
// the last part, where the place is short (a tile, a breadcrumb): Groceries, or the root's name
export const accountName = (a) => (a.includes(":") ? a.split(":").at(-1) : rootLabel(a));
// in a list without root headings, where Income:Gifts and Expenses:Gifts meet: Výdavky › Food › Groceries
export const fullLabel = (a) => (a.includes(":") ? `${rootLabel(a)} › ${accountLabel(a)}` : rootLabel(a));
