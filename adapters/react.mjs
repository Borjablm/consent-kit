"use client";
// React hooks and components for Consent Kit. Needs ConsentKitScript (./script.mjs) in <head>.
import { createElement, Fragment, useSyncExternalStore } from "react";
import { getConsent, onConsentChange, openConsentSettings } from "./index.mjs";

const subscribe = (notify) => onConsentChange(notify);
const serverSnapshot = () => null;

/** The visitor's choice: "granted", "denied" or null. Null on the server and before a choice. */
export function useConsent() {
  return useSyncExternalStore(subscribe, getConsent, serverSnapshot);
}

/**
 * Renders children only after the visitor accepted, for example a tracking <Script>.
 * If they accept later on the same page, the children appear then.
 */
export function ConsentGate({ children, fallback = null }) {
  return createElement(Fragment, null, useConsent() === "granted" ? children : fallback);
}

export { openConsentSettings };
