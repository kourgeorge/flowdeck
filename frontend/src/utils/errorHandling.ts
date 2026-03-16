/**
 * Utility functions for handling API errors with user-friendly messages
 */

interface ApiError {
  response?: {
    status?: number;
    data?: {
      detail?: string | string[];
    };
  };
  message?: string;
}

/**
 * Extract a user-friendly error message from an API error
 * Handles 402 (insufficient tokens) with special messaging
 */
export function getErrorMessage(error: unknown, defaultMessage = 'An error occurred. Please try again.'): string {
  const apiError = error as ApiError;
  
  // Handle 402 Payment Required (insufficient tokens)
  if (apiError.response?.status === 402) {
    const detail = apiError.response?.data?.detail;
    
    // If backend provides a detailed message, use it
    if (typeof detail === 'string' && detail) {
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
  const detail = apiError.response?.data?.detail;
  
  if (typeof detail === 'string' && detail) {
    return detail;
  }
  
  if (Array.isArray(detail) && detail.length > 0) {
    return String(detail[0]);
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
