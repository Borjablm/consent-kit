<?php
/**
 * Plugin Name: Consent Kit
 * Description: Accept/Reject cookie banner with Google Consent Mode v2, scripts held until consent, a consent log for proof, and noindex on legal pages. The same plugin runs on every site; each site's settings are stored in the database and set through the admin-only REST route consent-kit/v1/config (configure.py). Updates itself from the release manifest. Replaces Azvai, Lumination and QueCafe Cookie Consent.
 * Version: 1.0.0
 * Author: Azvai
 * Requires at least: 6.5
 * Requires PHP: 7.4
 * License: GPL-2.0-or-later
 * Update URI: https://github.com/Borjablm/consent-kit
 */

defined( 'ABSPATH' ) || exit;

const CONSENT_KIT_VERSION    = '1.0.0';
const CONSENT_KIT_DB_VERSION = '1';
const CONSENT_KIT_OPTION     = 'consent_kit_config';
if ( ! defined( 'CONSENT_KIT_UPDATE_URL' ) ) {
	define( 'CONSENT_KIT_UPDATE_URL', 'https://raw.githubusercontent.com/Borjablm/consent-kit/main/update.json' );
}

/**
 * This site's settings: the database option set through the config API. A config.json next to
 * this file only seeds the option on first activation. Without settings the kit stays silent.
 */
function consent_kit_config( $reset = false ) {
	static $cfg = null;
	if ( null === $cfg || $reset ) {
		$opt = get_option( CONSENT_KIT_OPTION );
		$cfg = apply_filters( 'consent_kit_config', is_array( $opt ) ? $opt : array() );
	}
	return $cfg;
}

/**
 * Check and clean a config before it is stored. Returns the clean array or a WP_Error listing every
 * problem. Values that reach CSS or HTML are restricted to safe characters.
 */
