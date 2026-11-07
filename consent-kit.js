/*!
 * Consent Kit 1.1.0. Accept/Reject cookie banner with Google Consent Mode v2.
 * One file for every site. Load it synchronously in <head>, before any Google tag,
 * after setting window.ConsentKitConfig. The WordPress plugin inlines this file.
 * https://github.com/Borjablm/consent-kit (GPL-2.0-or-later)
 */
(function (w, d) {
	'use strict';
	if (w.ConsentKit) { return; }

	var cfg = w.ConsentKitConfig || {};
	var NAME = cfg.cookie || 'ck_consent';
	var VERSION = parseInt(cfg.version, 10) || 1;
	var MAX_AGE = Math.round((cfg.maxAgeDays || 182) * 86400);
	var GRANT = cfg.grant || ['analytics_storage'];
	var CLEAR = cfg.clearCookies || ['_ga'];
	var SIGNALS = ['ad_storage', 'ad_user_data', 'ad_personalization', 'analytics_storage'];
	var listeners = [];

	// Stored value: "<choice>.<consent id>.<policy version>". Plain "granted"/"denied"
	// (the format of the older per-site plugins) counts as version 1 with no id.
	function read() {
		var m = d.cookie.match(new RegExp('(?:^|; )' + NAME + '=(granted|denied)(?:\\.([a-f0-9]{20}))?(?:\\.(\\d+))?(?:;|$)'));
		if (!m) { return null; }
		return { choice: m[1], id: m[2] || null, version: m[3] ? parseInt(m[3], 10) : 1 };
	}
	var saved = read();
	var current = saved && saved.version === VERSION ? saved.choice : null;

	// Global Privacy Control (a browser-wide "do not sell or share" signal, honoured under 11 CCR 7025).
	// With no choice yet it counts as Reject: the banner stays closed and nothing is stored or logged.
	// The visitor can still open the settings and accept. It is never read as Accept.
	var gpc = !current && cfg.respectGpc !== false && w.navigator && w.navigator.globalPrivacyControl === true;

	// Google Consent Mode v2 default. Must run before any Google tag.
	w.dataLayer = w.dataLayer || [];
	if (typeof w.gtag !== 'function') {
		w.gtag = function () { w.dataLayer.push(arguments); };
	}
	var defaults = {};
	SIGNALS.forEach(function (s) {
		defaults[s] = current === 'granted' && GRANT.indexOf(s) !== -1 ? 'granted' : 'denied';
	});
	defaults.wait_for_update = 500;
	w.gtag('consent', 'default', defaults);

	function newId() {
		var a = new Uint8Array(10);
		(w.crypto || w.msCrypto).getRandomValues(a);
		return Array.prototype.map.call(a, function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
	}

	function remember(choice, id) {
		var secure = location.protocol === 'https:' ? '; Secure' : '';
		d.cookie = NAME + '=' + choice + '.' + id + '.' + VERSION + '; path=/; max-age=' + MAX_AGE + '; SameSite=Lax' + secure;
	}

	function log(choice, id, lang) {
		if (!cfg.logEndpoint) { return; }
		var body = JSON.stringify({
			id: id, choice: choice, version: VERSION, lang: lang,
			site: cfg.site || location.hostname, path: location.pathname.slice(0, 255)
		});
		// Logging never blocks the choice: a failed beacon falls back to fetch, a failed fetch is dropped.
		if (navigator.sendBeacon && attempt(function () { return navigator.sendBeacon(cfg.logEndpoint, body); }) === true) { return; }
		if (w.fetch) {
			attempt(function () {
				return fetch(cfg.logEndpoint, { method: 'POST', body: body, keepalive: true, credentials: 'omit' }).catch(function () { return null; });
			});
		}
	}

	// Runs fn and returns its result, or the error it threw, so one failing step cannot stop the banner.
	function attempt(fn) {
		try { return fn(); } catch (err) { return err; }
	}

	// Scripts held back as <script type="text/plain" data-consent="granted"> run after Accept.
	function runDeferred() {
		d.querySelectorAll('script[type="text/plain"][data-consent]').forEach(function (old) {
			var s = d.createElement('script');
			for (var i = 0; i < old.attributes.length; i++) {
				var a = old.attributes[i];
				if (a.name !== 'type' && a.name !== 'data-consent' && a.name !== 'data-type') { s.setAttribute(a.name, a.value); }
			}
			if (old.getAttribute('data-type')) { s.type = old.getAttribute('data-type'); }
			if (old.src) { s.async = false; } else { s.text = old.text; }
			old.parentNode.replaceChild(s, old);
		});
	}

	function clearCookies() {
		var host = location.hostname.replace(/^www\./, '');
		d.cookie.split('; ').forEach(function (c) {
			var name = c.split('=')[0];
			var hit = CLEAR.some(function (p) { return name.indexOf(p) === 0; });
			if (hit && name !== NAME) {
				['', '; domain=' + host, '; domain=.' + host, '; domain=' + location.hostname].forEach(function (dom) {
					d.cookie = name + '=; path=/; max-age=0' + dom;
				});
			}
		});
	}

	function pickLang() {
		var texts = cfg.texts || {};
		var want = (cfg.lang || d.documentElement.lang || '').slice(0, 2).toLowerCase();
		if (texts[want]) { return want; }
		if (cfg.defaultLang && texts[cfg.defaultLang]) { return cfg.defaultLang; }
		return Object.keys(texts)[0] || 'en';
	}

	var FALLBACK = {
		message: 'We use analytics cookies to see how the site is used. They are only set if you accept.',
		accept: 'Accept', reject: 'Reject', link: 'Privacy policy', label: 'Cookie consent'
	};

	function css() {
		var t = cfg.theme || {};
		var v = function (k, dflt) { return t[k] || dflt; };
		var hide = (cfg.hideWhileOpen || []).map(function (sel) { return '.ck-open ' + sel; }).join(',');
		return '#consent-kit{position:fixed;left:16px;right:16px;bottom:16px;z-index:' + (cfg.zIndex || 99999) + ';max-width:' + v('maxWidth', '720px') + ';margin:0 auto;padding:14px 16px;box-sizing:border-box;' +
			'background:' + v('bg', '#fff') + ';color:' + v('fg', '#222') + ';border:1px solid ' + v('border', '#222') + ';border-radius:' + v('radius', '8px') + ';box-shadow:' + v('shadow', '0 4px 16px rgba(0,0,0,.15)') + ';' +
			'display:flex;flex-wrap:wrap;gap:12px;align-items:center;font-size:15px;line-height:1.45;text-align:left}' +
			'#consent-kit[hidden]{display:none}' +
			'#consent-kit p{margin:0;flex:1 1 320px;color:inherit;font-size:inherit}' +
			'#consent-kit a{color:' + v('link', v('fg', '#222')) + ';text-decoration:underline}' +
			'#consent-kit .ck-buttons{display:flex;gap:8px}' +
			'#consent-kit button{font:inherit;margin:0;padding:8px 18px;border:1px solid ' + v('button', v('fg', '#222')) + ';border-radius:' + v('buttonRadius', '6px') + ';cursor:pointer;background:' + v('buttonBg', '#fff') + ';color:' + v('buttonText', v('button', v('fg', '#222'))) + '}' +
			'#consent-kit button:hover{background:' + v('buttonHoverBg', v('buttonBg', '#fff')) + ';color:' + v('buttonHoverFg', v('button', v('fg', '#222'))) + '}' +
			'#consent-kit button:focus-visible{outline:2px solid ' + v('button', v('fg', '#222')) + ';outline-offset:2px}' +
			(hide ? hide + '{display:none!important}' : '');
	}

	var box = null;
	var lang = pickLang();

	function show(open) {
		if (!box) { return; }
		box.hidden = !open;
		d.documentElement.classList.toggle('ck-open', open);
	}

	function choose(choice) {
		var id = (saved && saved.id) || newId();
		saved = { choice: choice, id: id, version: VERSION };
		current = choice;
		remember(choice, id);
		var update = {};
		GRANT.forEach(function (s) { update[s] = choice; });
		w.gtag('consent', 'update', update);
		if (choice === 'granted') { runDeferred(); } else { clearCookies(); }
		show(false);
		log(choice, id, lang);
		listeners.forEach(function (fn) { attempt(function () { fn(choice); }); });
		attempt(function () { d.dispatchEvent(new CustomEvent('consentkit:change', { detail: { choice: choice } })); });
	}

	function build() {
		var t = (cfg.texts || {})[lang] || FALLBACK;
		var links = cfg.links || {};
		var href = links[lang] || links[cfg.defaultLang] || links[Object.keys(links)[0]];

		var style = d.createElement('style');
		style.id = 'consent-kit-css';
		style.textContent = css();
		d.head.appendChild(style);

		box = d.createElement('div');
		box.id = 'consent-kit';
		box.setAttribute('role', 'dialog');
		box.setAttribute('aria-live', 'polite');
		box.setAttribute('aria-label', t.label || FALLBACK.label);
		box.hidden = true;

		var p = d.createElement('p');
		p.appendChild(d.createTextNode((t.message || FALLBACK.message) + (href ? ' ' : '')));
		if (href) {
			var a = d.createElement('a');
			a.href = href;
			a.textContent = t.link || FALLBACK.link;
			p.appendChild(a);
		}
		var buttons = d.createElement('div');
		buttons.className = 'ck-buttons';
		[['reject', 'denied'], ['accept', 'granted']].forEach(function (b) {
			var btn = d.createElement('button');
			btn.type = 'button';
			btn.id = 'ck-' + b[0];
			btn.textContent = t[b[0]] || FALLBACK[b[0]];
			btn.addEventListener('click', function () { choose(b[1]); });
			buttons.appendChild(btn);
		});
		box.appendChild(p);
		box.appendChild(buttons);
		d.body.appendChild(box);

		// Any link to #cookie-settings reopens the banner so visitors can change their choice.
		d.addEventListener('click', function (e) {
			var link = e.target.closest ? e.target.closest('a[href$="#cookie-settings"]') : null;
			if (link) { e.preventDefault(); show(true); }
		});

		if (current === 'granted') { runDeferred(); }
		if (!current && !gpc) { show(true); }
	}

	w.ConsentKit = {
		get: function () { return current; },
		open: function () { show(true); },
		on: function (fn) { if (typeof fn === 'function') { listeners.push(fn); } },
		version: VERSION
	};

	if (d.readyState === 'loading') {
		d.addEventListener('DOMContentLoaded', build);
	} else {
		build();
	}
})(window, document);
