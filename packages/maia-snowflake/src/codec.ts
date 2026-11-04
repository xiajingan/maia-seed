import { SnowflakeError } from './errors.js';

export const EPOCH_MS = 1767225600000;
export const MAX_TIMESTAMP_MS = 3966248855551;
const MAX_ID = 9223372036854775807n;

export interface SnowflakeParts {
  timestampMs: number;
  workerId: number;
  sequence: number;
}

export function encode(parts: SnowflakeParts): string {
  if (typeof parts !== 'object' || parts === null) throw new SnowflakeError('INVALID_PARTS');
  const { timestampMs, workerId, sequence } = parts;
  if (!validTimestamp(timestampMs) || !validWorker(workerId) ||
      !Number.isInteger(sequence) || sequence < 0 || sequence > 1023 ||
      (timestampMs === EPOCH_MS && workerId === 0 && sequence === 0)) {
    throw new SnowflakeError('INVALID_PARTS');
  }
  return ((BigInt(timestampMs - EPOCH_MS) << 22n) |
    (BigInt(workerId) << 10n) | BigInt(sequence)).toString();
}

export function decode(id: string): SnowflakeParts {
  if (!isSnowflake(id)) throw new SnowflakeError('INVALID_ID');
  const value = BigInt(id);
  return {
    timestampMs: Number(value >> 22n) + EPOCH_MS,
    workerId: Number((value >> 10n) & 4095n),
    sequence: Number(value & 1023n),
  };
}

export function isSnowflake(value: unknown): value is string {
  return typeof value === 'string' && /^[1-9][0-9]{0,18}$/.test(value) &&
    BigInt(value) <= MAX_ID;
}

export function validTimestamp(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) &&
    value >= EPOCH_MS && value <= MAX_TIMESTAMP_MS;
}

export function validWorker(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= 4095;
}
