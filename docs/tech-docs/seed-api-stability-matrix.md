# Seed API stability matrix

状态：`retry-contract` 已由 `maia-seed==0.1.0` 不可变 Delivery 发布；`retry-reference-foundation` 为 additive `0.2.0` 设计，尚未实现或构建 candidate。

| Task | Stable module | Public symbols | Change | Consumer | Removal |
|---|---|---|---|---|---|
| SEED-001 | `seed.config` | `SettingsLoader`, `SettingsSource`, `RedactedSettingsSummary`, `ConfigLoadError` | additive | `mud.test.tenant-config` | N/A |
| SEED-002 | `seed.context` | `RequestContext`, `ContextToken`, `ContextScope`, `ContextError` | additive | `mud.test.tenant-context-isolation` | N/A |
| SEED-013 / `seed-dep-mud-p0-002-secrets` | `seed.secrets` | `SecretReference`, `SecretProvider`, `SecretLease`, `SecretBuffer`, `SecretProviderError` | additive；已有实现等待 Seed 主动接受输入并纳入本地 Sprint 后才可交付 | `mud.test.tenant-secret-lifecycle` | N/A |
| SEED-021 | `seed.oceanbase` | `OceanBaseRuntime`, `OceanBaseSettings`, `OceanBaseSessionScope`, `DialectCapabilities`, `DependencyHealth`, `OceanBaseRuntimeError` | additive | `mud.test.oceanbase-lifecycle` | N/A |
| S1-D01 / `seed-dep-mud-s2-r01-retry-contract` | `seed.errors` | `DetailsReferenceVerifier`, `ErrorContractError`, `ErrorEnvelope`, `MachineErrorCode`, `VerifiedDetailsReference`, `compose_error_envelope`, `serialize_error_envelope`, `verify_details_reference` | additive；已由 `0.1.0` Delivery 发布；`0.2.0` 仅加固内部 provenance predicate，合法 surface/七字段不变 | `maia-mud` / `seed_retry_contract` | N/A |
| S1-D01 / `seed-dep-mud-s2-r01-retry-contract` | `seed.retry` | `DependencyFailure`, `DependencyFailureKind`, `RetryContractError`, `RetryReferenceVerifier`, `VerifiedRetryReference`, `classify_dependency_failure`, `dependency_failure_to_error`, `verify_retry_reference` | additive；已由 `0.1.0` Delivery 发布；三项 errors 直接 alias identity 不变；`0.2.0` classifier/compose 统一 provenance predicate | `maia-mud` / `seed_retry_contract` (`RC-VALID-001`, `RC-INVALID-001`, `RC-ISSUER-001`, `RC-FAULT-001`) | N/A |
| S2-D01 / `seed-dep-mud-s2-r01-retry-reference-foundation` | `seed.crypto` | `CryptoContractError`, `KeyProvider`, `AeadKeyRing`, `AeadCipher`, `load_aead_key_ring`, `create_aead_cipher` | additive planned `0.2.0`；通用 key loading/rotation、AEAD、nonce allocation 唯一真源；candidate not built | `maia-mud` / `seed_retry_foundation_contract` (`RRF-FOUNDATION-001`, `RRF-OWNERSHIP-001`) | N/A |
| S2-D01 / `seed-dep-mud-s2-r01-retry-reference-foundation` | `seed.retry_reference` | `RetryReferenceFoundationError`, `RetryReferencePayloadVerifier`, `RetryReferenceCodec`, `RetryReferenceSnapshot`, `create_retry_reference_codec`, `freeze_retry_reference_snapshot` | additive planned `0.2.0`；组合 `seed.crypto` 的 framing/time/bound-verifier/snapshot；不定义 crypto 或第二 seal；candidate not built | `maia-mud` / `seed_retry_foundation_contract` (`RRF-PROVENANCE-001`, `RRF-SNAPSHOT-001`, `RRF-FOUNDATION-001`, `RRF-OWNERSHIP-001`, `RRF-HTTP-001`, `RRF-SOAK-001`) | N/A |

## `retry-contract` 治理记录

