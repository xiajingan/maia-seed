# `retry-contract` 公共包技术方案

状态：implemented（S1-C01）；候选版本：`0.1.0`；最终不可变身份由 S1-P01 的 Build Once 证据确定。

## 1. 能力与所有权

- capability ID：`retry-contract`；Provider/owner：`maia-seed`；当前消费者：`maia-mud`。
- 来源：Assignment `seed-dep-mud-s2-r01-retry-contract`，已接受并映射到 `SEED-009` / `sprint-1-retry-contract`；接受不等于实现或交付完成。
- 目标：为外部依赖调用提供类型安全、失败关闭的重试结果分类，并与 Seed 公共错误能力组合。
- 结果只有 `dependency_retryable`、`dependency_non_retryable`、`caller_contract_violation` 三类。
- 仅由本模块 verifier 成功路径铸造的 opaque reference 能进入 `dependency_retryable`；原始值不能冒充已验证引用。
- S1-C01 必须在同一个受审变更中实现本设计冻结的 `seed.errors` 与 `seed.retry`，二者通过同一次 Review、质量门禁并进入同一个 Build Once candidate；缺少任一 surface 或测试即 S1-C01 失败，这是唯一执行路线且不设置独立前置。

明确排除：任何消费者、业务平台或供应商的实体、状态、错误码、URL、DTO、HTTP 映射、业务完成事件；凭据、token 签发/加密算法；重试调度、次数、退避和消费者/业务恢复动作默认值。架构字段 `recovery` 仅可承载调用方提供且经安全校验的通用提示。Seed 不读取消费者工程，消费者只保留 transport/domain adapter。

## 2. 公共契约

稳定入口为 `seed.errors` 与 `seed.retry`；依赖方向固定为 `seed.retry → seed.errors`。两者 `__all__` 必须与 stability matrix 逐字一致。

### 2.1 `seed.errors` 稳定 surface

`seed.errors.__all__` 精确为：`DetailsReferenceVerifier`、`ErrorContractError`、`ErrorEnvelope`、`MachineErrorCode`、`VerifiedDetailsReference`、`compose_error_envelope`、`serialize_error_envelope`、`verify_details_reference`。这是 `0.1.0` 首次发布前的 additive design 收敛，不保留旧私有构造 alias。

| 符号 | 稳定 shape |
|---|---|
| `DetailsReferenceVerifier` | Protocol：`verify(candidate: str) -> bool` |
| `MachineErrorCode` | `str` enum：`DEPENDENCY_RETRYABLE="DEPENDENCY_RETRYABLE"`、`DEPENDENCY_NON_RETRYABLE="DEPENDENCY_NON_RETRYABLE"`、`CALLER_CONTRACT_VIOLATION="CALLER_CONTRACT_VIOLATION"` |
| `VerifiedDetailsReference` | 不可变；只读 `value: str`；public constructor 被拒绝 |
| `ErrorEnvelope` | 不可变且不可直接构造；精确七个只读字段，见下表 |
| `ErrorContractError` | `ValueError`；只读 `reason: Literal["invalid_domain", "invalid_code", "invalid_retry_shape", "invalid_user_message", "invalid_recovery", "invalid_correlation_id", "invalid_details_candidate", "details_verifier_rejected", "details_verifier_contract_fault", "details_seal_fault", "serialization_fault"]` |
| `verify_details_reference` | `(candidate: object, verifier: DetailsReferenceVerifier) -> VerifiedDetailsReference` |
| `compose_error_envelope` | `(domain: str, code: MachineErrorCode, *, retryable: bool, user_message: str, recovery: str | None = None, correlation_id: str | None = None, details_ref: VerifiedDetailsReference | None = None) -> ErrorEnvelope` |
| `serialize_error_envelope` | `(envelope: ErrorEnvelope) -> dict[str, str | bool | None]` |

