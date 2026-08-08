# 项目概述：mjy1113451/astrbot_plugin_gm

> 累计反思 50 次

## 1. 项目简介

`astrbot_plugin_gm` 是 AstrBot 的 QQ 群管理插件，提供插件管理员维护、禁言/解禁、踢人、撤回消息、群昵称、头衔、精华消息、官方群管理员设置等能力。逻辑集中在 `main.py`，依赖 AstrBot 插件体系与 aiocqhttp / OneBot API。

主要命令：`/设管`、`/取管`、`/禁言`、`/解禁`、`/禁我`、`/踢`、`/头衔`、`/取消头衔`、`/设管理`、`/取消管理`、`/设精`、`/设群昵称`、`/改昵称`、`/撤回`、`/撤回用户`。

## 2. 技术栈与结构

- **语言**：Python 3.10+；**框架**：AstrBot 插件体系；**接口**：aiocqhttp / OneBot action；**配置**：`_conf_schema.json` + 运行时读取；**许可证**：MIT。
- 主目录：`main.py`（命令、权限、配置、OneBot 兼容）、`metadata.yaml`、`_conf_schema.json`、`README.md`、`docs/`。

## 3. 权限与配置模型

1. **插件管理员**：`plugin_admins` 或 `/设管` 动态维护；群主天然具备。
2. **QQ 官方权限**：禁言、踢人、撤回、设精、设/取消管理/头衔仍依赖机器人群内官方权限。
3. **专项权限/按群覆盖**：`title_admins`、`group_admin_admins`、`kick_admins`、`group_admins`、`group_overrides`、`get_group_setting` 及 `has_*_admin_rights` 机制；权限变更应优先检查这些入口。
4. **全局默认 + 群级覆盖**：明确缺省回退、空列表/空对象/`0` 的语义。`0` 可能是合法配置（如关闭阈值），不能误当缺失回退。
5. **跨私聊审批**：若新增私信申请解禁等远程审批功能，必须明确插件管理员是否可对所有群代 bot 解禁、审批者所属与可审计状态。

## 4. 近期反思沉淀

### 4.1 AstrBot async / yield / return 风险（PR #116）

- `async def` 内出现 `yield` 即变为 async generator，不可 `return True/False`，不能被 `await func()` 当作 coroutine。
- 权限 helper（被 `await` 并返回业务值）不得含 `yield`；发送提示统一走 `_send` / `_build_text`。
- 顶层 handler 可 `yield event.plain_result(...)`，但不要与 `return` 混用。
- 验证至少 `python -m py_compile main.py`，并验证插件加载、无权限提示、有权限继续。
- 审查固定项：搜索 `async def`、`yield`、`return <value>`，确认所有被 `await` 的 helper 非 async generator（与 Issue #121 风险叠加）。

### 4.2 `/撤回` count 参数解析（Issue #106）

- 命令签名 `count: int = 0/1` 时 AstrBot 可能按注解提前转换，函数体内 `try/except int(count)` 捕获不到。
- 复杂命令入口用 `str` 或原始参数接收，统一在函数内解析、校验、给友好提示。
- 同类入口要一起排查：`recall_cmd`、`recall_user_cmd` 及所有 `: int =`、`count: int` 参数。
- 测试：`/撤回`、`/撤回 3`、`/撤回 abc`、引用撤回、带 @+ 数量、空串、负数、过大、中文数字。

### 4.3 `/撤回 N` 语义与本地缓存回退（Issue #109、#110、#117、#118、PR #123）

- `/撤回 1` 期望撤回"当前指令上方一条消息"而非指令自身：先取群历史，过滤当前命令 `message_id`，只撤回之前的 N 条可撤回消息。
- 历史接口不可用时不可回退为"撤回指令自身"误报成功；引用撤回优先级保持。
- **本地缓存回退模式（新增 §4.6 推荐骨架）**：
  1. 缓存设计：按群隔离（`{str(group_id): deque[dict]}`）、最小化存储（仅 `message_id` + `user_id`）、`deque(maxlen)` 显式上限、写入入口对称（用户消息走 `on_group_message`，bot 消息走 `after_message_sent`）、回退标识（"（来自本地缓存）"）、README 明示重启不可恢复。
  2. 工厂函数选择：`{}` + `setdefault(key, factory())` 优于 `defaultdict(factory)`，避免 `in` 检查、`copy`、`json.dumps` 等意外触发工厂。
  3. **bot 消息写入必须独立于业务早退链**：置于 `if not enabled: return` / `if not in list: return` 之前，否则对未启用自动撤回的群，bot 自发言永不入缓存，`/撤回 N` 回退路径失效（PR #123 阻断性 bug 根因）。
  4. 容量与功能耦合：`maxlen ≥ 4 × N`（N 上限）；同时考虑撤回时限（普通成员 2 分钟）与缓存期密度。
  5. 必须排除命令自身 `message_id`；读取按时间倒序取 N 条最近的；缓存首次写入失败不应阻塞 `on_group_message` 主流程（try/except + debug 日志）。
  6. 全局群组 key 无上限是潜在风险（low → medium），可加 LRU 淘汰二级保护。
