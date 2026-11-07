import type { ReactElement } from "react";
import type { ConsentKitConfig } from "./types";
export type * from "./types";

/** Inline <script> with the config and the core banner. Put it first in <head>. */
export declare function ConsentKitScript(props: { config: ConsentKitConfig; nonce?: string }): ReactElement;