| 字段 | Python 类型 | Model 必选规则 | 安全约束 |
|---|---|---|---|
| `domain` | `str` | 必选、不可为 `None` | exact `str`；1–64；小写稳定 namespace，pattern `^[a-z][a-z0-9_.-]{0,63}$`；本能力固定 `dependency` |
| `code` | `MachineErrorCode` | 必选 | 只接受当前 enum 实例；序列化为稳定字符串值，不接受任意 `str` 冒充 |
| `retryable` | `bool` | 必选 | exact `bool`；只能由固定 kind mapping 推导，consumer 不能覆盖 |
| `user_message` | `str` | 必选、不可为 `None` | exact `str`；1–512；非纯空白、无控制字符；必须是预先脱敏的用户文案，禁止异常正文/Secret/provider payload |
| `recovery` | `str | None` | 字段必选，值可为 `None` | 非空时 exact `str`、1–512、无控制字符；仅表达通用安全恢复提示，不编码 Mud/WeCom/provider 动作 |
| `correlation_id` | `str | None` | 字段必选，值可为 `None` | 非空时 exact `str`、1–128、可见 ASCII/稳定 allowlist；不得含 tenant、Secret、provider ID 或原始异常 |
| `details_ref` | `str | None` | 字段必选，值可为 `None` | 仅 opaque reference；不承诺格式/算法，不在日志或异常 repr 复制；retryable 时只能由 compose 在验证 sealed `VerifiedDetailsReference` 后写入其 value |

七个 model 字段和序列化 key 永远存在；`recovery`、`correlation_id`、`details_ref` 的缺省值为 `None`，不得省略、改为 camelCase 或添加未知 key。

`verify_details_reference` 只接受 `type(candidate) is str`、非空且非纯空白值；`bool`/int/bytes/object/`None` 抛 `invalid_details_candidate`。verifier 是调用方信任的真实性、时效、绑定与权限边界，必须返回 exact `bool`；仅 `True` 铸造 `VerifiedDetailsReference`，`False` 抛 `details_verifier_rejected`，非 bool 或异常抛 `details_verifier_contract_fault`。verified object 不可变、不可直接构造/copy/deepcopy/pickle/subclass 伪造；value 仅返回 opaque string，不承诺 URL、codec、算法或业务 ID。Seed 不提供 provider/consumer 默认 verifier。

`compose_error_envelope` 对七字段执行 exact-type/基础安全校验。`DEPENDENCY_RETRYABLE` 只允许 `domain="dependency"`、exact `retryable=True`、`details_ref` 为当前 `seed.errors.verify_details_reference` 铸造且 seal/identity 有效的 `VerifiedDetailsReference`；compose 校验后仅把其 value 写入不可变 `ErrorEnvelope.details_ref: str | None`。两个非重试 code 只允许 `domain="dependency"`、exact `retryable=False`、`details_ref=None`。raw `str`（包括真 verified object 的 `.value`）、空白、`bool`、bytes/int/object、同名 fake、cross-version/cross-implementation object 均抛 `details_seal_fault`；code/retryable/details presence 不一致抛 `invalid_retry_shape`。retryable 与非 retryable envelope 均由这一个 public compose 和同一七字段 core 构造，无第二 factory。异常只含固定 reason，不保存 candidate、verifier 异常、opaque value 或 traceback。

`serialize_error_envelope` 只接受当前模块 seal/identity 铸造且未篡改的 envelope；合法对象的无 I/O、确定性总操作恰好输出 `domain`、`code`、`retryable`、`user_message`、`recovery`、`correlation_id`、`details_ref` 七个 snake_case key，code 为稳定字符串值，可空值仍输出为 `None`。伪造、篡改或错误对象抛 `ErrorContractError(reason="serialization_fault")`，不得对任意对象隐式调用 `str()`。

