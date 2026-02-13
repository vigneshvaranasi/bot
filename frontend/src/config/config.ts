/**
 * Backend URL configuration.
 *
 * Set VITE_BE_URL in your .env file to override the default.
 * Example: VITE_BE_URL=https://api.production.com
 *
 * In production, this should be set via Docker build args.
 */
const defaultBeUrl = import.meta.env.DEV ? 'http://localhost:8000' : '';
export const BE_URL = import.meta.env.VITE_BE_URL || defaultBeUrl;

// Validate that BE_URL is set in production
if (!import.meta.env.DEV && !BE_URL) {
  console.error('VITE_BE_URL must be set in production builds');
}