function consent_kit_validate( $c ) {
	$err = array();
	if ( ! is_array( $c ) ) {
		return new WP_Error( 'consent_kit_invalid', 'Config must be a JSON object.', array( 'status' => 400 ) );
	}
	$known = array( 'site', 'cookie', 'version', 'maxAgeDays', 'grant', 'clearCookies', 'defaultLang', 'texts', 'theme', 'zIndex', 'hideWhileOpen', 'wp' );
	foreach ( array_diff( array_keys( $c ), $known ) as $k ) {
		$err[] = "unknown key \"$k\"";
	}
	$out = array();

	$out['site'] = isset( $c['site'] ) ? strtolower( (string) $c['site'] ) : wp_parse_url( home_url(), PHP_URL_HOST );
	if ( ! preg_match( '/^[a-z0-9.-]{3,100}$/', $out['site'] ) ) {
		$err[] = 'site must be a host name';
	}
	$out['cookie'] = isset( $c['cookie'] ) ? (string) $c['cookie'] : '';
	if ( ! preg_match( '/^[a-z][a-z0-9_]{2,30}$/', $out['cookie'] ) ) {
		$err[] = 'cookie must be a short lowercase name';
	}
	$out['version'] = isset( $c['version'] ) && is_int( $c['version'] ) ? $c['version'] : 0;
	if ( $out['version'] < 1 || $out['version'] > 9999 ) {
		$err[] = 'version must be a whole number from 1 (raise it to ask every visitor again)';
	}
	$out['maxAgeDays'] = isset( $c['maxAgeDays'] ) ? (int) $c['maxAgeDays'] : 180;
	if ( $out['maxAgeDays'] < 1 || $out['maxAgeDays'] > 395 ) {
		$err[] = 'maxAgeDays must be 1 to 395 (13 months at most)';
	}
	$signals      = array( 'ad_storage', 'ad_user_data', 'ad_personalization', 'analytics_storage' );
	$out['grant'] = isset( $c['grant'] ) ? array_values( (array) $c['grant'] ) : array( 'analytics_storage' );
	if ( array_diff( $out['grant'], $signals ) ) {
		$err[] = 'grant may only list ' . implode( ', ', $signals );
	}
	$out['clearCookies'] = isset( $c['clearCookies'] ) ? array_values( (array) $c['clearCookies'] ) : array( '_ga' );
	foreach ( $out['clearCookies'] as $p ) {
		if ( ! is_string( $p ) || ! preg_match( '/^[A-Za-z0-9_.-]{1,40}$/', $p ) ) {
			$err[] = 'clearCookies entries must be cookie names or prefixes';
		}
	}

	$texts = isset( $c['texts'] ) && is_array( $c['texts'] ) ? $c['texts'] : array();
	if ( ! $texts ) {
		$err[] = 'texts needs at least one language';
	}
	foreach ( $texts as $lang => $t ) {
		if ( ! preg_match( '/^[a-z]{2}$/', (string) $lang ) || ! is_array( $t ) ) {
			$err[] = "texts.$lang must be a two-letter language with its strings";
			continue;
		}
		foreach ( array( 'message', 'accept', 'reject', 'link', 'label' ) as $k ) {
			if ( ! isset( $t[ $k ] ) || ! is_string( $t[ $k ] ) || '' === trim( $t[ $k ] ) ) {
				$err[] = "texts.$lang.$k is missing";
				continue;
			}
			$out['texts'][ $lang ][ $k ] = mb_substr( wp_strip_all_tags( $t[ $k ] ), 0, 600 );
		}
	}
	$out['defaultLang'] = isset( $c['defaultLang'] ) ? (string) $c['defaultLang'] : (string) array_key_first( $texts );
	if ( $texts && ! isset( $texts[ $out['defaultLang'] ] ) ) {
		$err[] = 'defaultLang has no texts';
	}

	$theme_keys   = array( 'bg', 'fg', 'border', 'link', 'button', 'buttonText', 'buttonBg', 'buttonHoverBg', 'buttonHoverFg', 'radius', 'buttonRadius', 'shadow', 'maxWidth' );
	$out['theme'] = array();
	foreach ( (array) ( $c['theme'] ?? array() ) as $k => $v ) {
		if ( ! in_array( $k, $theme_keys, true ) ) {
			$err[] = "theme.$k is not a theme setting (" . implode( ', ', $theme_keys ) . ')';
		} elseif ( ! is_string( $v ) || ! preg_match( '/^[#a-zA-Z0-9(),.%\s-]{1,80}$/', $v ) ) {
			$err[] = "theme.$k must be a plain CSS colour or size";
		} else {
			$out['theme'][ $k ] = $v;
		}
	}
	$out['zIndex']        = isset( $c['zIndex'] ) ? (int) $c['zIndex'] : 99999;
	$out['hideWhileOpen'] = array();
	foreach ( (array) ( $c['hideWhileOpen'] ?? array() ) as $sel ) {
		if ( ! is_string( $sel ) || ! preg_match( '/^[#.\w\s\[\]="\'*^$|~:>+-]{1,120}$/', $sel ) ) {
			$err[] = 'hideWhileOpen entries must be simple CSS selectors';
		} else {
			$out['hideWhileOpen'][] = $sel;
		}
	}

	$wp        = isset( $c['wp'] ) && is_array( $c['wp'] ) ? $c['wp'] : array();
	$out['wp'] = array();
	$page      = $wp['policyPage'] ?? '';
	if ( is_int( $page ) || ( is_string( $page ) && preg_match( '#^([a-z0-9/-]+|https?://\S+)$#', $page ) ) ) {
		$out['wp']['policyPage'] = $page;
	} else {
		$err[] = 'wp.policyPage must be a page ID, page slug or URL';
	}
	foreach ( array( 'block', 'legalPages', 'allowedOrigins' ) as $k ) {
		$out['wp'][ $k ] = array();
		foreach ( (array) ( $wp[ $k ] ?? array() ) as $v ) {
			if ( ! is_string( $v ) || ! preg_match( '#^[A-Za-z0-9._/:-]{2,100}$#', $v ) ) {
				$err[] = "wp.$k entries must be host names, paths or slugs";
			} else {
				$out['wp'][ $k ][] = $v;
			}
		}
	}
	$out['wp']['log']              = isset( $wp['log'] ) ? (bool) $wp['log'] : true;
	$out['wp']['logRetentionDays'] = isset( $wp['logRetentionDays'] ) ? (int) $wp['logRetentionDays'] : 1095;
	if ( $out['wp']['logRetentionDays'] < 30 || $out['wp']['logRetentionDays'] > 3650 ) {
		$err[] = 'wp.logRetentionDays must be 30 to 3650';
	}

	return $err ? new WP_Error( 'consent_kit_invalid', implode( '; ', array_unique( $err ) ), array( 'status' => 400 ) ) : $out;
}

