/**
 * Backend URL configuration.
 *
 * Set VITE_BE_URL in your .env file to override the default.
 * Example: VITE_BE_URL=https://api.production.com
 */
export const BE_URL = import.meta.env.VITE_BE_URL || 'http://localhost:8000';
