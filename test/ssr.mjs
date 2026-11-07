// Server-renders <ConsentKitScript> with react-dom/server, as Next.js does. Used by test_adapters.py.
// Usage: node test/ssr.mjs '<config json>'
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ConsentKitScript } from "../adapters/script.mjs";

process.stdout.write(renderToStaticMarkup(createElement(ConsentKitScript, { config: JSON.parse(process.argv[2]) })));