/**
 * Clear page caches after a settings change, so visitors get the new banner straight away.
 * Returns the caches it cleared.
 */
function consent_kit_purge_page_caches() {
	global $kinsta_cache;
	$done = array();
	if ( isset( $kinsta_cache->kinsta_cache_purge ) && method_exists( $kinsta_cache->kinsta_cache_purge, 'purge_complete_caches' ) ) {
		$kinsta_cache->kinsta_cache_purge->purge_complete_caches();
		$done[] = 'kinsta';
	}
	if ( function_exists( 'rocket_clean_domain' ) ) {
		rocket_clean_domain();
		$done[] = 'wp-rocket';
	}
	if ( function_exists( 'w3tc_flush_all' ) ) {
		w3tc_flush_all();
		$done[] = 'w3tc';
	}
	if ( function_exists( 'wp_cache_clear_cache' ) ) {
		wp_cache_clear_cache();
		$done[] = 'wp-super-cache';
	}
	if ( has_action( 'litespeed_purge_all' ) ) {
		do_action( 'litespeed_purge_all' );
		$done[] = 'litespeed';
	}
	return $done;
}

function consent_kit_wp( $key, $fallback = null ) {
	$cfg = consent_kit_config();
	return isset( $cfg['wp'][ $key ] ) ? $cfg['wp'][ $key ] : $fallback;
}

function consent_kit_table() {
	global $wpdb;
	return $wpdb->prefix . 'consent_kit_log';
}

/**
 * The per-site plugins this kit replaces. If one is still active, the kit stays quiet so
 * visitors never get two banners or two consent defaults.
 */
function consent_kit_old_plugin() {
	if ( function_exists( 'azv_consent_default' ) ) {
		return 'Azvai Cookie Consent';
	}
	if ( function_exists( 'lai_consent_default' ) ) {
		return 'Lumination Cookie Consent';
	}
	if ( function_exists( 'qc_consent_page_url' ) ) {
		return 'QueCafe Cookie Consent';
	}
	return '';
}

function consent_kit_is_front_request() {
	return ! ( is_admin() || is_feed() || is_embed() || wp_doing_ajax() || wp_doing_cron() || ( defined( 'REST_REQUEST' ) && REST_REQUEST ) || is_customize_preview() );
}

/* ---------------------------------------------------------------- front end */

function consent_kit_lang() {
	if ( function_exists( 'pll_current_language' ) && pll_current_language( 'slug' ) ) {
		return pll_current_language( 'slug' );
	}
	return strtolower( substr( determine_locale(), 0, 2 ) );
}

/**
 * Policy link for the current language. wp.policyPage is a page ID (Polylang translation used
 * when there is one), a page slug, or a full URL.
 */
function consent_kit_policy_url( $lang ) {
	$page = consent_kit_wp( 'policyPage' );
	if ( is_int( $page ) || ctype_digit( (string) $page ) ) {
		$id = (int) $page;
		if ( function_exists( 'pll_get_post' ) ) {
			$tr = pll_get_post( $id, $lang );
			$id = $tr ? $tr : $id;
		}
		$url = get_permalink( $id );
		return $url ? $url : '';
	}
	if ( is_string( $page ) && '' !== $page ) {
		if ( preg_match( '#^https?://#', $page ) ) {
			return $page;
		}
		$p = get_page_by_path( $page );
		return $p ? get_permalink( $p ) : home_url( '/' . trim( $page, '/' ) . '/' );
	}
	return '';
}

/**
 * The config the browser sees: everything except the "wp" block, plus language, policy link
 * and log endpoint resolved for this page.
 */
function consent_kit_js_config() {
	$cfg = consent_kit_config();
	unset( $cfg['wp'] );
	$lang         = consent_kit_lang();
	$cfg['lang']  = $lang;
	$url          = consent_kit_policy_url( $lang );
	$cfg['links'] = $url ? array( $lang => $url ) : array();
	if ( empty( $cfg['site'] ) ) {
		$cfg['site'] = wp_parse_url( home_url(), PHP_URL_HOST );
	}
	if ( consent_kit_wp( 'log', true ) ) {
		$cfg['logEndpoint'] = rest_url( 'consent-kit/v1/log' );
	}
	return $cfg;
}

