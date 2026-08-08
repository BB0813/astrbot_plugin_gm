# 项目记忆

累计反思 38 次

## 仓库背景

仓库 `mjy1113451/astrbot_plugin_gm` 是 AstrBot 群管理类插件，Issue/PR 常涉及命令解析、撤回、群管理权限、按群配置、OneBot 适配器兼容、配置 schema 与 README 同步。Issue 中可能出现旧插件名或相近插件名（如 `astrbot_plugin_group_admin`），分析时需确认与当前仓库/插件注册名是否一致，避免把推断写成事实。

## 反模式（最关键警示）

- **结构化输出校验失败 ≠ 信息不足**：看到 `expected <SUGGESTED_TITLE>` 等字段校验错误时，应**仅修复字段输出**（如把"无建议"改成实际建议），不得把所有判断都退化为"无法评估"/`other`/空标签/无建议。**字段校验失败仅触发输出修复，不得影响分类/可行性/标签/标题等实质性判断**。
- 标题字段**禁止写"无建议"**；原标题已清晰应标"可保留"或给轻量规范化版。标题为空、"。"等无意义时必须改写。
- 标签在不确定体系时也应给通用候选并注明需映射，**不能留空**；可行性在信息不足时也应有条件判断，不能写"无法评估"。
- 格式失败应局部修复，**保留可判断信息**，不应整体降级。
- **"quick"策略不能成为零审查的借口**：涉及权限/撤回/缓存等横切关注点的 PR，最低限度必须覆盖安全相关检查和结构性检查（schema 一致性、命令签名、关键风险点）。
- **PR 描述数字与实际 diff 不一致**需主动指出（如声称 +520/-103 实际 +494/-52），不放过。
- **chore/reflection 批量 commit 污染提交历史**：多个相同信息的 chore commit 应在审查中标记为提交历史质量问题，可建议 squash。增量审查时优先识别哪些是"有价值的代码变更"、哪些是"chore 噪音"。

## Issue 分析经验

### 1. 分类、优先级、标签与标题

- 明确运行时报错、命令参数类型错误、用户反馈"更新后仍存在"时，主分类应为 `bug`；若是命令参数解析，可辅助 `command`、`parser`、`compatibility`、`needs-info`。
- 权限/配置粒度调整（按群独立配置头衔/管理/踢人/禁言）应归为 `enhancement`，不是 `other`；辅助 `configuration`、`permission`、`group-management`、`needs-discussion`，移除旧机制需评估 `breaking-change`。
- "被禁言/禁我用户私信申请解禁并由管理员审批"是新增审批工作流，应归为 `enhancement/feature + medium`，不是 bug/other；辅助 `group-management`、`moderation`、`permission`、`configuration`、`private-message`、`approval-flow`、`needs-discussion`。**medium 而非 low 的关键理由**：涉及代为执行群管理动作的敏感操作，存在越权/误批风险。
- `/撤回 N` 因 OneBot 不支持 `get_group_msg_history` 而不可用时，核心是 `compatibility`：本地缓存/回退通常为 `enhancement + medium`；仅询问提示/能力限制可为 `question` 或 `documentation + low`；文档承诺通用支持而常见环境不可用也可视为兼容性 bug。
- `medium` 适用于核心命令局部不可用、权限配置影响多群但非阻断、群管理命令提示成功但实际未生效。插件启动/加载失败、导入失败、装饰器注册失败、越权、误踢/误撤大量消息等应考虑 `high`。
- 标题中 `[bug][medium]`、`[enhancement][medium]` 是信号但需结合正文和代码。涉及"禁言/禁我申请解禁"时标题要覆盖两种状态；涉及批量撤回要覆盖普通与按用户两种形式。
- 标签推荐要贴合模块和根因；功能审批流至少给 `enhancement` + 模块/权限/配置/讨论候选；头衔 bug 至少给 `bug`、`command`、`group-management`、`title/special-title`、`onebot/compatibility`；撤回历史接口类常用 `enhancement`/`question`/`documentation`、`compatibility`、`command`、`recall`、`message-history`、`onebot`、`group-management`、`needs-info`。

### 2. AstrBot 命令参数与撤回逻辑

