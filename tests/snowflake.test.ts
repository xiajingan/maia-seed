import { readFileSync } from 'node:fs';
import { mkdtemp, rm, readFile, writeFile, symlink, mkdir, rename, stat, link } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { spawn, spawnSync, execFileSync } from 'node:child_process';
import { once } from 'node:events';
import { dirname, join } from 'node:path';
import { afterEach, expect, test } from 'vitest';
import { encode, decode } from '../packages/maia-snowflake/src/index.js';

// TC-SEED-001：跨语言固定字面量（不是由被测算法计算期望值）。
test('TC-SEED-001 固定向量编码解码及大于 2^53 的字符串无损', () => {
  const vectors: {id: string; timestampMs: number; workerId: number; sequence: number}[] =
    JSON.parse(readFileSync(new URL('./fixtures/snowflake-v1.json', import.meta.url), 'utf8'));
  for (const { id, ...parts } of vectors) {
    expect(encode(parts)).toBe(id);
    expect(decode(id)).toEqual(parts);
    expect(JSON.parse(JSON.stringify({ id }))).toEqual({ id });
  }
});

// TC-SEED-001
test('TC-SEED-001 非规范 ID、字段范围与零值拒绝且校验器接收 unknown', async () => {
  const { isSnowflake } = await import('../packages/maia-snowflake/src/index.js');
  for (const value of ['', '0', '01', '-1', '1.0', '+1', ' 1', '1\n', '9223372036854775808']) {
    expect(() => decode(value)).toThrowError(expect.objectContaining({ code: 'INVALID_ID' }));
    expect(isSnowflake(value)).toBe(false);
  }
  for (const value of [null, undefined, 1, 1n, {}, [], '9'.repeat(1000)]) {
    expect(isSnowflake(value)).toBe(false);
  }
  expect(isSnowflake('9007199254740993')).toBe(true);
  for (const parts of [
    {timestampMs: 1767225599999, workerId: 0, sequence: 1},
    {timestampMs: 3966248855552, workerId: 0, sequence: 1},
    {timestampMs: NaN, workerId: 0, sequence: 1},
    {timestampMs: 1767225600000.5, workerId: 0, sequence: 1},
    {timestampMs: 1767225600000, workerId: -1, sequence: 1},
    {timestampMs: 1767225600000, workerId: 4096, sequence: 1},
    {timestampMs: 1767225600000, workerId: 1.1, sequence: 1},
    {timestampMs: 1767225600000, workerId: 0, sequence: -1},
    {timestampMs: 1767225600000, workerId: 0, sequence: 1024},
    {timestampMs: 1767225600000, workerId: 0, sequence: 0},
  ]) expect(() => encode(parts)).toThrowError(expect.objectContaining({ code: 'INVALID_PARTS' }));
});

const cleanups: (() => Promise<unknown>)[] = [];
afterEach(async () => { for (const clean of cleanups.splice(0).reverse()) await clean(); });
async function statePath(): Promise<string> {
  const directory = await mkdtemp(join(tmpdir(), 'maia-snowflake-'));
  cleanups.push(() => rm(directory, { recursive: true, force: true }));
  return join(directory, 'state.json');
}

// TC-SEED-001
test('TC-SEED-001 首次初始化后公开 next 并发唯一，close 后拒绝', async () => {
  const { createSnowflake } = await import('../packages/maia-snowflake/src/index.js');
  const ids = await createSnowflake({ workerId: 7, statePath: await statePath(), initialize: true,
    now: () => 1767225600010 });
  cleanups.push(() => ids.close());
  const values = await Promise.all(Array.from({ length: 100 }, () => ids.next()));
  expect(new Set(values).size).toBe(100);
  expect(values[0]).toBe('41950208');
  expect(decode(values[99] ?? '')).toEqual({timestampMs: 1767225600010, workerId: 7, sequence: 99});
  await ids.close();
  await ids.close();
  await expect(ids.next()).rejects.toMatchObject({ code: 'CLOSED' });
});