| 字段 | 值 |
|---|---|
| capability / task | `retry-contract` / `S1-D01` |
| trace | Assignment `seed-dep-mud-s2-r01-retry-contract` / digest `sha256:3e85907c98f7188fbb7b23b6d3c561b6412c634d9ab8bfa3903e1b00e30300ea`；accepted Response digest `sha256:b944d6600b9d1af3cc47ebc39f1a8ade64b5066515563f57118fe8f8bbd587a9`；session/request digest `sha256:d62c78dac0210a60e11e4559c706749eb5724aa2828aaf59cf14b0355743f32d` |
| provider / consumer task | `maia-seed` `sprint-1-retry-contract` / `S1-D01`；`maia-mud` `sprint-2-wecom-capability-api` / `S2-D01`（Assignment source reference `S2-R01`） |
| target / consumer range | 已发布 `0.1.0` / 精确 `maia-seed==0.1.0` + wheel SHA-256 `b1e5af73b9571ee730212f51f76d858e1944ff755ceb1531c63cfc5b9546303c`；Delivery `maia-seed.retry-contract.0.1.0.b1e5af73`，manifest digest `sha256:e175941ef219e908375e4fdcec997c1d2aa23914f0ce252fcf22c81ca64553e4` |
| deprecated / earliest removal | N/A / N/A（首次 additive；后续弃用至少保留一个完整 minor，破坏删除升 major） |
| consumer workdir | `/Users/ws/space/git/mai/maia/maia-mud/.harness/worktrees/sprint-2-wecom-capability-api` |
| consumer command | `seed_retry_contract` = `["uv", "run", "python", "scripts/verify_seed_retry_contract.py"]`；已对上述 `0.1.0` wheel 通过 RC-VALID/INVALID/ISSUER/FAULT |
| upgrade / rollback | `replace_lock_then_test` / `restore_previous_version_and_hash`；首次 adoption 原子恢复 adoption 前完整 `pyproject.toml` + `uv.lock` snapshot（相对路径、受控完整内容、逐文件 SHA-256、整体 snapshot digest、consumer source commit），复算摘要、验证声明/resolved lock 均无 `maia-seed`并运行原有 lock/静态检查；后续升级恢复上一 exact version/wheel SHA-256 + 完整 snapshot，验证 adoption evidence并重跑 contract |
| error shape | `ErrorEnvelope` 及 serializer 恰好七个必选 snake_case 字段/key：`domain: str`、`code: MachineErrorCode`、`retryable: bool`、`user_message: str`、`recovery: str \| None`、`correlation_id: str \| None`、`details_ref: str \| None`；后三者值可为 `None` 但 key 不省略，无 `message`/`retry_reference`/额外 key |
| details API | `DetailsReferenceVerifier.verify(candidate: str) -> bool`；`VerifiedDetailsReference.value: str`；`verify_details_reference(candidate: object, verifier: DetailsReferenceVerifier) -> VerifiedDetailsReference`，仅 exact non-empty `str` + verifier exact `True` 铸造 sealed object |
| errors API | `compose_error_envelope(domain: str, code: MachineErrorCode, *, retryable: bool, user_message: str, recovery: str \| None = None, correlation_id: str \| None = None, details_ref: VerifiedDetailsReference \| None = None) -> ErrorEnvelope`；retryable 只接受 errors 铸造的 sealed object，非重试 code 只允许 false/None；`serialize_error_envelope(envelope: ErrorEnvelope) -> dict[str, str \| bool \| None]` |
| errors reasons | `invalid_domain`、`invalid_code`、`invalid_retry_shape`、`invalid_user_message`、`invalid_recovery`、`invalid_correlation_id`、`invalid_details_candidate`、`details_verifier_rejected`、`details_verifier_contract_fault`、`details_seal_fault`、`serialization_fault` |
| retry composition API | `dependency_failure_to_error(failure: DependencyFailure, *, user_message: str, recovery: str \| None = None, correlation_id: str \| None = None) -> ErrorEnvelope`；caller 不能传入 domain/code/retryable/details_ref |
| alias identity | `RetryReferenceVerifier is DetailsReferenceVerifier`；`VerifiedRetryReference is VerifiedDetailsReference`；`verify_retry_reference is verify_details_reference`；无第二 Protocol/class/validator/seal/reason mapping |
| retry reasons | `RetryContractError.reason` 精确为 `invalid_failure_kind`、`failure_shape_fault`、`seal_fault`；candidate/verifier 类错误原样为 `ErrorContractError` |
| composition | 唯一路线：S1-C01 在同一变更、Review、质量门禁和 Build Once candidate 内实现 `seed.errors` + `seed.retry`；缺任一 module/API/tests即失败。依赖仅 `seed.retry → seed.errors` public API；所有 envelope 经唯一 public compose，verified object 唯一进入 serialized `details_ref`，consumer 不复制 validator/shape/mapping/serializer |
| Python boundary | `0.2.0` 机械拒绝 public exact class 经 `object.__new__`/`object.__setattr__` 填任意 value/seal、copy/pickle/subclass/fake/cross-version/cross-implementation；classifier、failure validation、compose 复用同一 provenance verdict。不承诺抵御提取/替换模块私有 provenance、module `__dict__` 篡改、debugger 或内存修改 |
| provider checks | `tests/unit/test_errors.py`、`tests/unit/test_retry.py` 与 `tests/architecture/test_boundaries.py` 已覆盖 `0.1.0` surface；`0.2.0` 增补 reflection provenance 一致性并与 foundation checks 一起执行 strict mypy |

