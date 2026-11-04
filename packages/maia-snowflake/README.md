# maia-snowflake

Maia 本地 Snowflake SDK，ESM / Node 24。不连接发号服务。workerId 唯一分配及安全复用由部署负责；调用方为每个 workerId 提供独占、持久、支持 fsync/原子 rename 的本地状态路径，不能放在临时目录。

```ts
import { createSnowflake, decode, encode, isSnowflake } from 'maia-snowflake';

// 仅首次经部署确认的新 worker 使用 initialize: true；日常启动省略。
const ids = await createSnowflake({ workerId: 1, statePath: '/persistent/mud-1.json' });
const id: string = await ids.next();
await ids.close();
```

状态缺失、损坏、worker 不匹配、锁冲突均拒绝启动；initialize 不会覆盖已有损坏状态。每次进入新毫秒先持久预留整毫秒再返回 ID，重启须跨过该水位；停机可能留下未使用 ID。时钟回拨、序列耗尽和恢复等待最多 100 ms，返回带稳定 code 的 SnowflakeError。调用者不得重建状态绕过错误。

进程崩溃保留 `<statePath>.lock`，不会按 PID 或超时自动偷锁。运维确认旧进程已停止、状态完整且同一 worker 未被其他副本使用后，才可清理残留锁并重启；不得删除状态文件。正常 close 排空先前调用并释放锁，之后 next 拒绝。

所有 ID 是 1～2^63−1 的规范十进制字符串；不能经过 JS number。encode/decode 不接受前导零、负数或越界。内部时间位不代表业务时间、顺序或因果关系。
