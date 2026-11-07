import type { ReactElement, ReactNode } from "react";
import type { ConsentChoice } from "./types";
export type * from "./types";

/** The visitor's choice; null on the server and before a choice. */
export declare function useConsent(): ConsentChoice | null;
/** Renders children only after Accept. */
export declare function ConsentGate(props: { children?: ReactNode; fallback?: ReactNode }): ReactElement;
/** Reopens the banner. */
export declare function openConsentSettings(): void;