- 对 `@filter.command(...)` 命令，必须区分错误发生在启动/插件加载/命令注册阶段，还是用户调用后的业务函数阶段。AstrBot 根据函数注解提前转换参数，函数体内 `try/except int(count)` 无法兜底；复杂语法入口优先用字符串/原始事件解析。
- 遇到 `参数 count 类型错误`、`count(int)=0` 等，应优先检查命令函数签名、类型注解和默认值（如 `count: int = 0/1`），并确认触发命令、堆栈、AstrBot 版本、插件版本/commit、旧缓存。
- 修复方向通常是命令入口用 `str`/可选原始参数接收，内部统一转换、校验并给友好提示，同时明确 `0`、空字符串、`None`、负数、过大值边界。
- `/撤回 N` 应理解为撤回"当前命令之前的 N 条消息"，不能优先撤回命令自身；`count=1` 是最小必测。历史或缓存结果都必须排除当前 `event.message_id`，注意消息 ID 类型、正/倒序、消息不足、超时/权限不足。
- 撤回类要区分：参数解析问题、业务语义问题（撤回上一条还是命令自身）、历史接口问题（`get_group_msg_history` 不支持/返回结构差异）、引用撤回、按用户撤回。
- `/撤回 @用户 N` 与 `/撤回用户 @用户 N` 要区分"功能缺失、入口未路由、参数解析失败、文档/提示不清"。若已有 `recall_user_cmd`、`_extract_at_qq` 等，修复宜抽取共享 helper。`@用户` 解析应基于消息 segment/user_id/At 对象，不要按昵称文本或空格 split。
- **批量撤回的完整技术考量**（看似简单，实则涉及）：① 消息历史获取（OneBot 接口差异）；② 权限检查（bot 必须是群管理/群主）；③ 时间窗限制（QQ 普通成员只能撤回 2 分钟内，管理员可撤回更久）；④ 限流保护（避免一次请求过多导致风控）；⑤ 部分失败处理（N 条中部分失败如何提示）；⑥ 自身消息过滤（排除命令本身）；⑦ bot 消息处理（撤回自己的 vs 他人的，独立写入路径）；⑧ 撤回目标人员过滤；⑨ 引用撤回是短期替代提示，不等于真正 fallback。
- **撤回类 PR 强制检查清单**：每条都需逐项确认，不得仅检查"功能能不能跑通"。
- **本地缓存撤回模式（主路径失败→本地缓存兜底）**：处理 OneBot 接口兼容性问题的推荐骨架。设计要点：① 按群隔离（`{str(group_id): deque[dict]}`）② 最小化存储（仅 `message_id + user_id`，避免缓存内容）③ 显式上限（deque maxlen，建议 ≥ 4×N）④ 写入入口对称（用户消息走 `on_group_message`，bot 消息走 `after_message_sent`）⑤ 回退标识（"（来自本地缓存）"）⑥ 文档明示重启不可恢复 ⑦ 写入失败 try/except + debug 日志不影响主流程 ⑧ bot 消息独立写入路径（置于业务早退之前）⑨ 提示语区分"接口不可用 / 临时错误 / 历史为空"。
- 历史接口空返回的语义必须区分：可能是不支持/retcode 非 0/参数不兼容/网络异常/权限不足/历史不足等 5+ 种情况，不可一概写"不支持"。
- 本地缓存撤回需按群维护最近消息元数据（尽量只存 `message_id`、群号、发送者、时间/顺序，避免缓存完整内容），设置上限/过期，处理重启丢失、在线后才可用、并发顺序、多群隔离、当前命令过滤、message_id 类型、撤回时限、bot 权限和隐私边界。

### 3. 权限、群管理 API 与按群配置

- "按群独立配置"通常是权限模型调整，需区分功能权限、配置权限、插件管理权限；遵循最小权限原则，避免泛化"插件管理员"替代具体动作授权。
- 关键点：`plugin_admins`、`group_overrides`、`get_group_setting`、`title_admins`、`group_admin_admins`、`kick_admins`、`group_admins`，及对应 `has_*_admin_rights` 权限 helper。
- 按群配置看三层：业务读取层是否统一走 `get_group_setting`；命令管理层是否正确写入/查看/清除 `group_overrides[group_id][key]`；配置 UI/schema/README 是否表达"全局默认 + 群级覆盖"。
- 配置边界：`0` 可能表示关闭且必须能覆盖全局，不能被 `dict.get`/假值判断误当缺失；空列表是覆盖为空还是回退全局，`None`、缺失 key、空字符串要区分；旧配置迁移不能忽略。
- 群管理 API "返回成功但实际未生效"按链路排查：命令解析→权限判断→API 参数→适配器兼容→API 返回值→状态回读→用户提示。OneBot/NapCat/Lagrange/go-cqhttp 对 `special_title=""`、`duration=-1/0/不传`、返回值和缓存刷新语义可能不同。
- `/取消头衔` 等不能仅根据 action 返回值提示成功；需考虑 bot 是否管理员/群主、权限是否高于目标、目标是否群主、QQ 限制、客户端缓存/延迟。可用 `get_group_member_info` 回读确认。
- 头衔清空要严格区分 `special_title=""`、`" "`、空白字符、`None`、字段缺失及 `duration=-1/0/不传`；`strip()` 会把空格头衔误判为已清空。`special_title=" "` 兜底本质是兼容空白头衔，不是恢复默认。
- **本仓库"禁言/禁我"语义至少 3 层**：① 群管 API 禁言；② 插件内部"禁我"自怼；③ 申请解禁工作流中的"待审批禁言状态"。分析任何禁言相关 issue 时必须先确认指的是哪一层，不能混为一谈。
- 权限类改动测试：全局配置、按群覆盖、未配置回退、空列表/0 覆盖、多群隔离、普通用户不得获得踢人/管理/头衔权限、旧配置升级后行为。