function consent_kit_print() {
	if ( ! consent_kit_is_front_request() ) {
		return;
	}
	$js = (string) file_get_contents( __DIR__ . '/consent-kit.js' ); // phpcs:ignore WordPress.WP.AlternativeFunctions.file_get_contents_file_get_contents -- reads this plugin's own file, not a URL.
	echo "<script id=\"consent-kit-js\">\nwindow.ConsentKitConfig = " . wp_json_encode( consent_kit_js_config(), JSON_HEX_TAG | JSON_HEX_AMP | JSON_UNESCAPED_SLASHES ) . ";\n" . $js . "</script>\n"; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- our own script; the JSON escapes < > & so no tag can close early.
}

/**
 * Hold back third-party scripts until Accept. Any <script> whose src or inline code contains one
 * of wp.block is turned into type="text/plain" data-consent="granted" (consent-kit.js runs it after
 * Accept), and preload/prefetch hints for those hosts are dropped. JSON-LD and other data scripts
 * are left alone. If a regex fails on a huge page, the page is sent unchanged.
 */
function consent_kit_filter_html( $html ) {
	$block = array_values( array_filter( (array) consent_kit_wp( 'block', array() ), 'is_string' ) );
	if ( ! $block || ! is_string( $html ) || '' === $html ) {
		return $html;
	}
	$contains = function ( $haystack ) use ( $block ) {
		foreach ( $block as $needle ) {
			if ( '' !== $needle && false !== strpos( $haystack, $needle ) ) {
				return true;
			}
		}
		return false;
	};
	if ( ! $contains( $html ) ) {
		return $html;
	}

	$out = preg_replace_callback(
		'#<link\b[^>]*>#i',
		function ( $m ) use ( $contains ) {
			if ( preg_match( '#\brel\s*=\s*["\']?[^"\'>]*\b(preload|modulepreload|prefetch|preconnect|dns-prefetch)\b#i', $m[0] ) && $contains( $m[0] ) ) {
				return '';
			}
			return $m[0];
		},
		$html
	);
	if ( null === $out ) {
		return $html;
	}

	$out2 = preg_replace_callback(
		'#<script\b([^>]*)>(.*?)</script>#is',
		function ( $m ) use ( $contains ) {
			$attrs = $m[1];
			$body  = $m[2];
			if ( false !== strpos( $attrs, 'consent-kit' ) || ! ( $contains( $attrs ) || $contains( $body ) ) ) {
				return $m[0];
			}
			$type = '';
			if ( preg_match( '#\s+type\s*=\s*(["\']?)([^"\'\s>]+)\1#i', $attrs, $t ) ) {
				$type  = strtolower( $t[2] );
				$attrs = str_replace( $t[0], '', $attrs );
			}
			if ( '' !== $type && ! in_array( $type, array( 'text/javascript', 'application/javascript', 'module' ), true ) ) {
				return $m[0];
			}
			$keep = 'module' === $type ? ' data-type="module"' : '';
			return '<script type="text/plain" data-consent="granted"' . $keep . $attrs . '>' . $body . '</script>';
		},
		$out
	);
	return null === $out2 ? $out : $out2;
}

/* ---------------------------------------------------------------- legal pages */

function consent_kit_is_legal_page() {
	$pages = (array) consent_kit_wp( 'legalPages', array() );
	return $pages && is_page( $pages );
}

/* ---------------------------------------------------------------- consent log */

