# Seed API stability matrix

状态：既有能力实现完成、制品发布阻断；`retry-contract` 仅处于 design / candidate not built。当前 `0.0.0.dev0` 仅为源码工作区占位版本，不是 staged/release SemVer，不得被消费者锁定。

| Task | Stable module | Public symbols | Change | Consumer | Removal |
|---|---|---|---|---|---|
| SEED-001 | `seed.config` | `SettingsLoader`, `SettingsSource`, `RedactedSettingsSummary`, `ConfigLoadError` | additive | `mud.test.tenant-config` | N/A |
| SEED-002 | `seed.context` | `RequestContext`, `ContextToken`, `ContextScope`, `ContextError` | additive | `mud.test.tenant-context-isolation` | N/A |
| SEED-013 / `seed-dep-mud-p0-002-secrets` | `seed.secrets` | `SecretReference`, `SecretProvider`, `SecretLease`, `SecretBuffer`, `SecretProviderError` | additive；已有实现等待 Seed 主动接受输入并纳入本地 Sprint 后才可交付 | `mud.test.tenant-secret-lifecycle` | N/A |
| SEED-021 | `seed.oceanbase` | `OceanBaseRuntime`, `OceanBaseSettings`, `OceanBaseSessionScope`, `DialectCapabilities`, `DependencyHealth`, `OceanBaseRuntimeError` | additive | `mud.test.oceanbase-lifecycle` | N/A |
| S1-D01 / `seed-dep-mud-s2-r01-retry-contract` | `seed.errors` | `DetailsReferenceVerifier`, `ErrorContractError`, `ErrorEnvelope`, `MachineErrorCode`, `VerifiedDetailsReference`, `compose_error_envelope`, `serialize_error_envelope`, `verify_details_reference` | additive；0.1.0 发布前 design / candidate not built；与 `seed.retry` 由同一 S1-C01 candidate 实现 | `maia-mud` / `seed_retry_contract` | N/A（首次 additive） |
| S1-D01 / `seed-dep-mud-s2-r01-retry-contract` | `seed.retry` | `DependencyFailure`, `DependencyFailureKind`, `RetryContractError`, `RetryReferenceVerifier`, `VerifiedRetryReference`, `classify_dependency_failure`, `dependency_failure_to_error`, `verify_retry_reference` | additive；design / candidate not built；与 `seed.errors` 由同一 S1-C01 candidate 实现；verifier/type/function 三项为 errors 稳定直接 alias | `maia-mud` / `seed_retry_contract` (`RC-VALID-001`, `RC-INVALID-001`, `RC-ISSUER-001`, `RC-FAULT-001`) | N/A（首次 additive） |

## `retry-contract` 治理记录

