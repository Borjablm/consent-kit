# Consent Kit

A cookie banner for any website. It asks visitors before any tracking starts, holds trackers back until they accept, sets Google Consent Mode v2, and keeps a log of every choice as proof. It works the same way on WordPress, on Next.js or React apps, and on any other site that can add a script to its pages.

## What it does on every site

- **Asks first.** The banner offers Accept and Reject side by side, with the same size and style, on the first screen.
- **Holds trackers back.** Analytics, pixels and other optional scripts don't load, and set no cookies, until the visitor accepts.
- **Sets Google Consent Mode v2.** Every signal starts as denied, before any Google tag runs. Accept grants only the signals you choose (analytics by default).
- **Lets visitors change their mind.** A link to `#cookie-settings` anywhere on the page reopens the banner. Reject also deletes the tracking cookies.
- **Remembers the choice** for 180 days by default, and asks everyone again when you raise the policy `version`, for example after adding a tracker.
- **Logs every choice** with a random ID, the choice, the policy version, the page and the time, without any IP address.
- **Respects Global Privacy Control.** A browser that sends GPC is treated as Reject until the visitor chooses otherwise.
- **Fits the site.** Wording per language, the site's own colours, and the page's own font.

[docs/REGULATIONS.md](docs/REGULATIONS.md) lists the EU, Spanish, UK, Californian and Google rules this follows, with official links.

## Choose your stack

| | WordPress | Next.js or React | Plain HTML or any other stack |
|---|---|---|---|
| **Install** | Upload the plugin zip once | `npm install` the release | Two `<script>` tags |
| **Settings live in** | The site's database, changed with `configure.py` | A settings file in your code | The page |
| **Trackers wait by** | Listing their hosts in `wp.block` (automatic) | Wrapping them in `<ConsentGate>` | Marking them `type="text/plain"` |
| **Consent log** | Built in (Tools > Consent log) | Sent to a log endpoint | Sent to a log endpoint |
| **Updates** | Automatic, from this repo's releases | Change the version in `package.json` | Change the version in the script URL |

## WordPress

