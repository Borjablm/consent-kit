# Integration contract

How to install Consent Kit on each stack is in the [README](../README.md#choose-your-stack). This page is the technical contract behind it, for developers who build their own integration, check one, or write their own log endpoint. Any integration that meets it behaves the same as the official ones, and `audit.py` checks the result on the live site.

## Every site

1. **Settings.** One object that matches [schema/config.schema.json](../schema/config.schema.json).
2. **Load order.** The settings and `consent-kit.js` run first in `<head>`, before any Google tag or other tracker.
3. **Trackers wait.** Nothing optional loads, or sets a cookie, before Accept.
4. **Footer link.** Every page has a link to `#cookie-settings`, or a control that calls `ConsentKit.open()`.
5. **Policy page.** It names each cookie, how long it lasts and who receives the data, and mentions the consent log.
6. **Rules.** See [REGULATIONS.md](REGULATIONS.md).

## What the script does

- **Cookie.** It stores `<cookie>=<choice>.<consent id>.<version>`, for example `ex_consent=granted.3f9c0a1b2c3d4e5f6a7b.1`. The choice is `granted` or `denied`, and the consent ID is 20 hex characters. A plain `granted` or `denied` value from an older banner counts as version 1. The cookie uses `path=/`, `SameSite=Lax`, `Secure` on https, and lasts `maxAgeDays`.
- **Consent Mode.** On load it calls `gtag('consent', 'default', ...)` with all four v2 signals denied, or with the signals in `grant` granted if the visitor already accepted the current `version`. After a choice it calls `gtag('consent', 'update', ...)` for the signals in `grant`. It defines `window.gtag` if the page hasn't.
- **Held scripts.** On Accept, and on every later page view after Accept, it runs every `<script type="text/plain" data-consent="granted">`, keeping its attributes, `src` and `data-type` (for modules).
- **Reject.** It deletes the cookies whose names start with an entry in `clearCookies`.
- **Global Privacy Control.** With `respectGpc` on and no choice yet, `navigator.globalPrivacyControl === true` keeps the banner closed and nothing is stored or logged. The visitor can still open the settings and accept.
- **Page API.** `window.ConsentKit.get()` returns `"granted"`, `"denied"` or `null`. `ConsentKit.open()` reopens the banner and `ConsentKit.on(fn)` runs after each choice. The `consentkit:change` event on `document` carries `detail.choice`.

## Log endpoint

After each choice the script sends a `POST` with a `text/plain` body to `logEndpoint`, using `navigator.sendBeacon` or else `fetch` with `keepalive`. A failed request never blocks the choice.

```json
{"id": "3f9c0a1b2c3d4e5f6a7b", "choice": "granted", "version": 1, "lang": "en", "site": "example.com", "path": "/pricing/"}
```

The WordPress plugin's endpoint is `/wp-json/consent-kit/v1/log`. To write your own, it should do the following.

- Accept requests only from your own origins (check the `Origin` header), and limit requests per client.
- Reject the record unless `id` matches `^[a-f0-9]{20}$`, `choice` is `granted` or `denied`, and `version` is a positive integer.
- Store the fields with a UTC timestamp. Do not store the IP address.
- Delete records after your retention period (the plugin keeps them 3 years).
- Keep a copy of the banner wording for each `version`, so a record can be matched to what the visitor saw.

## Checking an integration

```bash
python audit.py https://your-site.example/
```

It lists the cookies and third-party requests before a choice, after Reject and after Accept, and exits with 1 if anything optional is set before consent.