| 字段 | 值 |
|---|---|
| capability / task | `retry-contract` / `S1-D01` |
| trace | Assignment `seed-dep-mud-s2-r01-retry-contract` / digest `sha256:3e85907c98f7188fbb7b23b6d3c561b6412c634d9ab8bfa3903e1b00e30300ea`；accepted Response digest `sha256:b944d6600b9d1af3cc47ebc39f1a8ade64b5066515563f57118fe8f8bbd587a9`；session/request digest `sha256:d62c78dac0210a60e11e4559c706749eb5724aa2828aaf59cf14b0355743f32d` |
| provider / consumer task | `maia-seed` `sprint-1-retry-contract` / `S1-D01`；`maia-mud` `sprint-2-wecom-capability-api` / `S2-D01`（Assignment source reference `S2-R01`） |
| target / consumer range | `0.1.0` / 精确 `maia-seed==0.1.0` + candidate wheel SHA-256 |
| deprecated / earliest removal | N/A / N/A（首次 additive；后续弃用至少保留一个完整 minor，破坏删除升 major） |
| consumer workdir | `/Users/ws/space/git/mai/maia/maia-mud/.harness/worktrees/sprint-2-wecom-capability-api` |
| consumer command | `seed_retry_contract` = `["uv", "run", "python", "scripts/verify_seed_retry_contract.py"]`（命令已登记；脚本为 S1-V01 前置，当前未创建） |
| upgrade / rollback | `replace_lock_then_test` / `restore_previous_version_and_hash`；首次 adoption 原子恢复 adoption 前完整 `pyproject.toml` + `uv.lock` snapshot（相对路径、受控完整内容、逐文件 SHA-256、整体 snapshot digest、consumer source commit），复算摘要、验证声明/resolved lock 均无 `maia-seed`并运行原有 lock/静态检查；后续升级恢复上一 exact version/wheel SHA-256 + 完整 snapshot，验证 adoption evidence并重跑 contract |
| error shape | `ErrorEnvelope` 及 serializer 恰好七个必选 snake_case 字段/key：`domain: str`、`code: MachineErrorCode`、`retryable: bool`、`user_message: str`、`recovery: str \| None`、`correlation_id: str \| None`、`details_ref: str \| None`；后三者值可为 `None` 但 key 不省略，无 `message`/`retry_reference`/额外 key |
| details API | `DetailsReferenceVerifier.verify(candidate: str) -> bool`；`VerifiedDetailsReference.value: str`；`verify_details_reference(candidate: object, verifier: DetailsReferenceVerifier) -> VerifiedDetailsReference`，仅 exact non-empty `str` + verifier exact `True` 铸造 sealed object |
| errors API | `compose_error_envelope(domain: str, code: MachineErrorCode, *, retryable: bool, user_message: str, recovery: str \| None = None, correlation_id: str \| None = None, details_ref: VerifiedDetailsReference \| None = None) -> ErrorEnvelope`；retryable 只接受 errors 铸造的 sealed object，非重试 code 只允许 false/None；`serialize_error_envelope(envelope: ErrorEnvelope) -> dict[str, str \| bool \| None]` |
| errors reasons | `invalid_domain`、`invalid_code`、`invalid_retry_shape`、`invalid_user_message`、`invalid_recovery`、`invalid_correlation_id`、`invalid_details_candidate`、`details_verifier_rejected`、`details_verifier_contract_fault`、`details_seal_fault`、`serialization_fault` |
| retry composition API | `dependency_failure_to_error(failure: DependencyFailure, *, user_message: str, recovery: str \| None = None, correlation_id: str \| None = None) -> ErrorEnvelope`；caller 不能传入 domain/code/retryable/details_ref |
| alias identity | `RetryReferenceVerifier is DetailsReferenceVerifier`；`VerifiedRetryReference is VerifiedDetailsReference`；`verify_retry_reference is verify_details_reference`；无第二 Protocol/class/validator/seal/reason mapping |
| retry reasons | `RetryContractError.reason` 精确为 `invalid_failure_kind`、`failure_shape_fault`、`seal_fault`；candidate/verifier 类错误原样为 `ErrorContractError` |
| composition | 唯一路线：S1-C01 在同一变更、Review、质量门禁和 Build Once candidate 内实现 `seed.errors` + `seed.retry`；缺任一 module/API/tests即失败。依赖仅 `seed.retry → seed.errors` public API；所有 envelope 经唯一 public compose，verified object 唯一进入 serialized `details_ref`，consumer 不复制 validator/shape/mapping/serializer |
| Python boundary | 机械验证 public 签名、runtime exact-type/seal、普通构造、copy/pickle/subclass/fake/cross-version 与 exports；构造面只有 public compose；不承诺抵御同解释器任意代码执行下的 `object.__new__`/`__setattr__`、模块 `__dict__`篡改、debugger 或内存修改，但 public raw/fake 仍必须失败 |
| provider checks | `tests/unit/test_errors.py` 验证 details verifier/type/compose 正反矩阵与七 key；`tests/unit/test_retry.py` 验证三 alias identity、同一 verified object、唯一 public compose且无 unwrap/二次验证；`tests/architecture/test_boundaries.py` 验证单向 public 依赖且无隐藏 raw-string 构造入口，strict `mypy src/seed` 拒绝 raw details_ref；均为 S1-C01 前置，当前未实现/未通过 |

兼容策略：首次稳定版本发布后，弃用发出标准 warning 并至少保留一个完整 minor；破坏变化提升 major，并在对应 Dependency Assignment/本地迁移 Story 登记删除版本。不可变版本不得覆写，Seed 不提供消费者业务 alias。

### 固定 kind → error mapping

| `DependencyFailureKind` | `domain` | `MachineErrorCode` | `retryable` | compose input | serialized `details_ref` |
|---|---|---|---:|---|---|
| `dependency_retryable` | `dependency` | `DEPENDENCY_RETRYABLE` | `true` | sealed `VerifiedDetailsReference` | 其 opaque `value` |
| `dependency_non_retryable` | `dependency` | `DEPENDENCY_NON_RETRYABLE` | `false` | `None` | `null` |
| `caller_contract_violation` | `dependency` | `CALLER_CONTRACT_VIOLATION` | `false` | `None` | `null` |

升级顺序：Provider 生成并验证单一 Build Once candidate → 消费者保存完整 lock snapshot manifest → 替换精确 version/hash lock → 对同一 candidate 运行已登记契约 → 同一 digest 提升 release。回滚统一采用 `restore_previous_version_and_hash`：首次 adoption 恢复并验证无 `maia-seed` 的完整 snapshot；后续升级恢复并验证上一 exact version/wheel SHA-256及完整 snapshot。两者均不得手工重解 lock、覆写 candidate/version或删除远端制品。
