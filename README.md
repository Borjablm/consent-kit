# Consent Kit

A small cookie banner for WordPress and any other site: Accept and Reject with equal weight, Google Consent Mode v2, third-party scripts held back until the visitor accepts, and a consent log for proof. One plugin runs on every site. Each site's wording, colours and rules are settings, changed through an admin-only REST API, and the plugin updates itself from this repository's releases.

## What it does
- **Google Consent Mode v2.** Every signal is denied until the visitor accepts, and Accept grants only the signals listed in `grant` (analytics by default). The default is printed before any Google tag.
- **Scripts held until consent.** In WordPress, `wp.block` lists hosts (for example `wct-3.com`). Any script that loads from or mentions one is held back as `type="text/plain"`, and its preload hints are removed. It runs after Accept. JSON-LD and other data scripts are left alone. On other sites, mark a script yourself as `<script type="text/plain" data-consent="granted">`. Add `googletagmanager.com` to `wp.block` for Consent Mode's basic mode, where Google receives no request at all before Accept.
- **Banner.** Accept and Reject have equal weight. The choice lasts `maxAgeDays`. Reject deletes the cookies whose names start with an entry in `clearCookies`. Any link to `#cookie-settings` reopens the banner. Raising `version` asks every visitor again, for example when a new tracker is added. A plain `granted` or `denied` cookie value from an earlier banner keeps counting.
- **Consent log.** Each choice is stored with a random consent ID (also kept in the visitor's cookie), the policy version, the page path and the time. No IP address is stored. Rows older than `wp.logRetentionDays` are deleted daily. Tools > Consent log shows the last 30 days with the acceptance rate, finds a consent ID and exports CSV. The log endpoint validates its input, accepts records only from its own site plus `wp.allowedOrigins`, and allows 30 records an hour per visitor.
- **Legal pages.** `wp.legalPages` (slugs) get `noindex, follow` and are left out of the Yoast sitemap.
- **Safe by default.** With no settings stored, the plugin prints nothing. It also stays silent, with an admin notice, while one of the per-site plugins it replaced is active, so a visitor never sees two banners.
- **Global Privacy Control.** A browser that sends GPC is treated as Reject until the visitor chooses otherwise: no banner, nothing stored. Set `respectGpc: false` to turn this off.
- **What the banner said.** The WordPress plugin keeps the wording, granted signals and policy link for each policy version (Tools > Consent log), so a logged choice can be matched to what the visitor saw.
- **Updates.** The header `Update URI: https://github.com/Borjablm/consent-kit` makes WordPress read `update.json` from this repository. Every site auto-updates within about 12 hours of a release, and no wordpress.org plugin can overwrite it.

## Files
| Path | What it is |
|---|---|
| `consent-kit.js` | The banner. The WordPress plugin inlines it, and other sites load it as a file. |
| `wordpress/consent-kit.php` | The WordPress plugin: settings, config API, script holding, consent log, legal pages, updates. |
| `adapters/` | `@borjablm/consent-kit` for JavaScript apps: `inlineScript()` and helpers, `<ConsentKitScript>` for the page head, and `useConsent()` and `<ConsentGate>` for React. TypeScript types included. `core.mjs` is generated from `consent-kit.js` by `build.py`. |
| `schema/config.schema.json` | The settings, as a JSON Schema. `build.py` checks every `sites/*.json` against it. |
| `docs/INTEGRATION.md` | How to add the kit to any site, and the contract every integration follows. |
| `docs/REGULATIONS.md` | The EU, Spanish, UK, Californian and Google rules behind the banner, with official links, and how the kit meets each one. |
| `sites/*.json` | Settings for each site. `_template.json` is the starting point for a new site. |
| `configure.py` | Reads, compares and pushes a site's settings through its REST API. |
| `theme.py` | Reads a site's colours from its live homepage, checks contrast and previews the banner. |
| `audit.py` | Lists the cookies and third-party requests on any page before a choice, after Reject and after Accept. |
| `build.py`, `release.py` | Build the zip and manifest, and publish a tested release. |
| `test/` | Lint, browser tests and a throwaway WordPress in Docker. |

## Install on a WordPress site
1. Download `consent-kit-<version>.zip` from the latest release and upload it in Plugins > Add New > Upload, then activate it. It shows nothing until it has settings.
2. Copy `sites/_template.json` to `sites/<name>.json` and edit it. The keys are described below.
3. Push the settings: `python configure.py <name> --push`, with the credentials described under configure.py.
4. Check with `python audit.py https://<site>/`.

From then on, settings change through `configure.py` and code changes arrive as releases.

## Settings
| Key | Meaning |
|---|---|
| `site` | Host name, recorded in the log. |
| `cookie` | Name of the cookie that stores the choice. Changing it loses existing choices. |
| `version` | Policy version. Raise it to ask everyone again. |
| `maxAgeDays` | How long a choice lasts (1 to 395). |
| `grant` | Consent Mode signals granted on Accept: `analytics_storage`, `ad_storage`, `ad_user_data`, `ad_personalization`. |
| `clearCookies` | Cookie names or prefixes deleted on Reject (for example `_ga`). |
| `defaultLang`, `texts.<lang>` | Wording per language: `message`, `accept`, `reject`, `link`, `label`. The language comes from Polylang or the site locale. |
| `theme` | `bg`, `fg`, `border`, `link`, `button`, `buttonText`, `buttonBg`, `buttonHoverBg`, `buttonHoverFg`, `radius`, `buttonRadius`, `shadow`, `maxWidth`. Plain CSS colours and sizes only. The banner uses the page's font. |
| `zIndex`, `hideWhileOpen` | Stacking order, and CSS selectors hidden while the banner is open (for example a floating ad bar). |
| `wp.policyPage` | Page ID (Polylang translations are followed), page slug or URL for the banner's link. |
| `wp.block` | Hosts whose scripts wait for Accept. |
| `wp.legalPages` | Page slugs that get noindex. |
| `wp.log`, `wp.logRetentionDays`, `wp.allowedOrigins` | Consent log on or off, how long it is kept, and other hosts allowed to log here. |

## configure.py
```bash
python configure.py <name> --diff                        # live settings vs sites/<name>.json
python configure.py <name> --push                        # make the live site match the file
python configure.py <name> --set theme.button=#7a3b10    # edit the file, then push
python configure.py <name> --auto-theme                  # colours from the live site, then push
python configure.py <name> --pull                        # copy the live settings into the file
```
Credentials come from `WP_<SLUG>_URL`, `WP_<SLUG>_USER` and `WP_<SLUG>_APP_PASSWORD` (a WordPress application password for an administrator), set in the environment or in a dotenv file named by `CONSENT_KIT_ENV_FILE`. `<SLUG>` is the site file name in capitals unless `SLUGS` in the script maps it. After a change, the plugin clears the page cache (Kinsta, WP Rocket, W3 Total Cache, WP Super Cache, LiteSpeed) and reports which caches it cleared.

## Colours from the live site
```bash
python theme.py https://example.com/ --preview test/shots/example.png
```
This reads the colours the page renders (background, text, links, buttons and their rounding) and picks the most used brand colour. It checks contrast (4.5:1 for text, 3:1 for outlines) and falls back to the body text colour when a colour is too faint. With `--preview`, it draws the banner over the live page in a headless browser for desktop and phone. Nothing on the site changes. `--site <name>` writes the theme into that site's settings file.

## Sites without WordPress
Next.js and React sites install `github:Borjablm/consent-kit#v1.1.1` and use `<ConsentKitScript>`, `<ConsentGate>` and `useConsent()`. Plain HTML sites load `consent-kit.js` from jsDelivr, pinned to a release. [docs/INTEGRATION.md](docs/INTEGRATION.md) has both, the contract every integration follows, and how to log choices.

## Tests and releases
- `python test/lint.py` (Docker) runs gitleaks, PHP 7.4+ compatibility, the WordPress-Extra coding standards and ESLint, with zero findings allowed. Every `phpcs:ignore` must name its rule and give a reason.
- `python test/test_js.py` runs the banner in Chrome with every settings file, including Global Privacy Control.
- `python test/test_adapters.py` (after `npm install`) server-renders `<ConsentKitScript>` with React 18 and checks `useConsent()` and `<ConsentGate>` in Chrome.
- `python test/test_wp.py` (Docker) uses a throwaway WordPress to test install, the config API and its validation, script holding, the consent log, purging, the admin page, the old-plugin guard, and a self-update that keeps the settings. Add `--keep` to leave it running at http://localhost:8089.
- To release, raise the version in the plugin header, in `CONSENT_KIT_VERSION`, in `package.json` and in the first line of `consent-kit.js`, run `python build.py` (it regenerates `adapters/core.mjs`), commit, and run `python release.py`. It runs all four checks above and stops on any failure. It attaches the zip to a GitHub release and only then commits `update.json`, so no site sees a version it cannot download. To roll back, release the earlier code under a higher version number.

## Not covered
Sites that show Google AdSense or Ad Manager ads in the EEA or UK need a Google-certified CMP that supports the IAB TCF. Consent Kit is not one.

## Licence
GPL-2.0-or-later, see `LICENSE`.
