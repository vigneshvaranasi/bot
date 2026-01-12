/**
 * Conditional logging utility that only logs in development mode.
 *
 * Usage:
 *   import { logger } from '../utils/logger';
 *   logger.debug('Debug message', { data });
 *   logger.info('Info message');
 *   logger.warn('Warning message');
 *   logger.error('Error message', error);
 */

const isDev = import.meta.env.DEV;

export const logger = {
  /**
   * Debug level - only logs in development, for verbose debugging info
   */
  debug: (...args: unknown[]): void => {
    if (isDev) {
      console.debug('[DEBUG]', ...args);
    }
  },

  /**
   * Info level - only logs in development, for general information
   */
  info: (...args: unknown[]): void => {
    if (isDev) {
      console.info('[INFO]', ...args);
    }
  },

  /**
   * Warn level - always logs, for warnings that should be investigated
   */
  warn: (...args: unknown[]): void => {
    console.warn('[WARN]', ...args);
  },

  /**
   * Error level - always logs, for errors that need attention
   */
  error: (...args: unknown[]): void => {
    console.error('[ERROR]', ...args);
  },
};

export default logger;
