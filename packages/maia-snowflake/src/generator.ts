import { encode, EPOCH_MS, validWorker, validTimestamp } from './codec.js';
import { setTimeout } from 'node:timers/promises';
import { openState } from './state.js';
import { SnowflakeError } from './errors.js';

export interface SnowflakeOptions {
  workerId: number;
  statePath: string;
  initialize?: boolean;
  now?: () => number;
}

export interface SnowflakeGenerator {
  next(): Promise<string>;
  close(): Promise<void>;
}

export async function createSnowflake(options: SnowflakeOptions): Promise<SnowflakeGenerator> {
  if (typeof options !== 'object' || options === null || !validWorker(options.workerId) ||
      typeof options.statePath !== 'string' || options.statePath.length === 0 || options.statePath.includes('\0') ||
      (options.initialize !== undefined && typeof options.initialize !== 'boolean') ||
      (options.now !== undefined && typeof options.now !== 'function')) throw new SnowflakeError('INVALID_OPTIONS');
  const workerId = options.workerId;
  const clock = options.now ?? Date.now;
  function now(): number {
    let value: unknown;
    try { value = clock(); } catch { throw new SnowflakeError('INVALID_CLOCK'); }
    if (!validTimestamp(value)) throw new SnowflakeError('INVALID_CLOCK');
    return value;
  }
  now();
  const state = await openState(options.statePath, workerId, options.initialize === true);
  try {
    if (state.highWaterMs >= EPOCH_MS) {
      const deadline = performance.now() + 100;
      while (now() <= state.highWaterMs) {
        if (performance.now() >= deadline) throw new SnowflakeError('RECOVERY_WAIT');
        await setTimeout(1);
      }
    }
  } catch (error) { await state.close(); throw error; }
  let lastMs = state.highWaterMs;
  let sequence = 0;
  let closed = false;
  let unavailable = false;
  let pending: Promise<unknown> = Promise.resolve();
  let closing: Promise<void> | undefined;
  async function nextId() {
    if (unavailable) throw new SnowflakeError('STATE_UNAVAILABLE');
    let time = now();
    const deadline = performance.now() + 100;
    while (time < lastMs) {
      if (performance.now() >= deadline) throw new SnowflakeError('CLOCK_ROLLBACK');
      await setTimeout(1);
      time = now();
    }
    if (time === lastMs && sequence >= 1023) {
      while (time <= lastMs) {
        if (performance.now() >= deadline) throw new SnowflakeError('SEQUENCE_EXHAUSTED');
        await setTimeout(1);
        time = now();
      }
    }
    const nextSequence = time === lastMs ? sequence + 1 :
      (time === EPOCH_MS && workerId === 0 ? 1 : 0);
    try {
      await state.assertOwnership();
      if (time !== lastMs) await state.persist(time);
    } catch (error) { unavailable = true; throw error; }
    lastMs = time;
    sequence = nextSequence;
    return encode({timestampMs: time, workerId, sequence});
  }
  return {
    next() {
      if (closed) return Promise.reject(new SnowflakeError('CLOSED'));
      const result = pending.then(nextId);
      pending = result.catch(() => undefined);
      return result;
    },
    close() {
      if (!closing) {
        closed = true;
        closing = pending.then(() => state.close());
      }
      return closing;
    },
  };
}
