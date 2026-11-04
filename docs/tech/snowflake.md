# Snowflake SDK

## 范围与公开边界

服务于 US-001 的 Mud 业务主键；格式唯一真源为[数据架构 §3](../../../docs/architecture/data-architecture.md#3-snowflake-生成与传输契约)。包名 `maia-snowflake`，ESM，Node 24，零运行时依赖，不调用网络。SDK 只处理技术 ID，不读取业务关系，不协调不同部署的 workerId。

```ts
createSnowflake(options: {
  workerId: number;
  statePath: string;
  initialize?: boolean;
  now?: () => number;
}): Promise<{ next(): Promise<string>; close(): Promise<void> }>;
encode(parts: { timestampMs: number; workerId: number; sequence: number }): string;
decode(id: string): { timestampMs: number; workerId: number; sequence: number };
isSnowflake(value: unknown): value is string;
```

编码与解码只接受规范正十进制 ID，使用 bigint 位运算，序列化不经过 JS number。固定向量位于 `tests/fixtures/snowflake-v1.json`，供 Mud/Celt 等消费者复用；向量含最小值、位边界、大于 2^53 的 ID 与最大值。

## 持久高水位与生命周期

调用者提供已存在的持久目录与 workerId。路径父目录 realpath 归一化后，以 `<statePath>.lock` 独占 mkdir 获得所有权；锁冲突立即拒绝。拒绝状态路径符号链接/多硬链接，避免别名绕过同路径排他；父目录及状态文件须由可信运维控制。

状态包含版本、workerId、已预留毫秒高水位及 SHA-256 校验。启动时状态缺失默认拒绝；只有显式 `initialize: true` 可首次创建。已有内容损坏、版本未知、workerId 不符一律拒绝，不覆盖原文件。校验和检测意外损坏，不是防恶意修改的认证签名；备份回滚、复制/删除状态均不能由 SDK 自动判明。

每次进入新毫秒，将整毫秒高水位先写独占临时文件、fsync、原子 rename，再 fsync 父目录，成功后才返回该毫秒 ID。同毫秒序列在进程内递增。相比逐 ID fsync，这最多按实际使用的毫秒落盘；牺牲崩溃后未使用序列，保留最多 1024/ms 的编码容量。此容量不是已测服务吞吐预算。持久化失败后当前实例停止发号，必须 close 并核对恢复。

重启严格等待当前时钟大于已预留毫秒；正常 close 也遵守此规则。时钟回拨等待恢复至上一毫秒，序列耗尽等待下一毫秒；统一使用单调时钟 100 ms deadline 与 1 ms 轮询，超时拒绝且不返回 ID。该边界限制时钟等待，不承诺操作系统 I/O 的硬超时。最后有效时刻耗尽后不能越过格式上限发号。

next 按调用顺序串行处理，close 禁止新调用并排空已有调用后释放锁，多次 close 幂等。崩溃残留锁不按 PID/TTL 自动回收，避免进程号复用、时钟和共享路径误判；确认旧 owner 已停止、worker 未被别处复用且状态完整后由运维清理锁，状态不可删除或重新初始化。同 worker 不同路径无法由本地 SDK 检测，仍由部署保证。

## 错误与恢复

公开 `SnowflakeError.code` 是稳定技术原因，message 不包含路径、原始状态或系统异常。输入错误由调用者修正；时钟类错误恢复后可重试；状态 I/O 后实例保持不可用，不能在内存继续发号；锁/状态错误须核对运维事实。具体 code 与测试一同维护。

## 验证与交付

[TC-SEED-001](../test-cases/TC-SEED-001.md) 通过公开 API 覆盖字面向量、非法输入、并发、耗尽、回拨、正常关闭重启、损坏/缺失状态、同路径进程争用、崩溃恢复及持久失败。真实临时文件与子进程用于验证恢复，时钟通过公开 now 注入；不 mock SDK 内部。

`pnpm check` 执行 lint/typecheck/test/build；CI 固定基线 Node/pnpm、冻结安装锁文件。`pnpm --dir packages/maia-snowflake pack --pack-destination ../../artifacts` 产出本地 tarball。此制品用于本次隔离环境消费验证，不代表完成组织签名、SBOM/provenance 信任根或 Test/Prod 发布准入；真实 Mud 消费与数据库无损往返由 Mud 验证。

错误码：

| code | 含义与动作 |
|---|---|
| INVALID_ID / INVALID_PARTS / INVALID_OPTIONS | 规范 ID、编解码字段或配置无效，修正输入 |
| INVALID_CLOCK | 时钟返回非整数、越界或抛异常，核对时钟 |
| CLOCK_ROLLBACK / SEQUENCE_EXHAUSTED / RECOVERY_WAIT | 有界时钟等待耗尽，确认时钟恢复后重试 |
| STATE_MISSING / STATE_CORRUPT / WORKER_MISMATCH | 缺少状态、内容/版本/校验错误或归属错误，停止并核对持久事实 |
| STATE_LOCKED / LOCK_LOST | 已被占用或当前 owner 丢失；不能偷锁，close 不删除替换的锁 |
| STATE_IO / STATE_UNAVAILABLE | 文件系统失败/失败实例不可继续，核对存储并重新启动 |
| CLOSED | 已开始关闭，不接受新调用 |

2026-11-04 本机 Node 24.21.0 / darwin、真实时钟与本地文件系统，200 个并发 next 生成 200 个唯一 ID，1777.43 ms，约 112.52 ID/s。此单次观察用于说明持久优先的成本，不是服务 SLO，也不证明目标部署卷吞吐；Mud 消费与目标存储验证仍独立进行。状态路径要求支持 POSIX 目录同步及原子 rename，当前本地证据为 macOS；CI 已配置 Ubuntu，尚未声称其运行通过。
