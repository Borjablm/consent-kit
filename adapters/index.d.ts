import type { ConsentChoice, ConsentKitConfig } from "./types";
export type * from "./types";

/** The core banner script, as a string. */
export declare const CORE: string;
export declare const VERSION: string;
/** The config plus the core banner, ready to inline first in <head>. */
export declare function inlineScript(config: ConsentKitConfig): string;
/** "granted", "denied", or null before a choice or outside a browser. */
export declare function getConsent(): ConsentChoice | null;
/** Calls fn after every choice; returns a function that stops listening. */
export declare function onConsentChange(fn: (choice: ConsentChoice) => void): () => void;
/** Reopens the banner. */
export declare function openConsentSettings(): void;
