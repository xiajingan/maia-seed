---
id: TC-SEED-001
title: Snowflake 公开接口与持久恢复保护
priority: P0
story: US-001
---

# TC-SEED-001 Snowflake 公开接口与持久恢复保护

## 来源

US-001 AC-01 首次登录创建个人根、User 与 manager Membership，AC-02 再次登录复用同一身份；其业务 ID 的必要技术前提来自[数据架构 §3.2](../../../docs/architecture/data-architecture.md#32-sdk-边界)及[已接受设计 §2](../../../docs/iterations/2026-11-personal-workspace/design.md#2-实施方案与工程职责)：Mud 消费 Seed SDK，不临时复制算法。

## 前置条件

- 基线 Node/pnpm；可 fsync 与原子 rename 的真实本地临时目录。
- 独占 workerId；复用已存在状态默认不传 initialize。
- 时钟异常通过公开 now 入口注入，固定向量由跨语言 JSON 夹具提供。

## 步骤与预期结果

1. 编解码固定字面向量并 JSON 往返：最小 ID、worker 位边界、毫秒位边界、超过 2^53 的 ID、最大正 BIGINT 全部逐字一致。
2. 输入非法 ID/worker/序列/时刻/配置：统一明确输入错误；isSnowflake 对 unknown 安全返回 false，不把 number 或非规范字符串当 ID。
3. 同一实例并发 next：所有 ID 唯一；同毫秒耗尽有界拒绝，时钟推进后可继续。epoch 零组合不会生成 0。
4. 注入时钟回拨：不在旧时刻发号，等待有界拒绝；时钟恢复后继续。超范围/非整数时钟拒绝。
5. 正常 close 并重启：水位未跨越拒绝，跨越后生成新 ID；close 排空已有调用，重复 close 幂等，后续 next 拒绝。
6. 缺失状态默认拒绝，显式首次初始化可用；损坏、未知版本、校验不符或 worker 不同拒绝且原文件保持不变。
7. 同路径同时启动、父路径别名和真实跨进程占用拒绝；失败启动不删除原 owner 的锁，正常释放后可重新获得所有权。
8. 真实子进程返回 ID 后被强制终止：残留锁阻止接管。确认子进程已停止并仅清锁后，SDK 仍按持久水位拒绝旧时钟；推进后恢复，原 ID 不重复。
9. 发号中真实文件系统写入失败：本次不返回 ID，后续停止发号；不能继续使用仅在内存更新的水位。

## 测试代码

- `tests/snowflake.test.ts` — 名称含 `TC-SEED-001` 的公开 codec 与 generator 行为测试。
- `tests/fixtures/snowflake-v1.json` — 所有消费者共享的固定跨语言向量。
- `tests/fixtures/owner.mjs` — 通过构建后公开 SDK 的真实进程所有权与崩溃测试。

P0 保护唯一性和重启防重；异常输入、路径和时钟分支为该技术用例的边界补充。此用例不证明 Mud 事务、真实 TiDB、不同机器的 workerId 分配或 Test/Prod 制品信任根。

补充边界：非普通文件（FIFO）不会阻塞启动；已创建实例的 workerId 不随调用方修改配置而改变；JavaScript 非对象编码输入仍返回稳定错误；两个独立 worker 各发满 1024 个 ID 后共 2048 个互不重复。