`ErrorEnvelope` 不输出 `message`、`retry_reference`、HTTP status、request ID、provider category、业务 event 或额外 details。该 dict 是 transport-neutral Python library contract，不承诺 JSON bytes、HTTP response 或 camelCase；consumer adapter 不得复制或重排为第二套稳定 error shape。`details_ref` 只能进入明确的安全响应边界，不得进入日志、metrics、异常正文、finished event 或 repr；安全序列化输出不等于观测输出。

### 2.2 `seed.retry` 稳定 surface

| 符号 | 稳定 shape |
|---|---|
| `DependencyFailureKind` | `str` enum：`DEPENDENCY_RETRYABLE="dependency_retryable"`、`DEPENDENCY_NON_RETRYABLE="dependency_non_retryable"`、`CALLER_CONTRACT_VIOLATION="caller_contract_violation"` |
| `RetryReferenceVerifier` | `seed.errors.DetailsReferenceVerifier` 的稳定直接 type alias/re-export，不定义第二个 Protocol |
| `VerifiedRetryReference` | `seed.errors.VerifiedDetailsReference` 的稳定直接 type alias/re-export，同一 runtime/type identity，不定义第二个 sealed class |
| `DependencyFailure` | 只读 `kind: DependencyFailureKind`、`reference: VerifiedDetailsReference | None`（可以 alias 名 `VerifiedRetryReference` 显示）；构造函数不公开 |
| `RetryContractError` | `ValueError`；只读 `reason: Literal["invalid_failure_kind", "failure_shape_fault", "seal_fault"]` |
| `verify_retry_reference` | `seed.errors.verify_details_reference` 的稳定直接函数 alias；不重复验证、翻译 reason 或重新铸造 |
| `classify_dependency_failure` | `(kind: DependencyFailureKind, *, reference: VerifiedRetryReference | None = None) -> DependencyFailure` |
| `dependency_failure_to_error` | `(failure: DependencyFailure, *, user_message: str, recovery: str | None = None, correlation_id: str | None = None) -> ErrorEnvelope` |

`seed.retry.__all__` 精确为：`DependencyFailure`、`DependencyFailureKind`、`RetryContractError`、`RetryReferenceVerifier`、`VerifiedRetryReference`、`classify_dependency_failure`、`dependency_failure_to_error`、`verify_retry_reference`。codec、seal、key ring、序列化 helper 和 verifier 实现均为内部符号。

### 2.3 Retry 不变量

- `RetryReferenceVerifier is DetailsReferenceVerifier`、`VerifiedRetryReference is VerifiedDetailsReference`、`verify_retry_reference is verify_details_reference` 为必测 identity；candidate/verifier 的唯一验证、seal 与 `ErrorContractError` reason 真源均在 `seed.errors`，retry 不保留 `invalid_candidate`/`verifier_*` 第二套映射。
- `VerifiedRetryReference.value` 只返回原 opaque value；复制字段、伪造同名类或跨版本/实现对象不能通过 errors 的 identity/seal 检查。
- `DependencyFailure.kind/reference` 只读，直接构造被拒绝；调用方只能获得 `classify_dependency_failure` 完成不变量检查后的实例。
- `classify_dependency_failure` 是结果唯一工厂。`dependency_retryable` 必须携带 errors 铸造的同一 sealed `VerifiedDetailsReference`；另两类禁止携带 reference。非法 kind 抛 `invalid_failure_kind`，kind/reference shape 不一致抛 `failure_shape_fault`，raw/fake/cross-implementation 抛 `seal_fault`，不返回降级结果。
- `RetryContractError` 只负责 `DependencyFailure` 分类/seal 不变量，不保存输入、异常正文或 traceback；candidate/verifier 错误原样为 `ErrorContractError`。
- 所有模型不可变；Seed 不发出业务事件，也不决定消费者恢复动作，只校验可空的通用 `recovery` 提示。

### 2.4 失败关闭矩阵

