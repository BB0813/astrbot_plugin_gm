# 项目记忆

累计反思 60 次

## 仓库背景

仓库 `mjy1113451/astrbot_plugin_gm` 是 AstrBot 群管理类插件，Issue/PR 常涉及命令解析、撤回、群管理权限、按群配置、OneBot 适配器兼容、配置 schema 与 README 同步。

- **"删除功能"类 Issue 不应自动归 medium**：维护者本人纯减法性质的功能裁剪，优先级应考虑"主动减法 + owner 自实施 + 无横切关注点"组合 → low（除非涉及撤回/缓存）。
- **`breaking-change` 应作为独立标签**：删除既有命令语法、修改既有命令参数语义、修改既有命令返回值、删除既有配置项都属 breaking change。
- **`recall_cmd` 是高频改动点**：本仓库撤回类 PR 多次出现（语义变更、批量撤回、缓存兜底、行号解析、接口收敛），未来分析应优先关注 Path 分支完整性、对称性、本地缓存写入、帮助文本同步。
- **撤回类 Issue 改动清单（五处同步→七处同步）**：main.py + README + 帮助 + schema + CHANGELOG；涉及"撤回+禁言"扩展应再加 **STT/转写配置文件** + **误伤率文档说明**（README 风险提示）。
- **撤回类 PR 强制检查清单**：① `/撤回 1 3 5` 多编号与 AstrBot 命令匹配器冲突 ② `after_message_sent` 钩子可用性与循环风险 ③ 缓存并发安全、重启丢失、过期策略 ④ `retcode=1200` 跨适配器识别 ⑤ `batch_max_count` vs `max_message_history` 关系 ⑥ bot 权限校验（QQ 2 分钟限制）⑦ 配置 schema 一致性 ⑧ 旧配置/缓存升级兼容 ⑨ README+帮助+docstring 三处同步。
- **撤回缓存三层链路优先级**：必须显式 `recent_messages`（旧）→ `message_history`（新）→ `get_group_msg_history`（OneBot 兜底）的优先级与失败回退。
- **删减类 issue 检查清单**：调用点清空、帮助/README/docstring 同步、CHANGELOG/公告、剩余路径边界、用户迁移路径；不能套用新增类检查模板。

### 头衔类 Issue 标准分析模板（#125 案例）

- **触发场景**：`/取消头衔 @用户` 提示成功但头衔仍存在。
- **必查项**：① Bot 在该群角色 ② 目标用户身份（是否群主）③ OneBot 实现版本 ④ AstrBot/插件版本与 commit ⑤ 完整执行日志 ⑥ 最近配置变更 ⑦ `_extract_at_qq` 解析 ⑧ `special_title` 传参（`""` vs `" "` vs 空白）⑨ `get_group_member_info` 回读。
- **必给标签**：`bug` + `command` + `group-management` + `title`/`special-title` + `onebot`/`compatibility` + `needs-info`（主分类 0.90+）。

### "提示成功但实际未生效"类 Issue 通用模式

分类必为 `bug`。根因排查：命令解析→权限判断→API 参数→适配器兼容→API 返回值→**状态回读**→用户提示。修复方向：补 `get_group_member_info` 回读 + 明确传参语义 + 适配器差异处理。

### 权限模型重构类 Issue 标准模式（#130 案例）

- **触发场景**：将插件自定义权限模型改为依赖群原生权限（如移除 `plugin_admins` 改为自动检测群管理员/群主）。
- **必查项**：① 待删除的配置项及影响范围 ② 群原生权限获取 API 跨适配器差异（`get_group_member_info`）③ 缓存策略（每次查 vs 缓存失效）④ **权限提升风险审计**（新模型下哪些群主能执行原不该执行的命令）⑤ 配置迁移路径（旧 `config.json` 处置）⑥ API 调用失败兜底（拒绝 vs 放行）。
- **分类**：`enhancement` + `breaking-change`，**优先级 `medium`**（横切重写但有迁移路径，非 `low`）。
- **五处同步清单**：main.py + `_conf_schema.json` + README + 帮助命令 + CHANGELOG（+ 迁移指南）。
- **新增标签建议**：`bot-role`/`sender-role`（bot 在群内角色鉴权）、`permission-model`（权限模型重构专用）、`deprecation`（废弃配置项/命令）。