## `retry-reference-foundation` 治理记录

| 字段 | 值 |
|---|---|
| capability / task | `retry-reference-foundation` / `S2-D01` |
| trace | session `seed-dep-mud-s2-r01-retry-reference-foundation` / request digest `sha256:6f9cc9d25900fd7a71f9218cd82c6f7388435f131177830c41eb6086dab07874` / status `provider-planning` |
| provider / consumer | `maia-seed` `sprint-2-retry-reference-foundation` / `S2-D01`；`maia-mud` `sprint-2-wecom-capability-api` / `S2-D02` |
| current / target | immutable `0.1.0` / additive planned `0.2.0`；deprecated/removal 均 N/A |
| crypto surface | `seed.crypto.__all__` 精确为本页 S2 crypto 行六个 symbols；KeyProvider/key-ring/AEAD/nonce/rotation 仅归 crypto |
| foundation surface | `seed.retry_reference.__all__` 精确为本页 S2 foundation 行六个 symbols；不含 KeyProvider/key-ring/AEAD/random/clock/nonce seam，也无第二 verified/failure/envelope 类型 |
| provenance | 合法 verifier 铸造对象可 classify/compose；exact-class reflection fake 固定 `seal_fault` / `details_seal_fault`；合法 `0.1.0` signature、alias、mapping 与七字段不变 |
| crypto invariants | active 恰1、previous≤8、32-byte copied keys；crypto frame `ac1.<kid>.<base64url(nonce+ciphertext)>`；active seal、active+previous open；rotation 创建新 immutable ring/cipher |
| nonce | public surface无RNG/nonce/counter/factory；仅同一ring generation共享active-key allocator/guard；重复load/跨ring/进程/重启仅CSPRNG概率边界。S2-C01 collision测试随实现提交并进入unit suite；S2-Q01 PASS quality JSON绑定source-clean `source_commit`；Mud consumer不声称验证guard |
| snapshot | entries `1..32`、slot `1..64`、payload `1..2048`、reference≤4096；freeze 原子 framing/clock/crypto/round-trip/`verify_retry_reference` seal；snapshot仅保存slot→sealed tuple，issue不读cipher/key/nonce/clock/verifier/raw |
| crypto reasons | `CryptoContractError.reason: Literal["invalid_key_ring", "key_provider_contract_fault", "invalid_cipher", "invalid_crypto_input", "nonce_allocation_fault", "encryption_fault"]`；open所有 rejection统一 `None` |
| foundation reasons | `RetryReferenceFoundationError.reason: Literal["invalid_input", "snapshot_fault", "unknown_slot"]`；bound verifier所有 rejection exact `False`且永不抛 |
| dependency | `seed.retry_reference → seed.crypto`；`seed.retry_reference → seed.retry → seed.errors`；无反向 import/cycle；consumer仅保留opaque payload/binding adapter |
| consumer command | `seed_retry_foundation_contract = ["uv", "run", "python", "scripts/verify_seed_retry_foundation.py"]`；正式入口只依赖candidate artifact/package/version/SHA及既有consumer evidence环境，不读取provider root/source commit或运行provider工作区test；旧RC显式0.2复用，公开snapshot/foundation/HTTP/300秒soak成功后动态追加，任一缺失失败 |
| module origin | contract断言前在无预载`seed*`的隔离进程逐一验证`seed.errors`/`seed.retry`/`seed.crypto`/`seed.retry_reference`及根包来自同一精确candidate wheel成员，distribution version/SHA/alias identity一致；HTTP/soak测试进程也必须输出同candidate origin witness，site-packages/source/editable/另一wheel/混合origin均失败 |
| case evidence | RC四项来自显式0.2旧contract JSON；PROVENANCE来自forged双reason+合法链；SNAPSHOT只验证wheel公开四slot sealed、重复issue同一对象、调用方mutation后issue只读及unknown slot，不证明内部guard；FOUNDATION来自previous/tamper/expiry/namespace/binding；OWNERSHIP/HTTP/300秒SOAK保持固定consumer证据 |
| provider checks | S2-C01在`tests/unit/test_crypto.py`提交强制collision场景并由登记unit/precommit suite执行；S2-Q01拒绝dirty/untracked/uncommitted source，整体quality PASS JSON写完整`source_commit`；不要求额外node、命令结果或日志摘要字段 |
| provider commands | `uv run --frozen pytest -q tests/unit/test_errors.py tests/unit/test_retry.py tests/unit/test_crypto.py tests/unit/test_retry_reference.py tests/architecture/test_boundaries.py --no-cov`；`uv run --frozen mypy src/seed tests`；S2-P01读取PASS quality JSON并要求current commit exact等于其`source_commit` |
| public failure matrix | load ring：shape→`invalid_key_ring`、provider fault→`key_provider_contract_fault`；create cipher→`invalid_cipher`；seal：input/nonce/encrypt三reason；open→bytes或`None`；create codec/bound verifier factory→`invalid_input`；bound verifier→exact bool；freeze shape/runtime→`invalid_input`/`snapshot_fault`；issue→`unknown_slot` |
| wire / legacy | retry reference wire v1组合crypto frame；consumer legacy format只读、不签新引用，最长保留旧`TTL+skew`，契约通过且窗口结束后删除 |
| upgrade / rollback | 保存完整 consumer declaration/lock/adapter snapshot → 锁定同一 `0.2.0` wheel+SHA → foundation contract；失败原子恢复精确 `0.1.0`/SHA snapshot，不重解 lock、不覆写/删除 artifact |
| Delivery | S2-P01仅从与quality JSON `source_commit` exact相同且无构建影响worktree变化的commit Build Once；package state写同一`source_commit`与该JSON文件SHA字段`quality_evidence_sha256`，candidate/Delivery继承两者并绑定request digest、wheel SHA、签名、SBOM、provenance与真实receipt；staged/release不重建 |

