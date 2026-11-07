// Consent Kit for JavaScript apps: the core banner as a string, plus browser helpers.
// Framework-free; React helpers are in ./react.mjs and ./script.mjs.
import { CORE, VERSION } from "./core.mjs";

export { CORE, VERSION };

/**
 * The inline script to put first in <head>: the config, then the core banner.
 * The JSON is escaped so no value can close the script tag early.
 */
export function inlineScript(config) {
  const json = JSON.stringify(config)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026")
    .split(String.fromCharCode(0x2028)).join("\\u2028")
    .split(String.fromCharCode(0x2029)).join("\\u2029");
  return `window.ConsentKitConfig = ${json};\n${CORE}`;
}

/** "granted", "denied", or null (no choice yet, or not in a browser). */
export function getConsent() {
  return typeof window !== "undefined" && window.ConsentKit ? window.ConsentKit.get() : null;
}

/** Calls fn(choice) after every choice. Returns a function that stops listening. */
export function onConsentChange(fn) {
  if (typeof document === "undefined") return () => {};
  const handler = (e) => fn(e.detail.choice);
  document.addEventListener("consentkit:change", handler);
  return () => document.removeEventListener("consentkit:change", handler);
}

/** Reopens the banner, for a "Cookie settings" button. A link to #cookie-settings does the same. */
export function openConsentSettings() {
  if (typeof window !== "undefined" && window.ConsentKit) window.ConsentKit.open();
}