// TC-SEED-001
test('TC-SEED-001 缺少恢复状态默认拒绝，初始化生成的水位跨重启保留', async () => {
  const { createSnowflake } = await import('../packages/maia-snowflake/src/index.js');
  const path = await statePath();
  await expect(createSnowflake({ workerId: 1, statePath: path })).rejects.toMatchObject({code: 'STATE_MISSING'});
  let time = 1767225600100;
  const first = await createSnowflake({workerId: 1, statePath: path, initialize: true, now: () => time});
  const id = await first.next();
  await first.close();
  await expect(createSnowflake({workerId: 1, statePath: path, now: () => time})).rejects.toMatchObject({code: 'RECOVERY_WAIT'});
  time++;
  const second = await createSnowflake({workerId: 1, statePath: path, now: () => time});
  cleanups.push(() => second.close());
  expect(BigInt(await second.next())).toBeGreaterThan(BigInt(id));
});


// TC-SEED-001
test('TC-SEED-001 非法配置与损坏恢复状态拒绝且 initialize 不覆盖', async () => {
  const { createSnowflake } = await import('../packages/maia-snowflake/src/index.js');
  const path = await statePath();
  for (const workerId of [-1, 4096, 1.5, NaN]) {
    await expect(createSnowflake({workerId, statePath: path, initialize: true})).rejects.toMatchObject({code: 'INVALID_OPTIONS'});
  }
  await expect(createSnowflake({workerId: 1, statePath: ''})).rejects.toMatchObject({code: 'INVALID_OPTIONS'});
  const gen = await createSnowflake({workerId: 1, statePath: path, initialize: true});
  await gen.next();
  await gen.close();
  const original = await readFile(path, 'utf8');
  await expect(createSnowflake({workerId: 2, statePath: path, initialize: true})).rejects.toMatchObject({code: 'WORKER_MISMATCH'});
  expect(await readFile(path, 'utf8')).toBe(original);
  for (const damaged of ['{', '{}', 'null', original.replace('"version":1', '"version":2'), original.replace('"workerId":1', '"workerId":3')]) {
    await writeFile(path, damaged);
    await expect(createSnowflake({workerId: 1, statePath: path, initialize: true})).rejects.toMatchObject({code: 'STATE_CORRUPT'});
    expect(await readFile(path, 'utf8')).toBe(damaged);
  }
});


// TC-SEED-001
test('TC-SEED-001 同路径与父目录别名排他，失败启动不会释放原 owner', async () => {
  const { createSnowflake } = await import('../packages/maia-snowflake/src/index.js');
  const path = await statePath();
  const owner = await createSnowflake({workerId: 1, statePath: path, initialize: true});
  cleanups.push(() => owner.close());
  const alias = join(dirname(path), 'alias');
  await symlink(dirname(path), alias, 'dir');
  for (const target of [path, join(alias, 'state.json'), path]) {
    await expect(createSnowflake({workerId: 1, statePath: target, initialize: true})).rejects.toMatchObject({code: 'STATE_LOCKED'});
  }
  await owner.next();
  await owner.close();
  await new Promise(resolve => setTimeout(resolve, 2));
  const recovered = await createSnowflake({workerId: 1, statePath: path});
  cleanups.push(() => recovered.close());
  expect(await recovered.next()).toMatch(/^[1-9][0-9]+$/);
});

// TC-SEED-001
test('TC-SEED-001 序列耗尽等待有界，推进时钟后恢复且 epoch 不返回零', async () => {
  const { createSnowflake } = await import('../packages/maia-snowflake/src/index.js');
  let time = 1767225600000;
  const gen = await createSnowflake({workerId: 0, statePath: await statePath(), initialize: true, now: () => time});
  cleanups.push(() => gen.close());
  const values = await Promise.all(Array.from({length: 1023}, () => gen.next()));
  expect(values[0]).toBe('1');
  expect(values[1022]).toBe('1023');
  const start = performance.now();
  await expect(gen.next()).rejects.toMatchObject({code: 'SEQUENCE_EXHAUSTED'});
  expect(performance.now() - start).toBeLessThan(500);
  time++;
  expect(await gen.next()).toBe('4194304');
});

