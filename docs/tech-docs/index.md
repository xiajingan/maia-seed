# Tech Docs Index

> ⚠️ **MAI-Harness 框架文件** — 请勿在项目中修改。如需变更请在框架工程中修改并覆盖到此项目。

> 技术方案文档索引。所有 AI 生成的技术方案文档保存于此目录。
> 技术方案须关联对应的 User Story（见 [USER_STORIES.md](../../USER_STORIES.md)）。

## 文档规范

- 每个技术方案文档须在此索引中注册
- 文件命名：`[模块]-[功能]-design.md`，例：`microsite-generation-design.md`
- 须包含：背景/目标、方案设计、接口定义、数据模型、关联需求、技术债记录

## 文档列表

| 文件 | 模块 | 关联需求 | 验证状态 |
|------|------|---------|---------|
| [seed-api-stability-matrix.md](seed-api-stability-matrix.md) | Seed API 稳定性与 Assignment 迁移 | SEED-022/023 | draft |
| [sprint-1-retry-contract.md](sprint-1-retry-contract.md) | `retry-contract` 公共 API 与交付设计 | S1-D01 / `seed-dep-mud-s2-r01-retry-contract` | draft |
| [sprint-2-retry-reference-foundation.md](sprint-2-retry-reference-foundation.md) | 组合 `seed.crypto` 的 retry-reference/snapshot 与 provenance 设计 | S2-D01 / `seed-dep-mud-s2-r01-retry-reference-foundation` | draft |

<!-- 验证状态: verified（已验证，与代码一致）/ stale（过期，需更新）/ draft（草稿） -->