兼容策略：首次稳定版本发布后，弃用发出标准 warning 并至少保留一个完整 minor；破坏变化提升 major，并在对应 Dependency Assignment/本地迁移 Story 登记删除版本。不可变版本不得覆写，Seed 不提供消费者业务 alias。

### 固定 kind → error mapping

| `DependencyFailureKind` | `domain` | `MachineErrorCode` | `retryable` | compose input | serialized `details_ref` |
|---|---|---|---:|---|---|
| `dependency_retryable` | `dependency` | `DEPENDENCY_RETRYABLE` | `true` | sealed `VerifiedDetailsReference` | 其 opaque `value` |
| `dependency_non_retryable` | `dependency` | `DEPENDENCY_NON_RETRYABLE` | `false` | `None` | `null` |
| `caller_contract_violation` | `dependency` | `CALLER_CONTRACT_VIOLATION` | `false` | `None` | `null` |

升级顺序：Provider 生成并验证单一 Build Once candidate → 消费者保存完整 lock snapshot manifest → 替换精确 version/hash lock → 对同一 candidate 运行已登记契约 → 同一 digest 提升 release。回滚统一采用 `restore_previous_version_and_hash`：首次 adoption 恢复并验证无 `maia-seed` 的完整 snapshot；后续升级恢复并验证上一 exact version/wheel SHA-256及完整 snapshot。两者均不得手工重解 lock、覆写 candidate/version或删除远端制品。
