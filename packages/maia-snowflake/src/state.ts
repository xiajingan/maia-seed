import { open, rename, realpath, mkdir, lstat, rmdir } from 'node:fs/promises';
import { constants } from 'node:fs';
import { createHash, randomUUID } from 'node:crypto';
import { basename, dirname, join } from 'node:path';
import { SnowflakeError } from './errors.js';
import { EPOCH_MS, validTimestamp, validWorker } from './codec.js';

function hasCode(error: unknown, code: string): boolean {
  return error instanceof Error && 'code' in error && error.code === code;
}

function checksum(workerId: number, highWaterMs: number): string {
  return createHash('sha256').update(JSON.stringify({version: 1, workerId, highWaterMs})).digest('hex');
}

function parseState(text: string, workerId: number): number {
  let value: unknown;
  try { value = JSON.parse(text); } catch { throw new SnowflakeError('STATE_CORRUPT'); }
  if (typeof value !== 'object' || value === null ||
      Object.keys(value).length !== 4 ||
      !('version' in value) || value.version !== 1 ||
      !('workerId' in value) || !validWorker(value.workerId) ||
      !('highWaterMs' in value) ||
      !(validTimestamp(value.highWaterMs) || value.highWaterMs === EPOCH_MS - 1) ||
      !('checksum' in value) || typeof value.checksum !== 'string' ||
      value.checksum !== checksum(value.workerId, value.highWaterMs)) {
    throw new SnowflakeError('STATE_CORRUPT');
  }
  if (value.workerId !== workerId) throw new SnowflakeError('WORKER_MISMATCH');
  return value.highWaterMs;
}

async function safe<T>(operation: () => Promise<T>): Promise<T> {
  try { return await operation(); }
  catch (error) {
    if (error instanceof SnowflakeError) throw error;
    throw new SnowflakeError('STATE_IO');
  }
}

export async function openState(statePath: string, workerId: number, initialize: boolean) {
  const state = await safe(() => acquireState(statePath, workerId, initialize));
  return {
    highWaterMs: state.highWaterMs,
    persist: (ms: number) => safe(() => state.persist(ms)),
    assertOwnership: () => safe(() => state.assertOwnership()),
    close: () => safe(() => state.close()),
  };
}

async function acquireState(statePath: string, workerId: number, initialize: boolean) {
  const directory = await realpath(dirname(statePath));
  const path = join(directory, basename(statePath));
  async function syncDirectory() {
    const parent = await open(directory, 'r');
    try { await parent.sync(); } finally { await parent.close(); }
  }
  const lockPath = `${path}.lock`;
  try { await mkdir(lockPath, {mode: 0o700}); }
  catch (error) {
    if (hasCode(error, 'EEXIST')) throw new SnowflakeError('STATE_LOCKED');
    throw error;
  }
  // Keep the directory descriptor open so a removed inode cannot be reused unnoticed.
  const lock = await open(lockPath, 'r');
  const identity = await lock.stat();
  let released = false;
  async function assertOwnership() {
    const current = await lstat(lockPath);
    if (!current.isDirectory() || current.dev !== identity.dev || current.ino !== identity.ino) {
      throw new SnowflakeError('LOCK_LOST');
    }
  }
  async function close() {
    if (released) return;
    try {
      await assertOwnership();
      await rmdir(lockPath);
      await syncDirectory();
    } finally { released = true; await lock.close(); }
  }
  async function persist(highWaterMs: number) {
    await assertOwnership();
    const temporary = `${path}.${randomUUID()}.tmp`;
    const file = await open(temporary, 'wx', 0o600);
    try {
      await file.writeFile(JSON.stringify({version: 1, workerId, highWaterMs,
        checksum: checksum(workerId, highWaterMs)}));
      await file.sync();
    } finally { await file.close(); }
    await rename(temporary, path);
    await syncDirectory();
  }
  try {
    await lock.sync();
    await syncDirectory();
    let highWaterMs: number;
    try {
      const file = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
      try {
        const stat = await file.stat();
        if (!stat.isFile() || stat.nlink !== 1 || stat.size > 4096) throw new SnowflakeError('STATE_CORRUPT');
        highWaterMs = parseState(await file.readFile('utf8'), workerId);
      } finally { await file.close(); }
    } catch (error) {
      if (!hasCode(error, 'ENOENT')) {
        if (error instanceof SnowflakeError) throw error;
        throw new SnowflakeError('STATE_IO');
      }
      if (!initialize) throw new SnowflakeError('STATE_MISSING');
      highWaterMs = EPOCH_MS - 1;
      await persist(highWaterMs);
    }
    return { highWaterMs, persist, close, assertOwnership };
  } catch (error) {
    await close();
    throw error;
  }
}
