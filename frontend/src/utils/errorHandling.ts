/**
 * Utility functions for handling API errors with user-friendly messages
 */

interface ApiError {
  response?: {
    status?: number;
    data?: {
      detail?: unknown;
    };
  };
  message?: string;
}

/**
 * Turn a FastAPI `detail` into one readable string, or null if it has none.
 * HTTPException gives a string, but request validation (422) gives a list of
 * {loc, msg, type} objects, e.g. when a chat message is over
 * CHAT_MAX_CONTENT_CHARS. Passing that list on as-is left the user with a
 * generic "Please try again" on every retry.
 */
export function formatApiDetail(detail: unknown): string | null {
  if (typeof detail === 'string') return detail || null;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object' && typeof (item as { msg?: unknown }).msg === 'string') {
          // Pydantic prefixes custom validator errors with "Value error, ".
          return (item as { msg: string }).msg.replace(/^Value error, /, '');
        }
        return '';
      })
      .filter((m) => m);
    return parts.length > 0 ? Array.from(new Set(parts)).join('; ') : null;
  }
  return null;
}

/**
 * Extract a user-friendly error message from an API error
 * Handles 402 (insufficient tokens) with special messaging
 */
export function getErrorMessage(error: unknown, defaultMessage = 'An error occurred. Please try again.'): string {
  // chatApi.streamMessage uses fetch, not axios, and reports errors as a plain
  // string (the backend detail, or "HTTP <status>" when there is none). A bare
  // status code means nothing to the user, so only show strings with words.
  if (typeof error === 'string') {
    return error && !/^HTTP \d+$/.test(error) ? error : defaultMessage;
  }

  const apiError = error as ApiError;

  // Handle 402 Payment Required (insufficient tokens)
  if (apiError.response?.status === 402) {
    const detail = formatApiDetail(apiError.response?.data?.detail);
    
    // If backend provides a detailed message, use it
    if (detail) {
      return detail;
    }
    
    // Fallback message for 402 errors
    return 'Insufficient DECK coins. Please purchase more tokens to continue.';
  }
  
  // Handle 401 Unauthorized
  if (apiError.response?.status === 401) {
    return 'You must be signed in to perform this action.';
  }
  
  // Extract detail from response
  const detail = formatApiDetail(apiError.response?.data?.detail);
  
  if (detail) {
    return detail;
  }
  
  // Fallback to error message or default
  return apiError.message || defaultMessage;
}

/**
 * Check if an error is due to insufficient tokens (402)
 */
export function isInsufficientTokensError(error: unknown): boolean {
  const apiError = error as ApiError;
  return apiError.response?.status === 402;
}

/**
 * Check if an error is due to authentication (401)
 */
export function isAuthenticationError(error: unknown): boolean {
  const apiError = error as ApiError;
  return apiError.response?.status === 401;
}

/**
 * Get a user-friendly message for insufficient tokens with context
 */
export function getInsufficientTokensMessage(context: 'chat' | 'report' | 'brief' | 'general' = 'general'): string {
  const messages = {
    chat: 'Insufficient DECK coins to continue chatting. Please purchase more tokens.',
    report: 'Insufficient DECK coins to create a report. You need 200 tokens to generate a stock analysis report.',
    brief: 'Insufficient DECK coins to create a brief. Please purchase more tokens.',
    general: 'Insufficient DECK coins. Please purchase more tokens to continue.',
  };
  
  return messages[context];
}

// Made with Bob