- OneBot `get_group_msg_history` 在部分实现不支持；空返回语义模糊（不支持/参数不兼容/权限/历史不足/错误被吞），提示语应写"可能不支持或未返回群消息历史"，不可一概写"不支持"。
- @ 解析不按空格拆昵称（昵称可含空格），优先 segment、`user_id` 或 `_extract_at_qq(raw)`。
- README/帮助应说明：`/撤回 N`、`/撤回 @用户 N` 依赖 `get_group_msg_history`；不支持时用引用撤回或切换支持群历史的实现。
- PR 描述中的"提示附带『来自本地缓存』"必须到 diff 中定位确认，避免文档与实现脱钩。

### 4.4 `/撤回 @用户 N` 与 `/撤回用户`（Issue #110、#117）

- `/撤回 @用户 N` 进入普通 `/撤回` 兜底属命令路由/解析 bug，应复用 `recall_user_cmd` 或抽 helper，不复制两套撤回逻辑。
- `/撤回 @用户 N` 和 `/撤回用户 @用户 N` 依赖群历史按 `user_id` 筛选；引用撤回已有 `message_id` 不依赖历史。
- 增量审查风险：只审 diff 会漏掉 `recall_cmd`/`recall_user_cmd` 两端缓存回退的对称性——必须抽样确认三条分支（按数量、按用户、引用）行为一致。

### 4.5 `/取消头衔` 提示成功但实际未清空（Issue #111、#119、PR #123）

- 链路：`/取消头衔` → `unset_group_title_cmd` → `_clear_group_title` → `set_group_special_title`。
- 严格区分 `""`、`" "`、`\t`、`None`、字段缺失；`strip()` 会把单空格误判为空（已知反模式）。
- `special_title=""` vs `" "` vs `None` vs 不传、`duration=-1/0/不传` 在 NapCat / Lagrange / go-cqhttp 语义可能不同；API 返回 ok 不代表实际生效。
- 必要时用 `get_group_member_info` 回读，但注意缓存、字段差异、刷新延迟。
- 严格判空 `title is None or title == ""`（不要 `not title`）是 PR #123 修复方向。
- 排查：@ 解析、`user_id`/`group_id`、目标是否在群、机器人权限、目标为群主/管理员、平台限制或客户端缓存。

### 4.6 本地缓存回退模式与严格判空（PR #123 沉淀，新增）

- **本地缓存回退骨架**：主路径失败 → 本地缓存静默回退 → 双重失败才报错 → 成功时附加来源标识；适用于 OneBot 适配器碎片化场景。
- **严格判空 vs falsy 判空**：对外暴露的通用 helper 优先 `x is None` / `x == ""`，避免误丢合法值（0、空集合等）；业务内部 shortcut 可保留 falsy 但必须在 docstring 注明"`0` 视为缺失"等约定。
- `_record_recent_message` 这种"既像通用 helper 又像业务实现"的灰色地带，审查应主动追问判空风格。
- 撤回类本地缓存必须满足：① 全局 key 数量上限 + LRU；② 写入失败不影响主流程（try/except + debug）；③ 读取排除命令自身；④ README/帮助/schema 同步；⑤ 缓存仅覆盖进程启动后；⑥ 隐私最小化（不缓存内容）。
- `ast.parse` ≠ 真实加载：PR 验证应至少 `python -m py_compile main.py`，最好有最小 AstrBot 启动验证（装饰器注册、命令注册等不会在 ast 阶段触发）。

### 4.7 禁言踢出阈值按群配置/展示（Issue #107）