// TC-SEED-001
test('TC-SEED-001 回拨有界拒绝，恢复后序列继续，非法时钟不会污染持久状态', async () => {
  const { createSnowflake } = await import('../packages/maia-snowflake/src/index.js');
  const path = await statePath();
  let time = 1767225600100;
  const gen = await createSnowflake({workerId: 1, statePath: path, initialize: true, now: () => time});
  cleanups.push(() => gen.close());
  const first = await gen.next();
  time--;
  const start = performance.now();
  await expect(gen.next()).rejects.toMatchObject({code: 'CLOCK_ROLLBACK'});
  expect(performance.now() - start).toBeLessThan(500);
  time++;
  expect(BigInt(await gen.next())).toBe(BigInt(first) + 1n);
  const state = await readFile(path, 'utf8');
  for (const invalid of [NaN, Infinity, 1767225599999, 3966248855552, 1767225600000.1]) {
    time = invalid;
    await expect(gen.next()).rejects.toMatchObject({code: 'INVALID_CLOCK'});
    expect(await readFile(path, 'utf8')).toBe(state);
  }
  time = 1767225600101;
  expect(decode(await gen.next()).timestampMs).toBe(time);
});

// TC-SEED-001
test('TC-SEED-001 close 立即禁止新调用并排空已接受调用', async () => {
  const { createSnowflake } = await import('../packages/maia-snowflake/src/index.js');
  const gen = await createSnowflake({workerId: 1, statePath: await statePath(), initialize: true});
  const ids = Array.from({length: 20}, () => gen.next());
  const closed = gen.close();
  await expect(gen.next()).rejects.toMatchObject({code: 'CLOSED'});
  expect(new Set(await Promise.all(ids)).size).toBe(20);
  await closed;
  await gen.close();
});

// TC-SEED-001
test('TC-SEED-001 并发 close 幂等，不重复释放锁', async () => {
  const { createSnowflake } = await import('../packages/maia-snowflake/src/index.js');
  const gen = await createSnowflake({workerId: 1, statePath: await statePath(), initialize: true});
  await Promise.all(Array.from({length: 10}, () => gen.close()));
});


// TC-SEED-001
test('TC-SEED-001 持久写入失败无 ID 返回并停止当前实例发号', async () => {
  const { createSnowflake } = await import('../packages/maia-snowflake/src/index.js');
  const path = await statePath();
  let time = 1767225600100;
  const gen = await createSnowflake({workerId: 1, statePath: path, initialize: true, now: () => time});
  cleanups.push(() => gen.close());
  await gen.next();
  const original = await readFile(path, 'utf8');
  await rm(path);
  await mkdir(path);
  time++;
  const rejected = await gen.next().catch((error: unknown) => error);
  expect(rejected).toMatchObject({code: 'STATE_IO'});
  expect(String(rejected)).not.toContain(path);
  await rm(path, {recursive: true});
  await writeFile(path, original);
  await expect(gen.next()).rejects.toMatchObject({code: 'STATE_UNAVAILABLE'});
});