### 4. PR/代码审查经验

- 加载级问题（`SyntaxError`、导入失败、装饰器注册失败）影响高，即使改动小也应高优先级审查。建议至少要求 `python -m py_compile main.py`、`python -m compileall .` 或最小 AstrBot 插件加载验证。**`ast.parse` ≠ 真实加载**（不执行装饰器、不触发命令注册），不能作为加载验证的替代品。
- `async def` 中一旦出现 `yield` 就变为 async generator，不能 `return <value>`，也不能按普通 coroutine `await func()` 获取返回值。被调用方以 `await func(...)` 获取业务值的 helper，函数体内不得出现 `yield`。
- 命令 handler 与普通 helper 的响应方式要区分：顶层 AstrBot 命令 handler 可使用 `yield event.plain_result(...)`；普通 helper 如需发送消息，优先统一调用 `_send`；返回 `True/False` 的 `require_*` 权限 helper 不应使用 `yield`。
- 审查从 `yield event.plain_result(...)` 改为 `await self._send(...)` 时，必须验证行为等价：事件类型支持、是否真的发送、异常处理、响应时机、与 handler 调用链兼容。
- 对集中式权限 helper（如 `_moderation_require_admin_msg`）要抽样所有调用语义：成功返回 `True`，失败发送提示并返回 `False`，调用点 `if not await ...: return` 短路正确；若有 18 处调用点，影响面广，不宜只看单点。
- **历史 PR 风险在新 issue 中继续适用**：新增 helper 必须保持纯 `async def`、避免在 `await` 业务 helper 中混入 `yield`，这种串联分析应成为标准动作。
- **早退语句吞噬共享逻辑**是高频陷阱：基础设施写入（缓存、统计、日志、监控）必须置于业务早退（`if not enabled: return` / `if not in list: return`）**之前**，否则功能开关关闭时连带基础设施也不工作。bot 消息的本地缓存写入必须独立于任何业务早退链。
- **注释即承诺原则**：注释描述的行为与代码实际不符，无论大小都应标记（项目级代码卫生问题，不是个别疏漏）。
- **`defaultdict(factory)` 的微妙陷阱**：`.get()` 安全，但 `if k in d` / `dict(d)` / `copy.copy(d)` / `json.dumps` 等操作会无差别创建空条目。**推荐 `{}` + 显式 `setdefault(key, factory())`**，避免副作用传播。
- **falsy 判空 vs 严格判空**：对外暴露的 helper 优先用 `x is None` / `x == ""` 严格判空，避免误丢合法值（`0`、空集合等）；内部业务 helper 若确认业务值不会为 0，可保留 falsy 判空但需在 docstring 注明约定。
- **增量审查的结构性盲区**：只看 diff 不足以验证完整行为，必须做"对接面扫描"——快速浏览 `__init__`、注册装饰器、其他调用点，验证修改未破坏既有假设。增量审查应主动补做：① 读取 README diff 确认文档与代码一致 ② 走一遍受影响命令的端到端流程 ③ 对权限、时限、限流等横切关注点做"未变更则保留、变更则重审"的清单化检查 ④ 抽样验证对称路径（如 `recall_cmd` 与 `recall_user_cmd` 的缓存回退分支对称性）。
- **审查评分校准**：涉及撤回/缓存等核心命令回退路径的 bug，无论代码量大小，影响面涉及「绝大多数未启用某配置的群组」时，评分上限不超过 5/10，决策应为 request_changes 或 comments。
- approve 可以，但若缺少真实 AstrBot 加载和命令验证，尤其涉及框架消息发送方式变化或撤回/缓存路径变化，评分不宜给满分。

### 5. 私聊申请与审批工作流