- 配置 UI/Schema/展示未体现"全局默认 + 群级覆盖"，归 `bug`。
- 不删除全局 `mute_kick_threshold`；它应说明为"全局默认禁言踢出阈值"，可被群级覆盖。
- 展示建议"有效值 + 来源"，如"禁言踢出阈值：3，来源：当前群覆盖；全局默认：5"。
- 缺失 key 回退全局；显式配置 `0` 表示关闭/覆盖，不能当未配置。

### 4.8 专项权限按群配置（Issue #105）

- 属 `enhancement`，按动作授权、符合最小权限原则。
- 改变 `group_admins` 语义需考虑迁移/废弃期/兼容读取。
- 敏感操作（踢人、设/取消管理、头衔）必须做越权和误授权测试。

### 4.9 私信申请解禁与管理员审批流程（Issue #120、#121）

- 归 `enhancement`/`feature`，优先级 `medium`：涉及自动解禁敏感动作，存在越权/误解禁/并发风险。
- 标签：`enhancement`、`group-management`、`moderation`、`mute`、`private-message`、`approval-flow`、`permission`、`configuration`、`needs-discussion`。
- 最小实现：私聊 `申请解禁 群号 说明` → 生成申请 ID → 转发固定管理员 QQ → 编号同意/驳回 → 复用 `_unmute_member` → 私信通知。
- 完整实现：管理员 QQ + 管理群、引用/编号/专用命令审批、状态持久化、重启恢复、过期、重复申请去重、多管理员并发幂等、权限校验、文档同步。
- 私聊无 `group_id`：必须用户输入群号或复用最近禁言/禁我记录；校验用户是否在目标群、是否真被禁言。
- 审批不能仅靠"同意/驳回"关键词（管理群易误触发）。应优先申请编号、引用申请消息或 `/解禁审批 同意 <id>`，并校验审批者 `sender.user_id`（非 `event.user_id`）。
- 自动解禁是敏感动作：只有配置的插件管理员或授权群管理员可审批；记录审批日志；失败反馈原因。
- 工作量：最小可用版中等偏低；完整版中等到中高。
- PR #116 风险叠加：新增 helper 必须纯 `async def`，避免 `await` 业务 helper 中混 `yield`。

### 4.10 合入外部仓库与批量撤回增强（Issue #122）

- 标题为"。"、正文仅 URL+命令形式时，必须从正文重建需求，不能依赖标题分类。
- 分类 `enhancement`（辅以 `merge-request` / `external-repo`），优先级 `medium`。
- 关注：外部代码质量评估、OneBot 适配兼容、与本仓库命令注册/权限模型集成点、schema 是否需扩展、bot 权限要求、缓存策略、撤回时间窗、限流保护、bot 自身消息处理、部分失败处理。
- 外部代码合入关注：代码归属、许可证（LICENSE 兼容性）、依赖与框架版本、代码风格统一、维护责任、submodule/copy/vendor 选择、后续同步策略。
- 复用了 §4.2–§4.4 已有沉淀：参数解析、自身 `message_id` 排除、OneBot 适配差异、@ 解析等。

### 4.11 PR #123 多轮增量审查教训

- **增量审查的结构性盲区**：只看 diff 易遗漏 `__init__` 初始化兼容、`after_message_sent` 钩子注册与签名兼容、读取端对新数据结构适配。必须做"对接面快速扫描"（被改动的接口上下游），无法验证端到端时应要求作者补最小集成测试。
- **审查评分校准**：撤回/缓存等核心命令回退路径 bug，当影响面涉及"绝大多数未启用某配置的群组"时，评分上限不超过 5/10，决策 `request_changes`。
- **结构化输出校验失败的反模式**：当 `expected <SUGGESTED_TITLE>` 等校验错误出现时，应**修复字段输出格式并保留实质判断**（分类、可行性、标签、关键问题列表），不得整体退化为"无法评估"。审查模板固化"字段校验失败时的最小输出保底"：分类/优先级/可行性/标签/关键问题列表五项必须保留。
- **"quick" 策略不等于零审查**：对涉及权限/撤回/缓存的 PR，最低限度必须覆盖安全相关检查、schema 一致性、命令签名、关键风险点。
- **commit 信息去重**：多个相同 `chore(sakura): add reflection for ...` commit 应标记为提交历史质量问题，建议合并或跳过；增量审查应优先识别"有价值的代码 commit"与"chore 噪音"。
- **PR 描述数字与实际 diff 不一致**：审查应主动核对（如 +520/-103 vs +494/-52），要求作者澄清。
- **重写型 PR 的额外审视**：即使评分无变更也应作为 red flag 标记，额外审查 API 兼容性、回退路径、新旧接口映射（`recent_messages` → `message_history` 升级时旧结构残留风险）。
- **`ast.parse` ≠ 真实加载**：PR 用 `ast.parse` 验证是常见错误认知，应替换为 `python -m py_compile main.py`，最好有最小 AstrBot 启动验证。
- **撤回类 PR 强制检查清单**（9 项）：时间窗（2 分钟）、限流、部分失败处理、自身消息排除、bot 消息处理、撤回目标过滤、缓存数据结构、OneBot 适配差异、配置 schema 一致性。
- **多编号参数与命令匹配器冲突**：`/撤回 1 3 5` 需确认 AstrBot 把整串当作 `arg_str` 还是按空格拆成多个位置参数。