### Install
1. Download `consent-kit-<version>.zip` from the [latest release](https://github.com/Borjablm/consent-kit/releases/latest) and upload it in Plugins > Add New > Upload. Activate it. It shows nothing until it has settings.
2. Copy `sites/_template.json` to `sites/<name>.json` and fill it in (see [Settings](#settings)). `python theme.py https://<site>/ --site <name>` fills in the colours from the live site.
3. Push the settings with `python configure.py <name> --push`.
4. Add a "Cookie settings" link to `#cookie-settings` in the footer.
5. Check the live site with `python audit.py https://<site>/`.

### Change settings later
Settings live in the site's database and change through an admin-only REST route, with no re-upload.

```bash
python configure.py <name> --diff                        # live settings vs sites/<name>.json
python configure.py <name> --set theme.button=#7a3b10    # edit the file, then push
python configure.py <name> --push                        # make the live site match the file
python configure.py <name> --auto-theme                  # colours from the live site, then push
python configure.py <name> --pull                        # copy the live settings into the file
```

`configure.py` reads `WP_<SLUG>_URL`, `WP_<SLUG>_USER` and `WP_<SLUG>_APP_PASSWORD` (an application password for an administrator) from the environment, or from a dotenv file named in `CONSENT_KIT_ENV_FILE`. After each change the plugin clears the page cache (Kinsta, WP Rocket, W3 Total Cache, WP Super Cache, LiteSpeed).

### What the plugin adds on WordPress
- **Trackers held back without code changes.** Any script that loads from or mentions a host in `wp.block` is held until Accept, and its preload hints are removed. JSON-LD and other data scripts are left alone. Adding `googletagmanager.com` gives Consent Mode's basic mode, where Google receives nothing before Accept.
- **Consent log and proof.** Tools > Consent log shows the last 30 days with the acceptance rate, finds a consent ID, exports CSV, and shows what the banner said for each policy version. Rows are deleted after `wp.logRetentionDays` (3 years by default).
- **Log endpoint for other sites.** Sites without WordPress can send their choices to this site's log once their host is listed in `wp.allowedOrigins`.
- **Legal pages.** Pages listed in `wp.legalPages` get `noindex, follow` and are left out of the Yoast sitemap.
- **Safe by default.** With no settings the plugin prints nothing. While an older per-site banner plugin is active it stays silent and shows an admin notice, so visitors never see two banners.
- **Automatic updates.** The plugin reads `update.json` from this repository and updates itself within about 12 hours of a release. No wordpress.org plugin can overwrite it.

## Next.js and React

### Install
```bash
npm install https://codeload.github.com/Borjablm/consent-kit/tar.gz/refs/tags/v1.1.1
```
Use the release tarball URL. npm saves a `github:` address as `git+ssh` in the lockfile, which fails in CI and Docker builds that have no SSH key.

### 1. Add your settings
```ts
// lib/consentKit.ts
import type { ConsentKitConfig } from "@borjablm/consent-kit";

export const consentKitConfig: ConsentKitConfig = {
  site: "example.com",
  cookie: "ex_consent",
  version: 1,
  texts: {
    en: {
      message: "We use Google Analytics cookies to see how the site is used. They are only set if you accept.",
      accept: "Accept",
      reject: "Reject",
      link: "Privacy policy",
      label: "Cookie consent",
    },
  },
  links: { en: "/privacy-policy" },
  logEndpoint: "https://your-wordpress-site.example/wp-json/consent-kit/v1/log",
};
```
`python theme.py https://example.com/` prints a `theme` block with the site's colours. See [Settings](#settings) for every key.

### 2. Put the script first in `<head>`
In the root layout (App Router) or `_document` (Pages Router):
```tsx
import { ConsentKitScript } from "@borjablm/consent-kit/script";
import { consentKitConfig } from "@/lib/consentKit";

<html lang="en">
  <head>
    <ConsentKitScript config={consentKitConfig} />
  </head>
```

### 3. Make trackers wait
```tsx
"use client";
import { ConsentGate } from "@borjablm/consent-kit/react";
import { GoogleAnalytics } from "@next/third-parties/google";

<ConsentGate>
  <GoogleAnalytics gaId="G-XXXX" />
</ConsentGate>
```
Anything inside `<ConsentGate>` renders only after Accept, including when the visitor accepts later on the same page. `window.gtag` exists from the start, so existing `gtag("event", ...)` calls stay safe. `useConsent()` returns the current choice for your own logic.

### 4. Add the footer link
A link to `#cookie-settings` reopens the banner, or call `openConsentSettings()` from a button.

## Plain HTML and other stacks

### Install
Put both tags first in `<head>`, before any tracker, with the version pinned:
```html
<script>window.ConsentKitConfig = { /* settings, see below */ };</script>
<script src="https://cdn.jsdelivr.net/gh/Borjablm/consent-kit@v1.1.1/consent-kit.js"></script>
```

### Make trackers wait
Change each optional script's type, and the kit runs it after Accept:
```html
<script type="text/plain" data-consent="granted" src="https://example-tracker.com/tag.js"></script>
```

### Footer link and page API
A link to `#cookie-settings` reopens the banner. Page code can use `ConsentKit.get()` (`"granted"`, `"denied"` or `null`), `ConsentKit.on(fn)`, `ConsentKit.open()`, or the `consentkit:change` event.

## Settings

The same settings work on every stack. [schema/config.schema.json](schema/config.schema.json) is the full definition, and the TypeScript type is `ConsentKitConfig`.

| Key | Stack | Meaning |
|---|---|---|
| `site` | All | Host name, recorded in the log. |
| `cookie` | All | Cookie that stores the choice. Changing it loses everyone's choice. |
| `version` | All | Policy version. Raise it to ask everyone again. |
| `maxAgeDays` | All | How long a choice lasts, 1 to 395 days (default 180). |
| `grant` | All | Consent Mode signals granted on Accept: `analytics_storage` (default), `ad_storage`, `ad_user_data`, `ad_personalization`. |
| `clearCookies` | All | Cookie names or prefixes deleted on Reject (default `_ga`). |
| `texts.<lang>`, `defaultLang` | All | Wording per language (`message`, `accept`, `reject`, `link`, `label`). The language comes from `<html lang>`, or Polylang on WordPress. |
| `theme` | All | Colours and rounding (`bg`, `fg`, `border`, `link`, `button`, `buttonText`, `buttonBg`, `buttonHoverBg`, `buttonHoverFg`, `radius`, `buttonRadius`, `shadow`, `maxWidth`). |
| `zIndex`, `hideWhileOpen` | All | Stacking order, and CSS selectors hidden while the banner is open (for example a chat bubble). |
| `respectGpc` | All | Treat Global Privacy Control as Reject (default on). |
| `links.<lang>` | Not WordPress | Link to the privacy policy per language. |
| `logEndpoint` | Not WordPress | Where each choice is sent. |
| `wp.policyPage` | WordPress | Policy page ID, slug or URL. |
| `wp.block` | WordPress | Hosts whose scripts wait for Accept. |
| `wp.legalPages` | WordPress | Page slugs that get noindex. |
| `wp.log`, `wp.logRetentionDays`, `wp.allowedOrigins` | WordPress | Consent log on or off, how long it is kept, and other hosts allowed to log here. |

## The consent log

Each choice is stored with a random consent ID (also kept in the visitor's cookie, so a record can be matched to a browser), Accept or Reject, the policy version, the language, the page and the time in UTC. No IP address is stored.

- **WordPress sites** keep their log in their own database (Tools > Consent log).
- **Other sites** send each choice to `logEndpoint`. Point it at a Consent Kit WordPress site run by the same organisation, and list your host in that site's `wp.allowedOrigins`. The log must stay with the organisation responsible for the site's data.
- **Your own endpoint** works too. [docs/INTEGRATION.md](docs/INTEGRATION.md#log-endpoint) describes what it receives and must check.

## Tools for any site

```bash
python audit.py https://example.com/
```
Lists the cookies and third-party requests before a choice, after Reject and after Accept, and exits with 1 if anything optional is set before consent. Run it after each deploy that adds a script, tag or embed.

```bash
python theme.py https://example.com/ --preview shots/example.png
```
Reads the colours the live page shows, checks contrast, and draws the banner over the page in a headless browser for desktop and phone. Nothing on the site changes.

Both need Python 3 with Playwright (`pip install playwright` and `playwright install chromium`).

## Not covered

Sites that show Google AdSense or Ad Manager ads in the EEA or UK need a Google-certified CMP that supports the IAB TCF. Consent Kit is not one.

## Maintaining this repository

| Path | What it is |
|---|---|
| `consent-kit.js` | The banner. Every stack runs this file. |
| `adapters/` | The `@borjablm/consent-kit` package: `inlineScript()` and helpers, `<ConsentKitScript>`, `useConsent()` and `<ConsentGate>`, with TypeScript types. `core.mjs` is generated from `consent-kit.js`. |
| `wordpress/consent-kit.php` | The WordPress plugin. |
| `schema/config.schema.json` | The settings, as a JSON Schema. |
| `sites/*.json` | Settings for each WordPress site we run. `_template.json` starts a new one. |
| `configure.py`, `theme.py`, `audit.py` | Settings push, colours from a live site, and the cookie audit. |
| `docs/` | `INTEGRATION.md` (the technical contract) and `REGULATIONS.md` (the rules). |
| `build.py`, `release.py`, `test/` | Build, release and tests. |

**Tests.** `python test/lint.py` runs gitleaks, PHP 7.4+ compatibility, the WordPress-Extra coding standards and ESLint, with zero findings allowed. `python test/test_js.py` runs the banner in Chrome with every settings file. `python test/test_adapters.py` (after `npm install`) checks the React adapters with React 18. `python test/test_wp.py` runs the plugin in a throwaway WordPress, including a self-update. The lint and WordPress tests need Docker.

**Releases.** Raise the version in the plugin header, in `CONSENT_KIT_VERSION`, in `package.json` and on the first line of `consent-kit.js`. Then run `python build.py`, commit, and run `python release.py`. It runs every test and stops on any failure, pushes, tags that exact commit, and only then updates `update.json`, which WordPress sites read. To roll back, release the earlier code under a higher version number.

## Licence

GPL-2.0-or-later, see [LICENSE](LICENSE).