### 加群申请工作流扩展模式（#129 案例）

- **OneBot 加群申请 API 必查**：`set_group_add_request(flag, sub_type, approve, reason)` 的 `reason` 字段跨适配器支持；`reason` 长度限制矩阵：NapCat ≤10 字符、Lagrange ≤10-20、go-cqhttp ≤30（部分版本不限）。
- **配置 schema 建议字段**：`reject_reason_enabled` / `reject_reason_default` / `reject_reason_per_group` / `reject_reason_templates` / `reject_reason_max_length`（跨适配器截断配置）。
- **分类必为 `enhancement` + `medium`**（涉及代为拒绝加群申请，存在误拒/理由不当风险，不能降 `low`）。
- **与既有 `pending_join_requests` 流程衔接**：复用入口避免新增并行通道；同意侧 reason 透传也需验证。

## 反模式（最关键警示）

- **结构化输出校验失败 ≠ 信息不足**：看到 `expected <SUGGESTED_TITLE>` 等字段校验错误时，应**仅修复字段输出**（如把"无建议"改成实际建议），**不得把所有判断都退化为"无法评估"/`other`/空标签/无建议**。**字段校验失败仅触发输出修复，不得影响分类/可行性/标签/标题等实质性判断**。**Pre-check 规则**：在任何字段出现"无建议/无法评估/空/未检测到重复"前，必须先确认是否源于校验失败——校验失败应**局部修复**而非**整体降级**。
- 标题字段**禁止写"无建议"**；原标题已清晰应标"可保留"或给轻量规范化版。标题为空、"。"等无意义时必须改写。
- 标签在不确定体系时也应给通用候选并注明需映射，**不能留空**；可行性在信息不足时也应有条件判断，不能写"无法评估"。
- **重复检测措辞强制模板**：无历史列表时**写"暂未发现"并列出建议检索关键词**，"未检测到重复"/"无重复"/"可能是 #X 的重复"均被明令禁止。每次重复检测输出末加注"⚠️ 措辞核对：是否使用了禁用的'未检测到重复'/'无重复'/'可能是#X的重复'？"。
- **"quick"策略不能成为零审查的借口**：涉及权限/撤回/缓存等横切关注点的 PR，最低限度必须覆盖安全相关检查和结构性检查（schema 一致性、命令签名、关键风险点）。
- **PR 描述数字与实际 diff 不一致**需主动指出（如声称 +520/-103 实际 +494/-52）。
- **chore/reflection 批量 commit 污染提交历史**：多个相同信息的 chore commit 应在审查中标记为提交历史质量问题。增量审查时优先识别哪些是"有价值的代码变更"、哪些是"chore 噪音"。
- **`ast.parse` ≠ 真实加载**：PR 用 `ast.parse` 验证是错误认知，应替换为 `python -m py_compile main.py` 至少保证编译通过，最好有最小 AstrBot 启动验证。
- **记忆引用必须可溯源**：引用具体编号（如"§4.13"）前必须确认该编号存在；模糊记忆时用"参 §X 章节关于 Y 的讨论"而非编造编号/原文。
- **审查评分校准**：撤回/缓存核心命令回退路径 bug，无论代码量大小，影响面涉及「绝大多数未启用某配置的群组」时，评分上限不超过 5/10，决策应为 request_changes 或 comments。

## Issue 分析经验

### 1. 分类、优先级、标签与标题

