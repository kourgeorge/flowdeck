/**
 * App-wide config. Website name can be set via VITE_APP_NAME (e.g. in .env).
 */
export const APP_NAME = import.meta.env.VITE_APP_NAME ?? 'Flowdeck';
export const LOGO_PATH = '/logo.svg';
export const SITE_URL = (import.meta.env.VITE_SITE_URL ?? 'https://flowdeck.biz').replace(/\/$/, '');
export const DEFAULT_SEO_DESCRIPTION = 'Flowdeck is an AI-powered stock research platform with live market data, multi-agent analysis, portfolio monitoring, and conversational investment copilots.';
export const DEFAULT_OG_IMAGE = `${SITE_URL}/logo.svg`;

/**
 * Trading Copilot brand name. Change VITE_COPILOT_NAME in .env to rename it everywhere.
 * The concept is "Trading Copilot"; this is the product name shown in the UI.
 */
export const COPILOT_NAME = import.meta.env.VITE_COPILOT_NAME ?? 'Ted';