### 4.12 `/取消头衔` 头衔清除失败回读仍存在（Issue #125）

- 分类 `bug`，优先级 `medium`：不是加载级问题，但"提示成功但实际未生效"会让用户误以为已清空，头衔涉及身份标识不可轻视。
- 排查链路（按概率）：① bot 权限不足（非群管理/无设头衔权限）→ ② 目标用户是群主（协议限制）→ ③ OneBot 适配器对 `set_group_special_title(special_title="")` 语义差异（NapCat/Lagrange/go-cqhttp）→ ④ API 返回成功但状态回读缓存未刷新。
- 严格区分 `special_title=""`、`" "`、`\t`、`None`、字段缺失（§4.5 已沉淀）；`strip()` 是已知反模式。
- `@昵称` 解析走 segment / `user_id` / `_extract_at_qq`，不要按空格 split（昵称可含空格，如 `@晚风抱抱我`）。
- 必要时 `get_group_member_info` 回读，但注意缓存、字段差异、刷新延迟。
- 标签建议：`bug` + `command` + `group-management` + `title`/`special-title` + `onebot` + `needs-info`。
- `needs-info` 收集清单：bot 群角色、目标用户角色（是否群主）、OneBot 实现与版本、AstrBot 版本、插件 commit、完整命令与日志、近期配置变更。
- 仓库内 `set_group_special_title` 调用点集中于 `main.py` 头衔 handler；审查该类 Issue 时主动检查 `_extract_at_qq`、`special_title` 传参、是否有回读。

### 4.13 Issue #124 三轮反思共性沉淀（撤回默认行为与按用户指定编号）

- 分类 `enhancement`，优先级 `medium`：UX 改进而非核心功能缺失；语义歧义处理不当会导致误撤回，故不能降为 `low`。
- **路由语义歧义分析框架**（高频陷阱，单参数多语义）：① 列出数字 N 所有候选语义（数量/编号/时长/次数）② 检查现有代码实际语义 ③ 检查文档/帮助承诺语义 ④ 显式标记"语义决策点"为 `needs-discussion`。
- **序号基准必须由维护者拍板**：相对序号（用户在该群最近发言的相对位置）还是绝对序号（`/消息列表` 列表中 1-based 编号）必须明确，不能由实现方自行决定。
- **行为变更 vs 实现风险要严格区分**：用户主动请求的语义修改（如 `/撤回 @用户 5` 从 5 条→1 条）是需求不是回归；风险聚焦实现层副作用（缓存一致性、对称性破坏、文档缺失）。
- **"默认 1 条"类改动的隐藏风险**：误输入空参数时不再看到用法提示→误触发撤回；与引用撤回优先级协调；与本地缓存兜底路径对接；长消息前缀解析失败误触发；是否需二次确认。
- **可行性强检查项**：`batch_max_count` 与新单数字路由交互（路由后 N 是否仍受约束、N> 时提示）；`/撤回自身 N` 与新默认行为冲突；`recall_user_cmd` 与 `recall_cmd` 对称性；历史快照编号语义（1-based/0-based、该用户最近一条=编号 1 需单独语义）；`defaultdict` 副作用（§4.6）；bot 消息本地缓存写入路径不得被破坏（§4.3 第 3 点）。
- **工作量估算常偏低**：看似"加个默认 1 条"实际涉及入口分流 + 命令提示 + README + 帮助命令 + `/消息列表` 帮助 + 行为兼容性说明 + 测试；估算需预留 40-80 行而非 20-40。
- **标签建议组合**：`enhancement` + `command` + `parser` + `recall` + `message-history` + `group-management` + `needs-discussion`（关键）；`good first issue`/`help wanted` 谨慎使用。
- **`good first issue` / `help wanted` 使用边界**：已规划清楚、有 owner、有明确改法→`enhancement`+模块标签即可；改法不明欢迎外部贡献→`help wanted`+`needs-design`；简单到任何人可上手、纯重构/文档→`good first issue`（增强类通常不适合）。
- 关联追溯：本次增强直接建立在 PR #123 本地缓存骨架上，必须主动声明依赖、避免重复实现。