- **私聊事件无 `group_id` 是硬约束**：私聊触发群管理动作时必须要求用户提供群号，或复用/维护禁言记录；还要校验申请人确属目标群、确处于群禁言或插件内部"禁我"状态。
- 群禁言与插件内部禁用可能是两套状态，解禁接口和存储需先核对，不能混为一谈。
- **审批必须用申请 ID / 引用回复 / 专用命令**（如 `同意 #123`、`驳回 #123 原因`、`/解禁审批 同意 123`），**不能只靠"同意/驳回"关键词**——否则多用户/多群并发无法区分、上下文丢失、重复审批无法幂等。
- 审批工作流要处理：多管理员并发、重复审批、重复申请、超时过期、重启恢复、幂等、申请消息长度限制（截断）。
- 自动解禁是敏感操作：审批者必须是插件管理员或被授权者；管理群审批也要校验发言者 `sender.user_id`（避免机器人/被 at 误触发）。调用 `_unmute_member`、`_send_private_msg`、`_send_group_text` 等 helper，处理 bot 不在群/无权限、用户已解禁/不在群、私信或群通知发送失败、OneBot `set_group_ban(0)` 解禁语义差异。
- 申请说明可能含隐私，只转发到配置的可信管理员或管理群；日志审计必要。
- 新增审批流配置需同步 `_conf_schema.json`、README、帮助命令、默认配置，如启用开关、审批管理员 QQ/管理群、有效期、是否群内通知、是否覆盖群禁言和"禁我"两种状态。建议预列配置项：`appeal_enabled`、`appeal_admin_qqs`、`appeal_admin_group`、`appeal_expire_minutes`、`appeal_max_concurrent`、`appeal_privacy_redact`、`appeal_cover_mute`、`appeal_cover_block_self`。
- 可参考 `pending_join_requests` 模式，但**不能假设其可直接适用于私聊解禁**。
- 工作量分两档：**最小可用实现中等偏低**（监听私聊+转发+编号审批+调 `_unmute_member`）；**完整可靠实现中等偏高**（持久化+并发幂等+过期+多适配器兼容+完整 schema/README 同步）。

### 6. 合入外部仓库/外部代码类 Issue

- 本质是"功能请求 + 代码复用"，分类为 `enhancement` + `merge-request`/`external-repo`（如仓库有此类标签）。
- 必须额外评估：① 外部仓库代码质量与风格统一性；② 依赖与 AstrBot/OneBot SDK 版本兼容性；③ 许可证兼容性（原仓库 LICENSE）；④ 维护责任与后续同步策略；⑤ 重构 vs 合并（是否应抽取通用逻辑而非直接复制）；⑥ 配置 schema 是否需扩展；⑦ bot 权限要求。
- 建议主动询问：原仓库地址、当前命令的失败行为、目标 OneBot 适配器、外部仓库的代码细节、是否考虑直接上游贡献而非合入。
- 合入动作本质是外部代码引入，分析时不可假定"已有部分实现"——即使项目记忆中有 `recall_cmd` 等，也需核实当前 main.py 的实际命令签名。
- 标签推荐：`enhancement` + `merge-request`/`external-repo` + 对应功能标签 + `license-check`（建议）+ `needs-info`。

### 7. 重复检测与流程注意

- 重复检测不能只依赖标题，**措辞要稳**：无历史列表时写"暂未发现"并列出建议检索关键词，**不能写"未检测到重复"或"无重复"**。
- 参数错误搜：`count(int)=0`、`参数 count 类型错误`、`撤回`、`recall_cmd`、`recall_user_cmd`、`filter.command`。
- 撤回自身搜：`/撤回 1`、`撤回指令本身`、`上一条消息`、`get_group_msg_history`、`message_id`。
- 历史接口/兼容性搜：`get_group_msg_history`、`group_msg_history`、`消息历史`、`当前 OneBot 实现不支持`、`引用消息撤回`、`按用户撤回`、`@用户`、`message-history`、`delete_msg`、批量撤回相关 `batch recall`、`astrbot_plugin_batchrecall`。
- 按群权限/配置搜：`按群配置`、`群独立`、`权限`、`踢人`、`管理`、`头衔`、`禁言阈值`、`mute_kick_threshold`、`group_overrides`、`group_admins`、`配置显示`；头衔问题搜 `取消头衔`、`special_title`、`set_group_special_title`、`空格头衔`、`恢复默认头衔`、`duration`、`NapCat`、`Lagrange`、`go-cqhttp`。
- 申请解禁/审批流搜：`申请解禁`、`解禁申请`、`禁言申诉`、`禁我`、`私信`、`审批`、`管理员审批`、`解除禁言`、`set_group_ban`、`mute`、`unmute`、`appeal`、`pending_join_requests`、`申诉`。**重复判断要比较完整用户故事链**（私聊申请→管理员审批→自动解禁→通知），私聊解禁 vs 群内解禁应标"关联"而非"重复"。
- 同命令/同模块但症状、触发路径、修复点不同的 Issue 应标关联而非重复。
- 对信息不足的 Issue，仍应给有条件的可行性判断：列出需要补充的证据，以及常见代码结构下的预估工作量与风险。
- 对"版本已更新仍存在"的问题，应追踪最近相关 commit/PR：可能是修复方向错误、覆盖入口不全、插件目录/缓存未更新。