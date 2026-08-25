# sprint-1-retry-contract

sprint_type: library-sprint
base_ref: refs/remotes/origin/develop
base_sha: d561a330e1f091229746057ebb1fa3d4e6181cc3
branch: library/1-retry-contract

- **目标**：在 maia-seed 提供无业务语义、类型安全且失败关闭的重试结果契约，并与 Seed 公共错误能力组合后供 Mud 使用
- **状态**：completed
- **环境就绪**：✅
dependency_session: seed-dep-mud-s2-r01-retry-contract
request_digest: sha256:d62c78dac0210a60e11e4559c706749eb5724aa2828aaf59cf14b0355743f32d
capability: retry-contract
- **验收条件**：仅经验证的 opaque retry reference 可重试；区分可重试依赖失败、不可重试依赖失败与调用方契约错误；不含 WeCom/Mud/provider 专用语义；与 `seed.errors` 组合且 Mud 不重复公共分类或序列化；Seed 正反例单测及 Mud 非法 issuer 消费者测试通过；Delivery、wheel 版本、SHA-256、供应链 receipt 与 Mud lock 一致

## 任务

| ID | 类型 | 来源 | 父任务 | 任务描述 | 依赖 | 产出物 | 验收条件 | 状态 |
|---|---|---|---|---|---|---|---|---|
| S1-D01 | library-design | planned | - | 定义 `retry-contract` 的最小公共 API、错误分类组合、失败关闭不变式、兼容策略与消费者契约 | - | `docs/tech-docs/sprint-1-retry-contract.md`；API stability matrix 更新 | 能力 ID、公共/业务边界、版本兼容与废弃策略明确；登记 Mud 契约命令；不含 WeCom、Mud 或 provider 专用语义 | done |
| S1-C01 | library-code | planned | - | 实现类型安全的 opaque retry reference/result 与可重试依赖失败、不可重试依赖失败、调用方契约错误，并与 `seed.errors` 组合 | S1-D01 | `src/seed/` 公共 API 与实现；`tests/` 正反例单测 | 仅已验证 reference 可产生 retryable 结果；空值、`bool`、错误类型及不可验证值失败关闭；静态、类型、单测通过且 0 Critical / 0 Major | done |
| S1-Q01 | library-quality | planned | - | 对当前源码提交执行 Library 全量质量评分 | S1-C01 | `docs/test-reports/sprint-1-retry-contract-quality.md` | `command_groups.precommit` 全部通过；覆盖率达到项目阈值；质量分达到 95 | done |
| S1-P01 | library-package | planned | - | 从通过质量门禁且已提交的源码执行一次 Build Once，登记不可变 wheel 身份 | S1-Q01 | `dist/` wheel；`.harness/state/library-packages/sprint-1-retry-contract.json` | package 仅构建一次；version、完整 source commit 与 SHA-256 证据一致 | done |
| S1-V01 | library-contract | planned | - | 将 Build Once candidate 登记到当前 session，并运行 Mud 的 `retry-contract` 消费者契约 | S1-P01 | `.harness/state/dependency-sessions/incoming/seed-dep-mud-s2-r01-retry-contract.json` 中的 consumer evidence | Seed 单元/公共 API 检查已通过；Mud 非法 issuer 等正反契约针对同一 candidate 通过；破坏性变更已升 major 或被拒绝 | done |
| S1-L01 | library-delivery | planned | - | 发布绑定当前 request digest、candidate 和供应链证据的不可变 `dependency-package` Delivery | S1-V01 | `docs/deliveries/` dependency-package Delivery；`.harness/state/delivery-verifications/` receipt | Delivery 同时绑定 Assignment 与当前 session 摘要；package/version/source commit/SHA-256 与 candidate 一致；签名、SBOM、provenance receipt 有效 | done |
| S1-X01 | library-close | planned | - | 在全部 Library 交付门禁通过后归档本 Sprint | S1-L01 | `docs/exec-plans/completed/sprint-1-retry-contract.md` | 全部 Library 任务完成；计划从 active 原子归档到 completed | done |
| S1-R01 | library-pr | planned | - | 通过统一 PR adapter 创建 Library Sprint 合并请求并确认远端门禁 | S1-X01 | PR/MR URL | PR/MR 由 `harness pr-adapter` 创建；远端 CI 与分支保护通过 | pending |
