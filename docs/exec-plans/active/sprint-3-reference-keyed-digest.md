# sprint-3-reference-keyed-digest

sprint_type: library-sprint
base_ref: refs/remotes/origin/develop
base_sha: 542083697439cffff61870a2854a993e2ca8691a
branch: library/3-reference-keyed-digest

- **目标**：在 maia-seed 提供无业务语义、域分离且 reference-keyed 的不可逆摘要能力
- **状态**：active
- **环境就绪**：✅
dependency_session: seed-dep-mud-s3-c02-reference-keyed-digest
request_digest: sha256:2f66a55e0e5e42e992f9773c044b49c60fc5196dc4ff411a63667a44d4ecf3c6
capability: seed.reference-keyed-digest.v1
- **验收条件**：Seed 独立 Library Sprint 交付精确 wheel version/SHA-256/receipt；API 不含 Mud/WeCom 语义；Mud 消费者契约验证域分离、确定性、密钥轮换和敏感材料零泄漏

## 任务

| ID | 类型 | 来源 | 父任务 | 任务描述 | 依赖 | 产出物 | 验收条件 | 状态 |
|---|---|---|---|---|---|---|---|---|
| SD3-D01 | library-design | planned | - | 设计无业务语义、reference-keyed、域分离的不可逆摘要公共 API 与兼容策略 | dependency_session + request_digest | `docs/tech-docs/reference-keyed-digest-design.md` | capability ID、公共边界、密钥轮换、版本兼容、消费者矩阵与废弃策略明确 | done |
| SD3-C01 | library-code | planned | - | 实现 reference-keyed digest API、密钥环、域分离与安全失败合同 | SD3-D01 | `src/seed/`、`tests/` | 无 Mud/WeCom 语义；确定性、域分离、篡改/错 key、active/previous 轮换、敏感材料零泄漏；静态/类型/单测通过 | done |
| SD3-Q01 | library-quality | planned | - | 执行 Seed 公共包质量门禁 | SD3-C01 | `docs/test-reports/sprint-3-reference-keyed-digest-quality.md` | 静态、类型、架构、单元、集成、安全审计、构建与覆盖率达到 Library 规范 | pending |
| SD3-P01 | library-package | planned | - | Build Once 生成唯一 maia-seed wheel candidate | SD3-Q01 | `dist/` + package evidence | 唯一 wheel 的 package/version/source commit/SHA-256 已登记且不可替换 | pending |
| SD3-CT01 | library-contract | planned | - | 以不可变 candidate 执行 Mud 消费者契约 | SD3-P01 | dependency session consumer evidence | 消费者验证域分离、确定性、密钥轮换、origin ownership 与敏感材料零泄漏 | pending |
| SD3-DLV01 | library-delivery | planned | - | 发布并验证签名、SBOM、provenance 与 Build Once Delivery | SD3-CT01 | `docs/deliveries/` + verifier receipt | Delivery 绑定 session/request digest/candidate，供应链 verifier 真实通过 | pending |
| SD3-X01 | library-close | planned | - | 归档 Library Sprint 与交付证据 | SD3-DLV01 | `docs/exec-plans/completed/sprint-3-reference-keyed-digest.md` | 全部前置任务完成，计划归档且 Delivery 不变 | pending |
| SD3-PR01 | library-pr | planned | - | 创建并合并 Seed Library PR | SD3-X01 | PR URL | pr-adapter 创建；precommit/构建通过；合并后安全清理 Provider worktree | pending |
