export type SnowflakeErrorCode = 'INVALID_ID' | 'INVALID_PARTS' | 'CLOSED' | 'STATE_MISSING' | 'RECOVERY_WAIT' | 'INVALID_OPTIONS' | 'STATE_CORRUPT' | 'STATE_IO' | 'WORKER_MISMATCH' | 'STATE_LOCKED' | 'LOCK_LOST' | 'SEQUENCE_EXHAUSTED' | 'INVALID_CLOCK' | 'CLOCK_ROLLBACK' | 'STATE_UNAVAILABLE';

/** Stable, safe errors: no state contents, OS paths or original I/O errors escape. */
export class SnowflakeError extends Error {
  constructor(public readonly code: SnowflakeErrorCode) {
    super(`Snowflake: ${code}`);
    this.name = 'SnowflakeError';
  }
}
