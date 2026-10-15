/**
 * Retry logic per KONNECT Architecture Spec (Section 2 & 5):
 * - Exponential backoff: baseDelay * 2^attempt + jitter
 * - Max 5 attempts
 * - Protects against thundering-herd retries and transient network failures
 */
async function withExponentialBackoff(
  fn,
  {
    maxAttempts = 5,
    baseDelayMs = 500,
    maxDelayMs = 10000,
    retryableStatusCodes = [408, 429, 500, 502, 503, 504],
    operationName = "Operation",
  } = {}
) {
  let attempt = 0;

  while (attempt < maxAttempts) {
    try {
      return await fn(attempt);
    } catch (error) {
      attempt++;

      const status = error?.response?.status;
      const isNetworkError = !error?.response && error?.code;
      const isRetryable =
        isNetworkError || (status && retryableStatusCodes.includes(status));

      if (attempt >= maxAttempts || !isRetryable) {
        console.error(
          `[${operationName}] Failed after ${attempt} attempt(s). Error: ${error.message}`
        );
        throw error;
      }

      // Exponential backoff: baseDelay * 2^(attempt - 1) + jitter (0 - 30% of delay)
      const exponentialDelay = baseDelayMs * Math.pow(2, attempt - 1);
      const jitter = Math.random() * 0.3 * exponentialDelay;
      const delay = Math.min(exponentialDelay + jitter, maxDelayMs);

      console.warn(
        `[${operationName}] Attempt ${attempt} failed (${error.message}). Retrying in ${Math.round(
          delay
        )}ms...`
      );

      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }
}

module.exports = { withExponentialBackoff };
