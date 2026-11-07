<?php
/**
 * Plugin Name: Azvai Cookie Consent (test stand-in)
 * Description: Minimal stand-in for the per-site plugin Consent Kit replaced, used only to test that the kit pauses while it is active.
 * Version: 1.0.0
 */

defined( 'ABSPATH' ) || exit;

function azv_consent_default() {
	echo "<script id=\"azv-consent-default\">window.dataLayer = window.dataLayer || []; function gtag(){dataLayer.push(arguments);} gtag('consent', 'default', {analytics_storage: 'denied'});</script>\n";
}
add_action( 'wp_head', 'azv_consent_default', 0 );