function consent_kit_install() {
	global $wpdb;
	require_once ABSPATH . 'wp-admin/includes/upgrade.php';
	$table   = consent_kit_table();
	$charset = $wpdb->get_charset_collate();
	dbDelta(
		"CREATE TABLE {$table} (
  id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  created_at datetime NOT NULL,
  consent_id char(20) NOT NULL,
  choice varchar(8) NOT NULL,
  policy_version smallint(5) unsigned NOT NULL,
  site varchar(100) NOT NULL DEFAULT '',
  lang varchar(5) NOT NULL DEFAULT '',
  path varchar(255) NOT NULL DEFAULT '',
  PRIMARY KEY  (id),
  KEY consent_id (consent_id),
  KEY created_at (created_at)
) {$charset};"
	);
	update_option( 'consent_kit_db_version', CONSENT_KIT_DB_VERSION, false );
	// Seed settings from a config.json shipped next to the plugin, only if none are stored yet.
	$file = __DIR__ . '/config.json';
	if ( ! get_option( CONSENT_KIT_OPTION ) && is_readable( $file ) ) {
		$clean = consent_kit_validate( json_decode( (string) file_get_contents( $file ), true ) ); // phpcs:ignore WordPress.WP.AlternativeFunctions.file_get_contents_file_get_contents -- reads this plugin's own file, not a URL.
		if ( ! is_wp_error( $clean ) ) {
			update_option( CONSENT_KIT_OPTION, $clean, true );
			consent_kit_config( true );
		}
	}
	if ( ! wp_next_scheduled( 'consent_kit_purge' ) ) {
		wp_schedule_event( time() + HOUR_IN_SECONDS, 'daily', 'consent_kit_purge' );
	}
}
register_activation_hook( __FILE__, 'consent_kit_install' );

register_deactivation_hook(
	__FILE__,
	function () {
		wp_clear_scheduled_hook( 'consent_kit_purge' );
	}
);

/**
 * Hosts allowed to log: this site plus wp.allowedOrigins (other sites using the standalone
 * consent-kit.js with this site's endpoint).
 */
function consent_kit_allowed_hosts() {
	$hosts = array( wp_parse_url( home_url(), PHP_URL_HOST ) );
	foreach ( (array) consent_kit_wp( 'allowedOrigins', array() ) as $o ) {
		$h = wp_parse_url( ( false === strpos( $o, '://' ) ? 'https://' : '' ) . $o, PHP_URL_HOST );
		if ( $h ) {
			$hosts[] = $h;
		}
	}
	return array_unique( array_map( 'strtolower', array_filter( $hosts ) ) );
}

function consent_kit_rest_log( WP_REST_Request $request ) {
	global $wpdb;
	$data = json_decode( $request->get_body(), true );
	if ( ! is_array( $data ) ) {
		return new WP_REST_Response( array( 'ok' => false ), 400 );
	}

	$origin = $request->get_header( 'origin' );
	$host   = $origin ? strtolower( (string) wp_parse_url( $origin, PHP_URL_HOST ) ) : strtolower( (string) wp_parse_url( home_url(), PHP_URL_HOST ) );
	if ( ! in_array( $host, consent_kit_allowed_hosts(), true ) ) {
		return new WP_REST_Response( array( 'ok' => false ), 403 );
	}

	$id      = isset( $data['id'] ) ? (string) $data['id'] : '';
	$choice  = isset( $data['choice'] ) ? (string) $data['choice'] : '';
	$version = isset( $data['version'] ) ? (int) $data['version'] : 0;
	if ( ! preg_match( '/^[a-f0-9]{20}$/', $id ) || ! in_array( $choice, array( 'granted', 'denied' ), true ) || $version < 1 || $version > 9999 ) {
		return new WP_REST_Response( array( 'ok' => false ), 400 );
	}

	// Rate limit per visitor address. The address is only hashed for the limit key and never stored.
	$ip  = isset( $_SERVER['REMOTE_ADDR'] ) ? (string) $_SERVER['REMOTE_ADDR'] : '';
	$key = 'consent_kit_rl_' . substr( hash_hmac( 'sha256', $ip, wp_salt( 'nonce' ) ), 0, 20 );
	$n   = (int) get_transient( $key );
	if ( $n >= 30 ) {
		return new WP_REST_Response( array( 'ok' => false ), 429 );
	}
	set_transient( $key, $n + 1, HOUR_IN_SECONDS );

	if ( get_option( 'consent_kit_db_version' ) !== CONSENT_KIT_DB_VERSION ) {
		consent_kit_install();
	}
	$lang     = isset( $data['lang'] ) ? substr( preg_replace( '/[^a-z-]/', '', strtolower( (string) $data['lang'] ) ), 0, 5 ) : '';
	$path     = isset( $data['path'] ) ? substr( esc_url_raw( '/' . ltrim( (string) $data['path'], '/' ) ), 0, 255 ) : '';
	$ok       = $wpdb->insert(
		consent_kit_table(),
		array(
			'created_at'     => current_time( 'mysql', true ),
			'consent_id'     => $id,
			'choice'         => $choice,
			'policy_version' => $version,
			'site'           => substr( $host, 0, 100 ),
			'lang'           => $lang,
			'path'           => $path,
		),
		array( '%s', '%s', '%s', '%d', '%s', '%s', '%s' )
	);
	$response = new WP_REST_Response( array( 'ok' => (bool) $ok ), $ok ? 201 : 500 );
	$response->header( 'Cache-Control', 'no-store' );
	return $response;
}

