# Maia Seed 用户故事

> 基线：`maia-greenfield-20260920`；2026-09-20 重建。上游：[Maia 用户故事](../USER_STORIES.md) US-020/022；边界见 [ARCHITECTURE.md](ARCHITECTURE.md)。Snowflake 公共库归属已明确，当前尚无执行 Assignment 或可消费的新制品。

## 产品愿景

为具体 Maia TS 服务交付可独立验证、版本固定的公共技术能力，让消费者无需复制技术实现，并能安全升级。

## 产品策略与体验原则

| ID | 原则 | 适用场景 | 边界 |
|---|---|---|---|
| PS-001 | 真实需求驱动 | 公共技术缺口 | 不预置旧 Python 模块的翻译 backlog |
| PS-002 | 契约与消费者共同验收 | 包发布和升级 | 没有真实 Delivery 不宣称能力可用 |
| PS-003 | 技术机制不拥有业务事实 | 所有公共包 | 不含业务表、SQL、Policy 或服务进程 |

## 用户画像

| 画像 | 使用上下文 | 核心诉求 | 能力或限制 |
|---|---|---|---|
| 消费服务开发者 | 已选 Story/Task 遇到公共技术缺口 | 明确契约、固定制品与消费者验证 | 应提供目标、边界和验收，不指定虚构版本 |
| Seed 维护者 | 接受真实 dependency 后规划交付 | 有边界的 TS 包与兼容性 | 自主迭代，不反向依赖消费工程 |

## 业务术语

| 术语 | 项目内唯一含义 | 易混淆概念 |
|---|---|---|
| Dependency Assignment | 消费工程的技术能力需求 | 已接受的 Story 或已交付能力 |
| Delivery | 固定制品与验证条件的不可变交付记录 | 文件夹、候选源码或旧 wheel |

## Story 索引

| ID | 标题 | 来源 | 优先级 | 状态 |
|---|---|---|---|---|

当前为空。旧 23 个 Story 及其状态已归档，不重新编号冒充新需求。Mud 的候选缺口只有在明确消费者和验收、并由 Seed 接受后才生成新 US 与 AC；下一编号从 US-101 开始以隔离旧身份。

## 已确定的技术约束

用户已指定 **Seed 实现 `maia-snowflake` 本地 ID SDK**（`seed.snowflake`），供 Mud 及其他 TS 服务直接调用，不依赖在线分配服务。生成、编解码和校验统一遵循 [Snowflake v1 格式与业务语义](../ARCHITECTURE.md#23-snowflake-生成与传输契约)；workerId 由部署配置保障，SDK 验证并发、回拨、序列耗尽、重启防重和大整数往返。

公共库归属已定，后续 dependency 落实接口与消费者验收，当前尚无可消费制品。TiDB/Drizzle、MySQL 8.0 及业务逻辑边界沿用 [Maia 数据库原则](../ARCHITECTURE.md#22-数据库五条硬约束)。

## 接入与验收要求

每个新 Story 必须关联真实 Assignment 和消费 Story/Task，包含角色、触发、困难、可观察结果、约束、非目标和行为 AC。Review、确认后才进入 Seed Sprint；MQ/Storage 的独立服务功能不得纳入 Seed 包故事。

本轮清理和输入重设不生成需求确认回执，不把任何 Story 标为 ready/done，也不启动包构建或发布。