// TC-SEED-001
test('TC-SEED-001 真实进程崩溃保留锁，人工核对清锁后仍服从落盘水位', async () => {
  const { createSnowflake } = await import('../packages/maia-snowflake/src/index.js');
  const path = await statePath();
  const child = spawn(process.execPath, [fileURLToPath(new URL('./fixtures/owner.mjs', import.meta.url)), path], {
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const exited = once(child, 'exit');
  cleanups.push(async () => { if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL'); await exited; });
  const generated = await new Promise<string>((resolve, reject) => {
    child.stdout.once('data', value => resolve(String(value).trim()));
    child.once('error', reject);
    child.once('exit', code => reject(new Error(`owner exited before ID: ${code}`)));
  });
  expect(generated).toBe('838870016');
  await expect(createSnowflake({workerId: 9, statePath: path})).rejects.toMatchObject({code: 'STATE_LOCKED'});
  child.kill('SIGKILL');
  await exited;
  await expect(createSnowflake({workerId: 9, statePath: path})).rejects.toMatchObject({code: 'STATE_LOCKED'});
  await rm(`${path}.lock`, {recursive: true});
  await expect(createSnowflake({workerId: 9, statePath: path, now: () => 1767225600200})).rejects.toMatchObject({code: 'RECOVERY_WAIT'});
  const recovered = await createSnowflake({workerId: 9, statePath: path, now: () => 1767225600201});
  cleanups.push(() => recovered.close());
  expect(BigInt(await recovered.next())).toBeGreaterThan(BigInt(generated));
});

// TC-SEED-001
test('TC-SEED-001 owner 丢失不再发号，close 不删除替换后的锁', async () => {
  const { createSnowflake } = await import('../packages/maia-snowflake/src/index.js');
  const path = await statePath();
  const gen = await createSnowflake({workerId: 1, statePath: path, initialize: true, now: () => 1767225600100});
  await gen.next();
  await rename(`${path}.lock`, `${path}.old-lock`);
  await mkdir(`${path}.lock`);
  await expect(gen.next()).rejects.toMatchObject({code: 'LOCK_LOST'});
  await expect(gen.close()).rejects.toMatchObject({code: 'LOCK_LOST'});
  expect((await stat(`${path}.lock`)).isDirectory()).toBe(true);
});

// TC-SEED-001
test('TC-SEED-001 状态 symlink 与硬链接拒绝，不跟随别名读写', async () => {
  const { createSnowflake } = await import('../packages/maia-snowflake/src/index.js');
  const path = await statePath();
  const gen = await createSnowflake({workerId: 1, statePath: path, initialize: true});
  await gen.close();
  await symlink(path, `${path}.symlink`);
  await expect(createSnowflake({workerId: 1, statePath: `${path}.symlink`, initialize: true})).rejects.toMatchObject({code: 'STATE_IO'});
  await link(path, `${path}.hardlink`);
  await expect(createSnowflake({workerId: 1, statePath: `${path}.hardlink`, initialize: true})).rejects.toMatchObject({code: 'STATE_CORRUPT'});
});

// TC-SEED-001
test('TC-SEED-001 已创建实例固定 worker，不受调用者事后修改配置影响', async () => {
  const { createSnowflake } = await import('../packages/maia-snowflake/src/index.js');
  const options = {workerId: 1, statePath: await statePath(), initialize: true, now: () => 1767225600100};
  const gen = await createSnowflake(options);
  cleanups.push(() => gen.close());
  options.workerId = 2;
  expect(decode(await gen.next()).workerId).toBe(1);
});

// TC-SEED-001
test('TC-SEED-001 JavaScript 调用的非对象编码输入仍返回安全错误码', () => {
  for (const value of [null, undefined, 1, '1', []]) {
    expect(() => Reflect.apply(encode, undefined, [value])).toThrowError(expect.objectContaining({code: 'INVALID_PARTS'}));
  }
});


// TC-SEED-001
test('TC-SEED-001 非普通状态文件不会阻塞启动', async () => {
  const path = await statePath();
  execFileSync('mkfifo', [path]);
  const entry = new URL('../packages/maia-snowflake/dist/index.js', import.meta.url).href;
  const result = spawnSync(process.execPath, ['--input-type=module', '-e',
    `import { createSnowflake } from ${JSON.stringify(entry)};
     try { await createSnowflake({workerId: 1, statePath: ${JSON.stringify(path)}}); }
     catch (error) { process.stdout.write(error.code); }`], {timeout: 1000, encoding: 'utf8'});
  expect(result.stdout).toBe('STATE_CORRUPT');
  expect(result.status).toBe(0);
});

// TC-SEED-001
test('TC-SEED-001 独立 worker 各自完整毫秒容量且跨实例不重复', async () => {
  const { createSnowflake } = await import('../packages/maia-snowflake/src/index.js');
  const first = await createSnowflake({workerId: 1, statePath: await statePath(), initialize: true, now: () => 1767225600100});
  cleanups.push(() => first.close());
  const second = await createSnowflake({workerId: 4095, statePath: await statePath(), initialize: true, now: () => 1767225600100});
  cleanups.push(() => second.close());
  const values = await Promise.all(Array.from({length: 1024}, async () => [await first.next(), await second.next()]));
  expect(new Set(values.flat()).size).toBe(2048);
  expect(decode(values[1023]?.[0] ?? '').sequence).toBe(1023);
  expect(decode(values[1023]?.[1] ?? '').sequence).toBe(1023);
});