- 明确运行时报错、命令参数类型错误、用户反馈"更新后仍存在"时，主分类应为 `bug`；辅助 `command`、`parser`、`compatibility`、`needs-info`。
- 权限/配置粒度调整应归为 `enhancement`（不是 `other`）；辅助 `configuration`、`permission`、`group-management`、`needs-discussion`，移除旧机制需评估 `breaking-change`。
- `medium` 适用于核心命令局部不可用、权限配置影响多群但非阻断、群管理命令提示成功但实际未生效。插件启动失败、越权、误踢/误撤大量消息应考虑 `high`。
- 标题中 `[bug][medium]`、`[enhancement][medium]` 是信号但需结合正文和代码。涉及"禁言/禁我申请解禁"标题要覆盖两种状态；涉及批量撤回要覆盖普通与按用户两种形式；涉及删除命令用法标题要明确"删除"动作与具体被删路径。
- **`needs-info` vs `needs-discussion` 区别**：前者用于"缺关键事实才能评估"，后者用于"决策待定/方向冲突"。owner-driven issue 缺的是决策而非信息，应降 `needs-info` ≤0.2，`needs-discussion` 保持高权重。不要把"系统能力待确认"等同于 `needs-info` 高权重——此时 `needs-info` 0.35-0.50，`needs-discussion` 0.80+。
- **"good first issue"慎用**：仅适合"明确小重构/纯文档/小功能"；增强类涉及设计决策/兼容性时置信度 ≤0.15。
- **`help wanted` 对 owner-driven self-implementation 几乎不适用**：维护者本人提交 + 改法明确 + 工作量小时置信度 ≤0.1。
- **行号引用必须可溯源**：精确行号若无"已读取 main.py 验证"说明，会让读者怀疑是猜测；要么读取验证，要么用"约 L2000-2060"等模糊表述。
- **同期并行 Issue 方向冲突要纳入优先级判定**：扫描同期相关 Issue 是否方向冲突，冲突则升级 `needs-discussion` 高权重。
- **语音/STT/语音违规检测类 Issue 标准标签**：`enhancement` + `stt`/`voice`（核心模块标签，仓库若未建立应主动建议）+ `moderation` + `recall` + `profanity` + `configuration` + `permission` + `onebot`/`compatibility` + `privacy` + `needs-discussion` 高权重 + `needs-info` ≤0.45。

### 2. AstrBot 命令参数与撤回逻辑

- 对 `@filter.command(...)` 命令，必须区分错误发生在启动/插件加载/命令注册阶段，还是用户调用后的业务函数阶段。AstrBot 根据函数注解提前转换参数，函数体内 `try/except int(count)` 无法兜底；复杂语法入口优先用字符串/原始事件解析。
- `/撤回 N` 应理解为撤回"当前命令之前的 N 条消息"，不能优先撤回命令自身；`count=1` 是最小必测。历史或缓存结果都必须排除当前 `event.message_id`。
- **本地缓存撤回模式骨架**：① 按群隔离 ② 最小化存储（仅 `message_id + user_id`）③ 显式上限（deque maxlen，按用户撤回场景 ≥ 8×N 或 per-user deque）④ 写入入口对称（用户消息 `on_group_message`、bot 消息 `after_message_sent` 独立路径，置于业务早退之前）⑤ 回退标识"（来自本地缓存）"⑥ 文档明示重启不可恢复 ⑦ 写入失败 try/except + debug 日志 ⑧ 提示语区分"接口不可用/临时错误/历史为空"。
- **"删减既有命令用法"类 Issue 分析结构**：① 删除目标（精确到 Path 分支/行号）② 保留目标 ③ 边界行为（删除后旧语法如何处理）④ 依赖解耦（被删功能下游是否同步调整）⑤ 用户迁移 ⑥ 替代方案。

### 非文本消息类型违规检测 / STT/语音类 Issue 标准分析模板

- **必查项**：① AstrBot 是否暴露 STT provider 或语音 segment 转写字段 ② OneBot 适配器语音文件获取差异 ③ STT 引擎选型成本 ④ 撤回时限硬约束（QQ 2 分钟）与 STT 耗时的撞限 ⑤ 隐私合规 ⑥ 误触发风险（语音转写误伤 5-15%、OCR 误伤 10-20%）⑦ 同步/异步模式（**异步对撤回场景基本不可用，必须推荐同步**）⑧ 降级策略 ⑨ 跨事件边界校验 ⑩ 复用既有违规词库是否构成隐性 breaking change。
- **可行性分支判定**：**分支A**（消息段已带转写/框架暴露 STT API）= ~100-200 行；**分支B**（需插件自行调 STT API）= ~200-300 行 + 5-7 天。可行性章节必须明确"分支A 则……分支B 则……"。
- **撤回时限撞限**：建议"超时则跳过本条"或"撤回失败时降级为仅记录违规次数"。
- **降级策略是横切关注点**：STT 不可用时必须明确降级路径（禁用整个功能/跳过语音/记录错误）。
- **多模态违规检测标准模式**：消息类型识别 → 转写/标准化层（STT/OCR/文件名校验）→ 关键词匹配 → 标准处置。新增输入源只需补"转写/标准化"环节。