### 4.14 PR #123 第五轮增量审查教训（追加）

- **增量覆盖度仍严重不足**：本次仅看 6 个新提交中"有价值的代码变更"（`38787272`、`4f3f94ee`）而非整 PR，但 38787272 前 main.py 状态、`recent_messages` → `message_history` 升级前的回退路径均未审查——增量审查天然缺少完整上下文，需主动索取被改动的接口上下游状态或假设评审。
- **提交模式异常**：6 个新提交中 4 个 commit 信息完全相同（`chore(sakura): add reflection for PR#123`），属于"批量反思 commit"噪音。增量审查应识别"有价值代码 commit"与"chore 噪音"，建议合并或跳过。
- **PR 描述数字与实际 diff 不一致**：描述自述 +520/-103，提交哈希显示 +494/-52——审查应主动核对，要求作者澄清。
- **重写型 PR 的额外审视**：撤回/缓存重做 PR 即使评分无变更也应作为 red flag 标记，额外审查 API 兼容性、回退路径、新旧接口映射（`recent_messages` → `message_history` 时旧结构残留风险）。
- **`ast.parse` ≠ 真实加载**：PR 用 `ast.parse` 验证是常见错误认知，应替换为 `python -m py_compile main.py`，最好附最小 AstrBot 启动验证（装饰器注册、命令注册等不会在 ast 阶段触发）。
- **审查评分校准**：撤回/缓存等核心命令回退路径 bug，当影响面涉及"绝大多数未启用某配置的群组"时，评分上限不超过 5/10，决策 `request_changes`。

### 4.15 Issue #126 功能裁剪/删除类沉淀（owner-driven 减法，多轮合并）

- **场景特征**：维护者本人发起（mjy1113451），要求删除 `/撤回 编号...` 与 `/撤回 @用户 编号...` 两种按编号撤回用法；属接口收窄而非 bug 或新增；属 `breaking-change`（已部署用户脚本/教程会失效）。
- **分类与优先级**：分类锁定 `enhancement`（功能减法，接口收敛）；优先级 `medium`（breaking change 但维护者自提 + 改动局部 + 影响存量少数用户）；不可降 `low`（对外契约删减），也不可升 `high`（无横切关注点）。
- **标签必填组合**：`enhancement` + `breaking-change` + `recall` + `command` + `parser` + `documentation` + `needs-discussion`；与缓存/历史相关的补 `cache`/`message-history`；`help wanted` 置信度 ≤0.1（owner 自提且改法明确，不需要外部抢着接）。
- **必查 9 项检查清单（删除类反向清单）**：① 精确删除路径（行号 ± 验证已读 main.py）② 保留路径边界（剩余 Path 1/3/5 不受影响）③ 调用点清空（测试用例同步删）④ README 帮助文案清理（移除"按编号"措辞）⑤ `/撤回` 自身 `yield event.plain_result(...)` 帮助文本同步 ⑥ 配置 schema 语义缩窄（`batch_max_count` 从"约束两种分支"→"仅约束按数量分支"）⑦ bot 回复模板/错误提示措辞清理 ⑧ CHANGELOG/release notes 标注破坏性 ⑨ 替代方案提示（引导引用撤回、`/撤回用户`）。
- **AstrBot 消歧层选择**：撤回/计数类命令的参数语义修改必须明确是在 `@filter.command` 装饰器签名层（改类型注解/默认值，僵硬但简单）还是 handler 内部（先收 `str` 再分流，灵活但要处理 `try/except int()` 已被 AstrBot 提前按注解转换的情况——参 §4.2）。
- **`/撤回 N` 与 `/撤回自身 N` / `after_message_sent` 钩子的循环风险**：删除按编号语义后必须确认未影响 bot 自身消息记录路径（PR #123 引入的 `after_message_sent`）。
- **OneBot 兼容性回退路径**：若 `/撤回 N` 在某些 OneBot 客户端下不可用，用户原本可用 `/撤回 1 3 5`（纯本地缓存）作精确手段，删除后这条精确路径消失，回退到 `/撤回 N`（数量）也失效，会形成双重退化——删除前需评估。
- **与并行 Issue 的方向冲突**：Issue #124（要求按编号撤回增强）与本 Issue（删除按编号）方向相反——单独实施任何一方都会制造新不兼容，必须显式标 `needs-discussion` 并建议先解决 #124 决议再实施；冲突项应升级或强化 `needs-discussion` 权重。
- **行号定位必须标注证据来源**：精确行号（L2024-2057 等）若无"已读取 main.py 验证"说明，会让读者怀疑是猜测——要么读取验证，要么用"约 L2000-2060"模糊表述。
- **工作量估算需拆分**："代码 X 天 + 文档 Y 天 + 测试 Z 天 + 验证 W 天"区间估，预留 40-80 行而非 20-40（README + 帮助 + CHANGELOG + schema + 测试 + 验证六面同步）。
- **关联追溯（区别于重复）**：与 Issue #124 方向相反但同主题，应标 `related` 而非"重复"；与 PR #123 缓存骨架强耦合，应标 `related`。

