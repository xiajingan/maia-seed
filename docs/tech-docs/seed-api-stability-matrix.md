# Seed API stability matrix

状态：实现完成、制品发布阻断。当前 `0.0.0.dev0` 仅为源码工作区占位版本，不是 staged/release SemVer，不得被消费者锁定。

| Task | Stable module | Public symbols | Change | Consumer | Removal |
|---|---|---|---|---|---|
| SEED-001 | `seed.config` | `SettingsLoader`, `SettingsSource`, `RedactedSettingsSummary`, `ConfigLoadError` | additive | `mud.test.tenant-config` | N/A |
| SEED-002 | `seed.context` | `RequestContext`, `ContextToken`, `ContextScope`, `ContextError` | additive | `mud.test.tenant-context-isolation` | N/A |
| SEED-013 / `seed-dep-mud-p0-002-secrets` | `seed.secrets` | `SecretReference`, `SecretProvider`, `SecretLease`, `SecretBuffer`, `SecretProviderError` | additive；已有实现等待 Seed 主动接受输入并纳入本地 Sprint 后才可交付 | `mud.test.tenant-secret-lifecycle` | N/A |
| SEED-021 | `seed.oceanbase` | `OceanBaseRuntime`, `OceanBaseSettings`, `OceanBaseSessionScope`, `DialectCapabilities`, `DependencyHealth`, `OceanBaseRuntimeError` | additive | `mud.test.oceanbase-lifecycle` | N/A |

兼容策略：首次稳定版本发布后，弃用至少保留一个 minor；破坏变化提升 major，并在对应 Dependency Assignment/本地迁移 Story 登记删除版本。Seed 不提供 Mud 业务 alias。

升级顺序：Seed 先主动处理 `seed-dep-mud-p0-002-secrets` 并映射本地 Story/Sprint → 可信 staged index 安装精确版本及摘要 → 四项 Mud consumer tests → 同一 digest 提升 release。回滚采用 `restore_previous_version_and_hash`；首次采用时恢复为无 Seed 锁的状态。