| 输入/故障 | 可产生 retryable | 机器分类 | reference | 消费者业务 finished event |
|---|---:|---|---:|---:|
| 合法值且 verifier 精确返回 `True` | 是 | `dependency_retryable` | 有 | Seed 不产生；消费者仅可按自身规则处理 |
| 明确选择不可重试且无 reference | 否 | `dependency_non_retryable` | 无 | Seed 不产生；由消费者规则决定 |
| `""`、纯空白、`None`、`bool`/int/bytes/object candidate | 否 | `ErrorContractError` / `invalid_details_candidate` | 无 | 否 |
| verifier 返回非精确 `bool` 类型 | 否 | `ErrorContractError` / `details_verifier_contract_fault` | 无 | 否 |
| verifier 返回 `False`（不可验证、过期或绑定失败） | 否 | `ErrorContractError` / `details_verifier_rejected` | 无 | 否 |
| verifier 抛异常 | 否 | `ErrorContractError` / `details_verifier_contract_fault` | 无 | 否 |
| public compose 收到 raw/真 `.value`/伪造/跨实现 verified object | 否 | `ErrorContractError` / `details_seal_fault` | 无 | 否 |
| retry alias 验证后分类 | 是 | 与 errors 同一 verified object，无二次验证/seal | 有 | Seed 不产生 |

消费者必须把非法 issuer、verifier fault 和 seal fault 留在 operational/contract fault 路径；不得包装成 retryable provider error 或业务完成事件。

### 2.5 Errors 组合边界

`seed.errors` 是 machine code、架构七字段安全 envelope、verified details 验证/seal、唯一 compose 与 serializer 真源；`seed.retry` 只持有三个 errors 直接 alias，并拥有 failure kind 与下表 mapping。`dependency_failure_to_error` 验证 sealed `DependencyFailure` 后直接调用同一 public `compose_error_envelope`；retryable 分支必须把 `VerifiedDetailsReference` 对象本身传入 `details_ref`，不得先 unwrap 成 raw string，非重试分支传 `None`。入口固定 domain/code/retryable mapping，caller 只提供已脱敏 `user_message`、通用 `recovery`、`correlation_id`；不自行组 dict、不复制 details verifier、不捕获 `ErrorContractError` 后降级。

| `DependencyFailureKind` | `domain` | `MachineErrorCode` | `retryable` | compose input | serialized `details_ref` |
|---|---|---|---:|---|---|
| `dependency_retryable` | `dependency` | `DEPENDENCY_RETRYABLE` | `true` | sealed `VerifiedDetailsReference` | 其 opaque `value` |
| `dependency_non_retryable` | `dependency` | `DEPENDENCY_NON_RETRYABLE` | `false` | `None` | `null` |
| `caller_contract_violation` | `dependency` | `CALLER_CONTRACT_VIOLATION` | `false` | `None` | `null` |

公开 envelope 不存在 `retry_reference`；verified opaque reference 只能经上表映射到 serialized `details_ref`。errors verifier `True` 铸造 verified object 后，直接 public compose 与 retry 组合路径应用同一 seal 校验；`False`/非 bool/异常、raw/空白/bool/伪造对象均无 retryable envelope。retry aliases 返回同一 verified object，不二次验证或二次 seal。非法 issuer/verifier/platform fault 不生成 ErrorEnvelope、details_ref 或 finished event。

基线源码尚未实现或导出 `seed.errors`。这只说明 S1-C01 尚未完成；S1-C01 必须在同一变更、同一 Review、同一 candidate 内实现并测试本节全部 `seed.errors` 与 `seed.retry` surface，不得临时自建第二套 envelope。

## 3. 兼容策略