## 5. Issue 分析与标签经验

- 标题为"。"、"，"或信息极少时，必须基于正文错误文本、复现命令和代码线索检索，不能依赖标题分类。
- **结构化输出校验失败 ≠ 信息不足**：应优先修复字段输出，不得把所有判断退化为"无法评估"——这是仓库反复出现的反模式（PR #123 第六轮审查即因此完全失败）。pre-check：任何字段出现"无建议/无法评估/空"前，确认是否源于校验失败而非真正判断缺失。
- 不能因校验失败把明确的 `bug` / `enhancement` 降级为 `other`、标签留空、标题"无建议"、可行性"无法评估"。
- 标签建议覆盖主类型、模块和风险；至少保留主标签与核心模块；复杂功能补 `permission`、`configuration`、`needs-discussion`、`needs-info`。仓库高频模块标签：`recall`、`message-history`、`command`、`parser`、`onebot`、`group-management`。
- **重复检测措辞模板化**：无历史列表时**必须**写"暂未发现（建议检索关键词：...）"，不得写"未检测到重复"或"无重复"或"可能是 #X 的重复"（无依据时）。关键词：撤回（`/撤回`、`/撤回用户`、`@用户`、`get_group_msg_history`、`message_id`、`delete_msg`、`batch recall`、`批量撤回`、`默认 1 条`、`按编号撤回`）；头衔（`取消头衔`、`special_title`、`空格头衔`、`set_group_special_title`）；解禁审批（`申请解禁`、`禁言申诉`、`私信`、`审批`、`禁我`、`appeal`、`unmute`）。
- **重复 vs 关联 判定**：方向相反但同主题（如 Issue #124 要求按编号增强 vs #126 要求删除按编号）应严格归为 `related` 而非重复，必须显式列出；纯方向相同、用户故事链与修复点重合才归为重复。
- **撤回命令族五处同步清单**（高频踩坑，固化输出模板）：`main.py` + `README.md` + `/撤回`/`/消息列表` 帮助文本 + `_conf_schema.json` + CHANGELOG（若存在），每条撤回类改动默认占一席 CHANGELOG 同步而非可选。
- **删除既有命令用法类 Issue 强制结构**（维护者自提减法场景）：① 精确删除目标（Path 分支/行号）② 保留目标边界 ③ 删除后旧语法处理（报错/回退）④ 依赖解耦（被删功能下游如 `/消息列表` ↔ `/撤回 编号` 是否需调整）⑤ 用户迁移成本与告知方式 ⑥ CHANGELOG breaking-change 标注。
- **"功能裁剪"类 Issue 优先级判定**：维护者自提 + 纯删减 + 改动局部化 → `low`~`medium`；若涉及对外契约删减且与并行 Issue 方向冲突 → `medium` 且强化 `needs-discussion`。
- **路由语义歧义类 Issue**（如 `/撤回 @用户 N` 的单数字语义）：必须显式列出候选语义并请求维护者确认，标 `needs-discussion`。
- 信息不足时可标 `needs-info`，要求补充 AstrBot 版本、OneBot 实现与版本、插件 commit、完整命令、日志和权限；头衔类 bug 还需 bot 群角色、目标用户角色、近期配置变更。
- **"默认行为"类改动**：UX 增强常被低估工作量，预留 40-80 行而非 20-40。

