/**
 * App-wide config. Website name can be set via VITE_APP_NAME (e.g. in .env).
 */
export const APP_NAME = import.meta.env.VITE_APP_NAME ?? 'Flowdeck';
export const LOGO_PATH = '/logo.png';

/**
 * Trading Copilot brand name. Change VITE_COPILOT_NAME in .env to rename it everywhere.
 * The concept is "Trading Copilot"; this is the product name shown in the UI.
 */
export const COPILOT_NAME = import.meta.env.VITE_COPILOT_NAME ?? 'Deck';