- 本能力是首次 additive public surface，目标引入版本为 `0.1.0`；最终身份以 S1-P01 的 Build Once candidate 为准。
- additive symbol/可选字段升 minor；兼容 bug fix 升 patch；删除/重命名、分类语义变化、构造规则变化导致消费者破坏均升 major。
- 首次稳定后，deprecated API 发出标准 `DeprecationWarning` 并至少保留一个完整 minor；matrix 登记 deprecated 版本、最早 removal major 和迁移命令。禁止无限期 alias。
- 消费者锁定精确 wheel version 与 SHA-256，不使用 `latest`、Git、branch、editable 或 path dependency。
- 升级为 `replace_lock_then_test`；回退动作统一命名为 `restore_previous_version_and_hash`，但恢复目标分两种：
  - 首次 adoption（当前 Mud）：previous state 是 adoption 前完整 lock snapshot，其中 `pyproject.toml`、`uv.lock` 均不含 `maia-seed`。adoption 前保存相对路径、受控完整内容、每文件 SHA-256、整体 snapshot digest 与 consumer source commit；回退时原子恢复全部文件并复算摘要，确认声明与 resolved lock 均无 `maia-seed`，再运行消费者原有 lock/静态检查。
  - 后续升级：previous state 是上一精确 `maia-seed` version、wheel SHA-256及其完整 lock snapshot；恢复后验证 version/hash/resolution 与 adoption evidence 一致，再运行已登记 consumer contract。
- 回退不得手工重解析出近似旧 lock，不覆写 candidate/version，不删除远端 wheel 或 Delivery。
- 删除旧入口前，必须证明所有已登记消费者已迁移并对同一 candidate 通过契约；同步改调用方不能替代 SemVer。

## 4. 实现结构

- `src/seed/errors.py`：独立稳定 code/envelope、shape 校验与安全序列化真源；不依赖 retry、consumer 或 transport。
- `src/seed/retry.py`：直接 re-export errors 的 verifier/type/function alias，只新增 failure 分类与 kind→error mapping；所有 envelope 均调用 errors public compose。
- consumer adapter：只依赖以上公开入口，负责 transport/domain 映射与业务事件，不进入 Seed。

- `seed.retry → seed.errors` 只依赖 errors public symbols；`seed.errors` 不 import retry，无反向 callback、隐藏 raw-string 构造入口或 cycle。stubs/签名中 compose 只接受 `VerifiedDetailsReference | None`，alias 不产生重复 class/Protocol。
- verifier 负责真实性、过期和绑定校验；codec/crypto 是可替换内部实现，公共 API 不暴露算法或 provider。
- `src/seed/__init__.py` 同时增加模块名 `errors`、`retry`；符号只从各稳定子模块导入。两模块必须进入同一个源码 commit、Review、质量门禁和 Build Once candidate。
- `tests/unit/test_errors.py` 覆盖新三个 public symbols/`__all__`、candidate exact-type、verifier True/False/non-bool/异常、constructor/copy/deepcopy/pickle/subclass/fake/cross-version 负例；public compose 传 raw non-empty/空白/`True`/`False`/bytes/int/object/fake/真 `.value` 均不产生 retryable envelope，唯一直接 compose 正例传真 `VerifiedDetailsReference` 对象并序列化为恰好七 key/value；非重试 code 仍只允许 false/None，观测脱敏不回归。
- `tests/unit/test_retry.py` 断言三项直接 alias identity、同一 verified 对象无二次验证/seal；`DependencyFailure` 持有同一 verified type，raw/fake/cross-implementation 不能分类为 retryable；`dependency_failure_to_error` 直接调用 public compose 并传 verified object 本身，spy 证明不 unwrap 后重验、不调用第二 factory。唯一 retryable 链为 verify details/retry alias→classify→public compose→七字段 envelope。
- `tests/architecture/test_boundaries.py` 证明 errors 不 import retry、retry 只 import errors public symbols、无反向 callback/隐藏 raw-string 构造入口，stubs 的 compose 只接受 `VerifiedDetailsReference`，alias 无重复 class/Protocol，public symbols 与 matrix 逐字一致；mypy 拒绝 raw details_ref。
- Python library contract 机械保证 public 签名、runtime exact-type/seal、普通显式构造、copy/deepcopy/pickle/subclass/fake/cross-version 对象与 public module/root exports。本设计只有一个 public compose 构造面；但不把拥有任意进程内代码执行的攻击者使用 `object.__new__`、`object.__setattr__`、模块 `__dict__`篡改、debugger 或内存修改作为安全 sandbox 承诺；该威胁边界不放宽 public compose 对 raw/fake 的失败关闭。
- 本能力无数据库、缓存、网络、部署、UI、业务事件或消费者配置默认值。