## 6. 开发约定与注意事项

- 逻辑集中在 `main.py`，修改时全局搜索相似命令模式，避免复制粘贴式遗漏。
- 管理员 QQ 号按字符串处理，避免数字精度或格式问题；群号统一 `str()` 归一化（缓存键、日志键、配置键一致）。
- QQ 操作依赖平台 API 和机器人群权限，必须处理接口失败、权限不足、消息超时和异常返回。
- 权限类改动必须覆盖：全局配置、群级覆盖、命令入口、权限判断函数、文档说明和回归测试。
- AstrBot API/命令解析兼容问题，应区分插件启动、命令注册、命令调用、特定输入触发四个阶段。
- 对群管理"成功提示"保持保守：设/取消头衔、设/取消管理、禁言、踢人、撤回、改群昵称等都应检查 API 返回与状态，失败时给明确提示；"API 返回 ok ≠ 实际生效"是已知反模式，必要时回读。
- 对依赖 OneBot 能力的命令，应在 README/帮助中标注依赖与替代方案，避免用户把平台能力限制误认为插件崩溃。
- 新增跨私聊/群聊工作流时，必须先设计状态机、申请 ID、权限边界、持久化/过期、并发幂等、隐私和发送失败处理。
- 引入外部代码前评估：许可证兼容、依赖与框架版本、代码风格、维护责任、配置 schema 兼容性、是否应抽取通用逻辑而非直接复制。
- 撤回相关改动必须做**对称性检查**：`recall_cmd` 与 `recall_user_cmd` 在入口分流、缓存读写、用法提示上必须对称；`/撤回自身 N` 与新默认行为不得冲突；`message_history` 写入路径不得被业务早退链吞噬。
- 撤回类 PR 强制检查清单（9 项）：时间窗、限流、部分失败处理、自身消息排除、bot 消息处理、撤回目标过滤、缓存数据结构、OneBot 适配差异、配置 schema 一致性。
- **撤回类删除 PR 强制检查清单（9 项反向，参 §4.15）**：精确删除路径 + 保留路径边界 + 调用点/测试用例清空 + README 帮助文案清理 + `/撤回` 自身 yield 帮助文本同步 + 配置 schema 语义缩窄 + bot 回复模板措辞清理 + CHANGELOG breaking-change 标注 + 替代方案提示。
- 验证清单：`python -m py_compile main.py` ≥ `ast.parse`；本地缓存回退类改动应附最小单元测试；README/帮助/schema/CHANGELOG 必须在同一 PR 同步；提交信息避免批量重复 `chore` commit（多个相同 `chore(sakura): add reflection for ...` 应合并或跳过，属提交历史质量问题——参 §4.11、§4.14）；行号引用必须标注"已读取 main.py 验证"或用"约 Lxxxx"模糊表述。
- **撤回命令族五处同步清单**：`main.py` + `README.md` + `/撤回`/`/消息列表` 帮助文本 + `_conf_schema.json` + CHANGELOG（若存在），每条撤回类改动默认占一席 CHANGELOG 同步而非可选。
- **AstrBot 消歧层选择**：撤回/计数类命令的参数语义修改必须明确是在 `@filter.command` 装饰器签名层（改类型注解/默认值）还是 handler 内部（先收 `str` 再分流）做消歧——后者要处理 `try/except int()` 已被 AstrBot 提前按注解转换的情况（参 §4.2、§4.15）。

## 7. 协作与维护

README 维护功能表、安装方法、配置说明、权限说明和使用示例。Bug 与功能建议通过 GitHub Issue 管理；低到中等复杂度修复类 PR 优先合并；提交信息避免批量重复 `chore` commit 污染历史。项目仅供学习与交流使用，需遵守 QQ / QQ 群相关规范。