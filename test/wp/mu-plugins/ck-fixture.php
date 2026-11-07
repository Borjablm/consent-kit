<?php
/**
 * Test fixture: prints what real sites print in <head>, so the kit's output buffer has work to do.
 * Only used by test_wp.py in the local Docker WordPress.
 */
add_action(
	'wp_head',
	function () {
		?>
<link rel="preload" href="https://wct-3.com/wct.js?type=session" as="script">
<link rel="dns-prefetch" href="//wct-3.com">
<link rel="preload" href="/wp-includes/css/dist/block-library/style.min.css" as="style">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-TEST" id="google_gtagjs-js"></script>
<script id="google_gtagjs-js-after">window.dataLayer = window.dataLayer || [];function gtag(){dataLayer.push(arguments);} gtag("js", new Date()); gtag("config", "G-TEST");</script>
<script>
	(function(w, c, t, u) { w._wct = w._wct || {}; w._wct = u; var s = c.createElement(t);
	s.type = 'text/javascript'; s.async = true; s.src = 'https://wct-3.com/wct.js?type=session'; var r = c.getElementsByTagName(t)[0];
	r.parentNode.insertBefore(s, r); }(window, document, 'script', {'uid' : 'TEST', 'proxy' : 'https://wct-3.com'}));
</script>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebSite","url":"https://wct-3.com/not-a-script"}</script>
<script type="module" src="https://wct-3.com/module.js"></script>
<script>window.__untouched = 1;</script>
		<?php
	},
	5
);

// The update test serves its release from the host machine, which WordPress treats as internal.
add_filter( 'http_request_host_is_external', '__return_true' );

add_action(
	'wp_footer',
	function () {
		echo '<p><a href="#cookie-settings" id="reopen">Configurar cookies</a></p><aside id="qc-ads-bar">ads</aside>';
	}
);
