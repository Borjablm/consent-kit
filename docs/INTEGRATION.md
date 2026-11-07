# Adding Consent Kit to a site

Consent Kit is one script, `consent-kit.js`, plus thin adapters. Any site that follows this guide behaves the same way, and `audit.py` checks the result on the live site.

## The contract

Whatever the framework, a site using Consent Kit does these things.

1. **Settings.** One object that matches [`schema/config.schema.json`](../schema/config.schema.json). The fields that matter most are `cookie`, `version`, `texts` and, for logging, `logEndpoint`.
2. **Load order.** The config and `consent-kit.js` run first in `<head>`, before any Google tag or other tracker. They set Google Consent Mode v2 to denied for every signal unless the visitor accepted before.
3. **Trackers wait.** Nothing optional loads before Accept. Either render the tracker only when consent is granted (React `<ConsentGate>`), or mark it `<script type="text/plain" data-consent="granted">` and the kit runs it after Accept.
4. **Footer link.** Every page has a link to `#cookie-settings`, which reopens the banner.
5. **Policy page.** It names each cookie, how long it lasts and who receives the data, and mentions the consent log.
6. **Rules.** See [REGULATIONS.md](REGULATIONS.md).

### What the kit stores and sends

- **Cookie.** `<cookie>=<choice>.<consent id>.<version>`, for example `ai_consent=granted.3f9c...e1.1`. `<choice>` is `granted` or `denied` and the consent ID is 20 hex characters. A plain `granted` or `denied` value from an older banner counts as version 1. The cookie uses `path=/`, `SameSite=Lax`, `Secure` on https, and lasts `maxAgeDays`.
- **Consent Mode.** `gtag('consent', 'default', ...)` with all four v2 signals denied, or granted for the signals in `grant` when the visitor already accepted the current version. After a choice it calls `gtag('consent', 'update', ...)` for the signals in `grant`.
- **Log.** After each choice it POSTs `text/plain` JSON `{"id", "choice", "version", "lang", "site", "path"}` to `logEndpoint`, with `navigator.sendBeacon` or else `fetch(keepalive)`. A failed log never blocks the choice.
- **Page API.** `window.ConsentKit.get()` returns `"granted"`, `"denied"` or `null`. `ConsentKit.open()` reopens the banner and `ConsentKit.on(fn)` runs after each choice. The `consentkit:change` event on `document` has `detail.choice`.

## Next.js or React

Install from a release tag (no npm account needed):

```bash
npm install github:Borjablm/consent-kit#v1.1.1
```

Put the script first in `<head>` of the root layout (App Router) or `_document` (Pages Router):

```tsx
import { ConsentKitScript } from "@borjablm/consent-kit/script";
import { consentKitConfig } from "@/lib/consentKit";

<html lang="en">
  <head>
    <ConsentKitScript config={consentKitConfig} />
  </head>
  ...
```

Render trackers only after Accept:

```tsx
"use client";
import { ConsentGate } from "@borjablm/consent-kit/react";
import { GoogleAnalytics } from "@next/third-parties/google";

<ConsentGate>
  <GoogleAnalytics gaId="G-XXXX" />
</ConsentGate>
```

`useConsent()` returns the current choice for your own logic, and `openConsentSettings()` reopens the banner. `window.gtag` exists from the first moment, so existing `gtag("event", ...)` calls are safe before Google loads. Their events wait in `dataLayer` and Google reads them only if the visitor accepts.

## Plain HTML

```html
<script>window.ConsentKitConfig = { /* settings */ };</script>
<script src="https://cdn.jsdelivr.net/gh/Borjablm/consent-kit@v1.1.1/consent-kit.js"></script>
```

Put both in `<head>`, before any tracker, and pin the version.

## WordPress

Install the release zip once. After that, settings change through the plugin's admin-only API with `configure.py`, and the plugin updates itself from this repository's releases. See the README.

## Consent log for sites without WordPress

Point `logEndpoint` at a Consent Kit WordPress site run by the same company, and add your host to that site's `wp.allowedOrigins`. The log must be held by the same organisation that is responsible for your site's data.

To keep the log in your own app instead, accept `POST` with a `text/plain` body. Check that `id` matches `^[a-f0-9]{20}$`, `choice` is `granted` or `denied` and `version` is a positive integer. Check the `Origin` header, limit requests per client, and store the fields with a UTC timestamp, without the IP address. Delete rows after your retention period. Keep a copy of your banner text for each `version`.

## Checking your work

```bash
python audit.py https://your-site.example/
```

This lists the cookies and third-party requests before a choice, after Reject and after Accept, and exits with 1 if anything optional is set before consent. Run it after each deploy that adds a script, tag or embed.