add_action(
	'consent_kit_purge',
	function () {
		global $wpdb;
		$days = max( 30, (int) consent_kit_wp( 'logRetentionDays', 1095 ) );
		$wpdb->query( $wpdb->prepare( 'DELETE FROM ' . consent_kit_table() . ' WHERE created_at < %s', gmdate( 'Y-m-d H:i:s', time() - $days * DAY_IN_SECONDS ) ) ); // phpcs:ignore WordPress.DB.PreparedSQL -- the only interpolation is the table name from $wpdb->prefix; values go through prepare().
	}
);

/* ---------------------------------------------------------------- admin: Tools > Consent log */

function consent_kit_admin_page() {
	global $wpdb;
	$table = consent_kit_table();
	$since = gmdate( 'Y-m-d H:i:s', time() - 30 * DAY_IN_SECONDS );
	$rows  = $wpdb->get_results( $wpdb->prepare( "SELECT choice, COUNT(*) AS n FROM {$table} WHERE created_at >= %s GROUP BY choice", $since ), OBJECT_K ); // phpcs:ignore WordPress.DB.PreparedSQL -- the only interpolation is the table name from $wpdb->prefix; values go through prepare().
	$yes   = isset( $rows['granted'] ) ? (int) $rows['granted']->n : 0;
	$no    = isset( $rows['denied'] ) ? (int) $rows['denied']->n : 0;
	$find  = isset( $_GET['consent_id'] ) ? preg_replace( '/[^a-f0-9]/', '', strtolower( (string) wp_unslash( $_GET['consent_id'] ) ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Recommended -- read-only lookup on an admin-only page; it changes nothing.
	?>
<div class="wrap">
	<h1>Consent log</h1>
	<p>Every Accept or Reject is stored with a random consent ID (also kept in the visitor's <code><?php echo esc_html( consent_kit_config()['cookie'] ?? '' ); ?></code> cookie), the policy version, page path and time. No IP address or other personal data is stored. Rows older than <?php echo (int) consent_kit_wp( 'logRetentionDays', 1095 ); ?> days are deleted daily.</p>
	<h2>Last 30 days</h2>
	<p>Accepted: <strong><?php echo (int) $yes; ?></strong> &nbsp; Rejected: <strong><?php echo (int) $no; ?></strong><?php echo $yes + $no ? ' &nbsp; Acceptance rate: <strong>' . esc_html( round( 100 * $yes / ( $yes + $no ) ) ) . '%</strong>' : ''; ?></p>
	<h2>Look up a consent ID</h2>
	<form method="get">
		<input type="hidden" name="page" value="consent-kit-log">
		<input type="text" name="consent_id" value="<?php echo esc_attr( $find ); ?>" size="24" placeholder="20 hex characters">
		<?php submit_button( 'Look up', 'secondary', '', false ); ?>
	</form>
	<?php
	if ( $find ) {
		$hits = $wpdb->get_results( $wpdb->prepare( "SELECT created_at, choice, policy_version, site, lang, path FROM {$table} WHERE consent_id = %s ORDER BY id", $find ) ); // phpcs:ignore WordPress.DB.PreparedSQL -- the only interpolation is the table name from $wpdb->prefix; values go through prepare().
		echo '<table class="widefat striped" style="max-width:900px;margin-top:12px"><thead><tr><th>Time (UTC)</th><th>Choice</th><th>Policy version</th><th>Site</th><th>Lang</th><th>Page</th></tr></thead><tbody>';
		foreach ( $hits as $h ) {
			echo '<tr><td>' . esc_html( $h->created_at ) . '</td><td>' . esc_html( $h->choice ) . '</td><td>' . (int) $h->policy_version . '</td><td>' . esc_html( $h->site ) . '</td><td>' . esc_html( $h->lang ) . '</td><td>' . esc_html( $h->path ) . '</td></tr>';
		}
		if ( ! $hits ) {
			echo '<tr><td colspan="6">No records for this ID.</td></tr>';
		}
		echo '</tbody></table>';
	}
	?>
	<h2>Export</h2>
	<p><a class="button" href="<?php echo esc_url( wp_nonce_url( admin_url( 'admin-post.php?action=consent_kit_export' ), 'consent_kit_export' ) ); ?>">Download CSV</a></p>
</div>
	<?php
}

add_action(
	'admin_post_consent_kit_export',
	function () {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_die( 'Not allowed.' );
		}
		check_admin_referer( 'consent_kit_export' );
		global $wpdb;
		nocache_headers();
		header( 'Content-Type: text/csv; charset=utf-8' );
		header( 'Content-Disposition: attachment; filename=consent-log-' . gmdate( 'Y-m-d' ) . '.csv' );
		$out = fopen( 'php://output', 'w' );
		fputcsv( $out, array( 'created_at_utc', 'consent_id', 'choice', 'policy_version', 'site', 'lang', 'path' ) );
		$last = 0;
		do {
			$rows = $wpdb->get_results( $wpdb->prepare( 'SELECT id, created_at, consent_id, choice, policy_version, site, lang, path FROM ' . consent_kit_table() . ' WHERE id > %d ORDER BY id LIMIT 5000', $last ), ARRAY_A ); // phpcs:ignore WordPress.DB.PreparedSQL -- the only interpolation is the table name from $wpdb->prefix; values go through prepare().
			foreach ( $rows as $r ) {
				$last = (int) $r['id'];
				unset( $r['id'] );
				fputcsv( $out, $r );
			}
			$batch = count( $rows );
		} while ( 5000 === $batch );
		fclose( $out ); // phpcs:ignore WordPress.WP.AlternativeFunctions.file_system_operations_fclose -- closes php://output, not a file.
		exit;
	}
);

/* ---------------------------------------------------------------- config API (admins only) */

function consent_kit_rest_config_get() {
	return new WP_REST_Response(
		array(
			'plugin_version' => CONSENT_KIT_VERSION,
			'config'         => get_option( CONSENT_KIT_OPTION ) ? get_option( CONSENT_KIT_OPTION ) : null,
			'paused_by'      => consent_kit_old_plugin(),
		)
	);
}

function consent_kit_rest_config_put( WP_REST_Request $request ) {
	$clean = consent_kit_validate( json_decode( $request->get_body(), true ) );
	if ( is_wp_error( $clean ) ) {
		return $clean;
	}
	update_option( CONSENT_KIT_OPTION, $clean, true );
	consent_kit_config( true );
	return new WP_REST_Response(
		array(
			'saved'          => true,
			'config'         => $clean,
			'caches_cleared' => consent_kit_purge_page_caches(),
		)
	);
}

add_action(
	'rest_api_init',
	function () {
		register_rest_route(
			'consent-kit/v1',
			'/config',
			array(
				array(
					'methods'             => 'GET',
					'callback'            => 'consent_kit_rest_config_get',
					'permission_callback' => function () {
						return current_user_can( 'manage_options' );
					},
				),
				array(
					'methods'             => 'PUT, POST',
					'callback'            => 'consent_kit_rest_config_put',
					'permission_callback' => function () {
						return current_user_can( 'manage_options' );
					},
				),
			)
		);
	}
);

/* ---------------------------------------------------------------- updates */

/**
 * Fetch the release manifest (cached 6 hours, 1 hour after a failure):
 * {"version": "1.0.1", "package": "<zip url>", "url": "<repo url>", "requires": "6.5", "requires_php": "7.4", "tested": "6.8"}
 */
function consent_kit_manifest() {
	$m = get_site_transient( 'consent_kit_manifest' );
	if ( false === $m ) {
		$r = wp_remote_get( CONSENT_KIT_UPDATE_URL, array( 'timeout' => 10 ) );
		$m = ( ! is_wp_error( $r ) && 200 === wp_remote_retrieve_response_code( $r ) ) ? json_decode( wp_remote_retrieve_body( $r ), true ) : null;
		$m = ( is_array( $m ) && ! empty( $m['version'] ) && ! empty( $m['package'] ) ) ? $m : array();
		set_site_transient( 'consent_kit_manifest', $m, $m ? 6 * HOUR_IN_SECONDS : HOUR_IN_SECONDS );
	}
	return $m;
}

// WordPress asks the host in "Update URI" (github.com) for updates to this plugin.
add_filter(
	'update_plugins_github.com',
	function ( $update, $plugin_data, $plugin_file ) {
		if ( plugin_basename( __FILE__ ) !== $plugin_file ) {
			return $update;
		}
		$m = consent_kit_manifest();
		if ( ! $m ) {
			return $update;
		}
		return array(
			'slug'         => 'consent-kit',
			'version'      => $m['version'],
			'url'          => $m['url'] ?? 'https://github.com/Borjablm/consent-kit',
			'package'      => $m['package'],
			'requires'     => $m['requires'] ?? '6.5',
			'requires_php' => $m['requires_php'] ?? '7.4',
			'tested'       => $m['tested'] ?? '',
		);
	},
	10,
	3
);

// Releases go live on every site without a click.
add_filter(
	'auto_update_plugin',
	function ( $update, $item ) {
		return ( isset( $item->plugin ) && plugin_basename( __FILE__ ) === $item->plugin ) ? true : $update;
	},
	10,
	2
);

// The plugin row shows that this plugin updates itself.
add_filter(
	'plugin_auto_update_setting_html',
	function ( $html, $plugin_file ) {
		return plugin_basename( __FILE__ ) === $plugin_file ? 'Updates itself from github.com/Borjablm/consent-kit' : $html;
	},
	10,
	2
);

/* ---------------------------------------------------------------- wiring */

add_action(
	'plugins_loaded',
	function () {
		$old = consent_kit_old_plugin();
		if ( $old ) {
			add_action(
				'admin_notices',
				function () use ( $old ) {
					echo '<div class="notice notice-warning"><p><strong>Consent Kit is paused:</strong> deactivate ' . esc_html( $old ) . ' first, so visitors do not get two cookie banners.</p></div>';
				}
			);
			return;
		}
		if ( ! consent_kit_config() ) {
			add_action(
				'admin_notices',
				function () {
					echo '<div class="notice notice-warning"><p><strong>Consent Kit</strong> is installed but has no settings for this site yet, so no banner is shown. Push them with configure.py (consent-kit/v1/config).</p></div>';
				}
			);
			return;
		}

		// The consent default has to come before any Google tag in <head>.
		add_action( 'wp_head', 'consent_kit_print', -1000 );

		add_action(
			'template_redirect',
			function () {
				if ( consent_kit_wp( 'block' ) && consent_kit_is_front_request() ) {
					ob_start( 'consent_kit_filter_html' );
				}
			},
			0
		);

		add_filter(
			'wpseo_robots',
			function ( $robots ) {
				return consent_kit_is_legal_page() ? 'noindex, follow' : $robots;
			}
		);
		add_filter(
			'wp_robots',
			function ( $robots ) {
				if ( consent_kit_is_legal_page() ) {
					unset( $robots['index'] );
					$robots['noindex'] = true;
					$robots['follow']  = true;
				}
				return $robots;
			}
		);
		add_filter(
			'wpseo_exclude_from_sitemap_by_post_ids',
			function ( $ids ) {
				foreach ( (array) consent_kit_wp( 'legalPages', array() ) as $slug ) {
					$p = get_page_by_path( $slug );
					if ( $p ) {
						$ids[] = $p->ID;
					}
				}
				return $ids;
			}
		);

		if ( consent_kit_wp( 'log', true ) ) {
			add_action(
				'rest_api_init',
				function () {
					register_rest_route(
						'consent-kit/v1',
						'/log',
						array(
							'methods'             => 'POST',
							'callback'            => 'consent_kit_rest_log',
							'permission_callback' => '__return_true',
						)
					);
				}
			);
			add_action(
				'admin_menu',
				function () {
					add_management_page( 'Consent log', 'Consent log', 'manage_options', 'consent-kit-log', 'consent_kit_admin_page' );
				}
			);
			add_action(
				'admin_init',
				function () {
					if ( get_option( 'consent_kit_db_version' ) !== CONSENT_KIT_DB_VERSION ) {
						consent_kit_install();
					}
				}
			);
		}
	}
);
