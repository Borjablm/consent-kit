// <ConsentKitScript config={...} />: renders the config and core as one inline <script>.
// Put it first inside <head> in the root layout (Next.js App Router) or _document (Pages Router),
// before any Google tag, so Consent Mode's default is set before Google loads.
// Works in any React app that renders on the server. No "use client": it is plain markup.
import { createElement } from "react";
import { inlineScript } from "./index.mjs";

export function ConsentKitScript({ config, nonce }) {
  return createElement("script", {
    id: "consent-kit-js",
    nonce,
    dangerouslySetInnerHTML: { __html: inlineScript(config) },
  });
}