### 3. 权限、群管理 API 与按群配置

- "按群独立配置"是权限模型调整，需区分功能权限、配置权限、插件管理权限；遵循最小权限原则。
- 关键点：`plugin_admins`、`group_overrides`、`get_group_setting`、`title_admins`、`group_admin_admins`、`kick_admins`，及对应 `has_*_admin_rights` helper。
- 群管理 API "返回成功但实际未生效"按链路排查：命令解析→权限判断→API 参数→适配器兼容→API 返回值→状态回读→用户提示。OneBot/NapCat/Lagrange/go-cqhttp 对 `special_title=""`、`duration=-1/0/不传` 可能不同。
- 头衔清空要严格区分 `special_title=""`、`" "`、空白字符、`None`；`strip()` 会把空格头衔误判为已清空。
- **本仓库"禁言/禁我"语义至少 3 层**：① 群管 API 禁言 ② 插件内部"禁我"自怼 ③ 申请解禁工作流中的"待审批禁言状态"。分析禁言相关 issue 必须先确认指哪一层。

### 4. PR/代码审查经验

- **增量审查的噪音识别与对接面扫描**：先识别哪些 commit 是"有价值的代码变更"、哪些是"chore 噪音"，对重复 commit 合并视为 1 个或直接跳过；**不能仅看新增 commit 而忽略被改动的接口**——必须主动补做：① 读取改动前代码确认既有接口契约 ② 走端到端流程 ③ 横切关注点"未变更则保留、变更则重审"清单化检查 ④ 抽样验证对称路径（如 `recall_cmd` 与 `recall_user_cmd` 的缓存回退对称性）。
- **`async def` 中一旦出现 `yield` 就变为 async generator**，不能 `return <value>`，也不能按普通 coroutine `await func()` 获取返回值。
- 命令 handler 与普通 helper 的响应方式要区分：顶层 AstrBot 命令 handler 可使用 `yield event.plain_result(...)`；普通 helper 优先统一调用 `_send`。
- 对集中式权限 helper 要抽样所有调用语义：成功返回 `True`，失败发送提示并返回 `False`。
- **早退语句吞噬共享逻辑**是高频陷阱：基础设施写入（缓存、统计、日志）必须置于业务早退**之前**，否则功能开关关闭时连带基础设施也不工作。
- **注释即承诺原则**：注释描述的行为与代码实际不符，无论大小都应标记。
- **`defaultdict(factory)` 的微妙陷阱**：`.get()` 安全，但 `if k in d` / `dict(d)` / `copy.copy(d)` / `json.dumps` 会无差别创建空条目。**推荐 `{}` + 显式 `setdefault(key, factory())`**。
- **falsy 判空 vs 严格判空**：对外暴露的 helper 优先用 `x is None` / `x == ""` 严格判空；内部业务 helper 若确认业务值不会为 0，可保留 falsy 判空但需在 docstring 注明约定。
- approve 可以，但若缺少真实 AstrBot 加载和命令验证，尤其涉及框架消息发送方式变化或撤回/缓存路径变化，评分不宜给满分。

### 5. 私聊申请与审批工作流

- **私聊事件无 `group_id` 是硬约束**：私聊触发群管理动作时必须要求用户提供群号，或复用/维护禁言记录。
- **审批必须用申请 ID / 引用回复 / 专用命令**（如 `同意 #123`），**不能只靠"同意/驳回"关键词**。
- 申请说明可能含隐私，只转发到配置的可信管理员或管理群。
- 建议预列配置项：`appeal_enabled`、`appeal_admin_qqs`、`appeal_admin_group`、`appeal_expire_minutes`、`appeal_max_concurrent`、`appeal_privacy_redact`、`appeal_cover_mute`、`appeal_cover_block_self`。

### 6. 合入外部仓库/外部代码类 Issue

分类 `enhancement` + `merge-request`/`external-repo`。评估维度：外部代码质量、依赖兼容性、许可证兼容性、维护责任、重构 vs 合并、配置 schema 扩展、bot 权限要求。标签建议加 `license-check`。
