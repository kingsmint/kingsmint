// Messages after a change, as toasts at the top right, under the tabs: over the page, which they do not move. A
// message is a Svelte component mounted into a wa-toast-item, with a `close` prop; wa-toast removes the item when it
// hides (after its duration, or closed), and the component goes with it. One message at a time: a new one closes the
// one before.
import { mount, unmount } from "svelte";

let stack = null;
let last = null;

export function toast(Component, props = {}, { duration = 6000, variant = "brand" } = {}) {
  last?.();
  if (!stack) {
    stack = document.createElement("wa-toast");
    stack.setAttribute("placement", "top-end");
    document.body.append(stack);
  }
  const item = document.createElement("wa-toast-item");
  item.setAttribute("variant", variant);
  item.setAttribute("duration", String(duration)); // 0: until it is closed
  const close = () => item.isConnected && item.hide?.();
  const view = mount(Component, { target: item, props: { ...props, close } });
  item.addEventListener("wa-after-hide", (e) => e.target === item && unmount(view));
  stack.append(item);
  last = close;
  return close;
}
