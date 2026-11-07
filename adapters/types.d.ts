// Types for Consent Kit's settings. The same shape is published as schema/config.schema.json.

export type ConsentChoice = "granted" | "denied";

export type ConsentSignal = "ad_storage" | "ad_user_data" | "ad_personalization" | "analytics_storage";

export interface ConsentTexts {
  /** Banner sentence. Say which tools set cookies and that they only run after Accept. */
  message: string;
  accept: string;
  reject: string;
  /** Text of the link to the privacy or cookie policy. */
  link: string;
  /** Accessible name of the banner. */
  label: string;
}

export interface ConsentTheme {
  bg?: string;
  fg?: string;
  border?: string;
  link?: string;
  /** Button outline and text colour. */
  button?: string;
  /** Button text colour when `button` is too faint for text. */
  buttonText?: string;
  buttonBg?: string;
  buttonHoverBg?: string;
  buttonHoverFg?: string;
  radius?: string;
  buttonRadius?: string;
  shadow?: string;
  maxWidth?: string;
}

export interface ConsentKitConfig {
  /** Host name recorded in the consent log. */
  site?: string;
  /** Name of the cookie that stores the choice. Changing it loses everyone's choice. */
  cookie: string;
  /** Policy version. Raise it to ask every visitor again. */
  version: number;
  /** How long a choice lasts, 1 to 395 days. Default 180. */
  maxAgeDays?: number;
  /** Consent Mode signals granted on Accept. Default ["analytics_storage"]. */
  grant?: ConsentSignal[];
  /** Cookie names or prefixes deleted on Reject. Default ["_ga"]. */
  clearCookies?: string[];
  /** Language whose texts to show when the page language has none. */
  defaultLang?: string;
  /** Force a language; otherwise <html lang> is used. */
  lang?: string;
  /** Banner wording per two-letter language. */
  texts: Record<string, ConsentTexts>;
  /** Policy link per language. */
  links?: Record<string, string>;
  theme?: ConsentTheme;
  zIndex?: number;
  /** CSS selectors hidden while the banner is open, for example a floating chat button. */
  hideWhileOpen?: string[];
  /** Treat the Global Privacy Control signal as Reject when there is no choice yet. Default true. Never read as Accept. */
  respectGpc?: boolean;
  /** Where each choice is POSTed for the consent log (a Consent Kit WordPress site, or your own endpoint). */
  logEndpoint?: string;
}

export interface ConsentKitApi {
  get(): ConsentChoice | null;
  open(): void;
  on(fn: (choice: ConsentChoice) => void): void;
  version: number;
}

declare global {
  interface Window {
    ConsentKit?: ConsentKitApi;
    ConsentKitConfig?: ConsentKitConfig;
  }
  interface DocumentEventMap {
    "consentkit:change": CustomEvent<{ choice: ConsentChoice }>;
  }
}