## 5. 消费者矩阵

| 消费者 | 使用入口 | 版本/制品 | 契约命令 |
|---|---|---|---|
| `maia-mud` | 外部依赖诊断/调用的 application adapter | 精确 `maia-seed==0.1.0` + wheel SHA-256；candidate/Delivery/lock/evidence digest 一致 | 见下方 `seed_retry_contract` |

Seed provider 检查（S1-C01 建立测试后执行）：

- `seed_retry_public_and_failure_matrix`：`["uv", "run", "--frozen", "python", "-m", "pytest", "-q", "tests/unit/test_errors.py", "tests/unit/test_retry.py", "tests/architecture/test_boundaries.py", "--no-cov"]`
- `seed_retry_typecheck`：`["uv", "run", "--frozen", "python", "-m", "mypy", "src/seed"]`

Mud 已在 `config/harness.yml` 登记命令名和数组；工作目录为其 Sprint worktree：

- 工作目录：`/Users/ws/space/git/mai/maia/maia-mud/.harness/worktrees/sprint-2-wecom-capability-api`
- `seed_retry_contract`：`["uv", "run", "python", "scripts/verify_seed_retry_contract.py"]`

命令已登记，但脚本当前尚未创建，必须作为 S1-V01 前置建立，且只针对 `HARNESS_DEPENDENCY_ARTIFACT` / wheel 对应的不可变 candidate 与精确锁运行，禁止源码树或 editable/path 安装。`RC-VALID-001` 通过 `verify_retry_reference` 直接 alias 取得与 errors 同一 verified object，分类后由唯一 public compose 产生 retryable 七字段 envelope。`RC-INVALID-001` 直接 public compose 传 raw/空白/bool/bytes/object/fake/真 `.value` 均失败，只有 verified object 正例成功。`RC-ISSUER-001` 证明非法 issuer 返回不产生 `VerifiedDetailsReference`/`DependencyFailure`/envelope。`RC-FAULT-001` 证明 verifier/platform fault 不产生 retryable provider failure、details_ref 或 finished event。wheel 中只能存在 verified-object 的唯一 public compose 构造 API，不以 underscore 或模块隐私作为安全边界。Mud 不复制 details verifier/seal、retry validator、mapping、envelope 或 serializer。任一负例未执行、reason/七字段 shape 不符或 raw/fake 通过 public compose 时，consumer contract 必须退出非零；不得用全量泛化测试冒充。

## 6. 交付方案

1. S1-C01 在同一受审变更实现 `seed.errors` 与 `seed.retry` 全部冻结 surface；任一 API/测试缺失即失败。S1-Q01 随后通过 `command_groups.precommit` 与质量阈值，提交并冻结同一源码 commit。
2. S1-P01 对 `maia-seed` 执行一次 `package_build`（`["uv", "build"]`），登记 SemVer、完整 source commit 和 wheel SHA-256；不得重建候选。
3. candidate 同时生成签名、SBOM、provenance，并由配置的真实 verifier 形成 receipt。
4. S1-V01 把同一 candidate 登记到 session，运行 Seed 检查和 Mud `seed_retry_contract`。
5. S1-L01 发布绑定 assignment/request digest、candidate 和供应链证据的 `dependency-package` Delivery。
6. Mud adoption 前保存第 3 章定义的完整 lock snapshot manifest，再验证 Delivery、替换精确 version/hash lock、运行同一消费者命令并保存 adoption evidence；任何 digest 不一致均失败关闭。首次 adoption 失败恢复无 `maia-seed` 的完整 snapshot，后续升级失败恢复上一 exact version/hash snapshot。
