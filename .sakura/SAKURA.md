# 项目概述：mjy1113451/astrbot_plugin_gm

> 累计反思 71 次

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

- `/撤回 1` 期望撤回"当前指令上方一条消息"而非指令自身：先取群历史，过滤当前命令 `message_id`，只撤回之前的 N 条可撤回消息；历史接口不可用时不可回退为"撤回指令自身"误报成功；引用撤回优先级保持。
- **本地缓存回退骨架**：① 按群隔离（`{str(group_id): deque[dict]}`）+ 最小化（仅 `message_id` + `user_id`）+ `deque(maxlen)` 显式上限；② 工厂函数 `{}` + `setdefault(key, factory())` 优于 `defaultdict(factory)`，避免 `in`/`copy`/`json.dumps` 意外触发工厂；③ **bot 消息写入必须独立于业务早退链**，置于 `if not enabled: return` / `if not in list: return` 之前（PR #123 阻断性 bug 根因）；④ 容量 `maxlen ≥ 4 × N`；⑤ 必须排除命令自身 `message_id`；⑥ 写入失败 try/except + debug，不阻塞主流程；⑦ README/帮助明示重启不可恢复 + 回退标识"（来自本地缓存）"。
- OneBot `get_group_msg_history` 部分实现不支持；空返回语义模糊（不支持/参数不兼容/权限/历史不足/错误被吞），提示"可能不支持或未返回群消息历史"，不可一概写"不支持"。
- @ 解析不按空格拆昵称（昵称可含空格），优先 segment、`user_id` 或 `_extract_at_qq(raw)`。
- 多编号参数与命令匹配器冲突：`/撤回 1 3 5` 需确认 AstrBot 把整串当 `arg_str` 还是按空格拆。
- PR 描述"提示附带『来自本地缓存』"必须到 diff 中定位确认，避免文档与实现脱钩。

### 4.4 `/撤回 @用户 N` 与 `/撤回用户`（Issue #110、#117）

- `/撤回 @用户 N` 进入普通 `/撤回` 兜底属命令路由/解析 bug，应复用 `recall_user_cmd` 或抽 helper，不复制两套撤回逻辑。
- `/撤回 @用户 N` 和 `/撤回用户 @用户 N` 依赖群历史按 `user_id` 筛选；引用撤回已有 `message_id` 不依赖历史。
- 增量审查风险：只审 diff 会漏掉 `recall_cmd`/`recall_user_cmd` 两端缓存回退的对称性——必须抽样确认三条分支（按数量、按用户、引用）行为一致。

### 4.5 `/取消头衔` 提示成功但实际未清空（Issue #111、#119、#125、PR #123）

- 链路：`/取消头衔` → `unset_group_title_cmd` → `_clear_group_title` → `set_group_special_title`。
- 严格区分 `""`、`" "`、`\t`、`None`、字段缺失；`strip()` 会把单空格误判为空（反模式）；严格判空 `title is None or title == ""`。
- `special_title=""` vs `" "` vs `None` vs 不传、`duration=-1/0/不传` 在 NapCat / Lagrange / go-cqhttp 语义可能不同；API 返回 ok ≠ 实际生效。
- 排查：@ 解析（按空格 split 会误判 `@晚风抱抱我` 类带空格昵称）、`user_id`/`group_id`、目标是否在群、bot 权限、目标为群主/管理员（协议限制）、平台限制或客户端缓存；必要时 `get_group_member_info` 回读，注意缓存、字段差异、刷新延迟。

### 4.6 本地缓存回退模式与严格判空（PR #123）

- 主路径失败 → 本地缓存静默回退 → 双重失败才报错 → 成功时附加来源标识；适用于 OneBot 适配器碎片化场景。
- 对外暴露的通用 helper 优先 `x is None` / `x == ""` 严格判空，避免误丢合法值（0、空集合等）；业务内部 shortcut 可保留 falsy 但 docstring 注明"`0` 视为缺失"等约定。
- 撤回类本地缓存强制 6 项：① 全局 key 数量上限 + LRU；② 写入失败不影响主流程（try/except + debug）；③ 读取排除命令自身；④ README/帮助/schema 同步；⑤ 仅覆盖进程启动后；⑥ 隐私最小化（不缓存内容）。
- `ast.parse` ≠ 真实加载：PR 验证应至少 `python -m py_compile main.py`，最好有最小 AstrBot 启动验证。

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

### 4.11 PR #123 多轮增量审查教训（含 incr1–5，3878727 第五轮）

- **增量审查结构性盲区**：只看 diff 易遗漏 `__init__` 初始化兼容、`after_message_sent` 钩子注册与签名兼容、读取端对新数据结构适配；重写型 PR 必须额外审视 API 兼容性、回退路径、新旧接口映射（`recent_messages` → `message_history` 升级时旧结构残留风险）。
- **审查评分校准**：撤回/缓存核心命令回退路径 bug，影响面涉及"绝大多数未启用某配置的群组"时评分上限 ≤5/10，决策 `request_changes`/`comments`。
- **结构化输出校验失败的反模式**：校验错误出现时应**修复字段输出格式并保留实质判断**（分类/可行性/标签/关键问题列表五项），不得整体退化为"无法评估"——这是仓库反复出现的反模式（PR #123 第六轮审查即因此完全失败）。审查模板固化"字段校验失败时的最小输出保底"。
- **"quick" ≠ 零审查**：涉及权限/撤回/缓存的 PR 最低限度必须覆盖安全检查、schema 一致性、命令签名、关键风险点。
- **commit 信息去重**：多个相同 `chore(sakura): add reflection for ...` 应标记为提交历史质量问题，建议合并或跳过；增量审查优先识别"有价值的代码 commit"与"chore 噪音"（3878727 第五轮 6 个新增 commit 中 4 个 chore 完全相同）。
- **PR 描述数字与 diff 不一致**：描述 +520/-103 vs 提交 +494/-52，审查应主动核对要求作者澄清。
- **`ast.parse` ≠ 真实加载**：PR 用 `ast.parse` 验证是常见错误认知，应替换为 `python -m py_compile main.py`，最好附最小 AstrBot 启动验证。
- **撤回类 PR 强制检查清单（9 项）**：时间窗（2 分钟）、限流、部分失败处理、自身消息排除、bot 消息处理、撤回目标过滤、缓存数据结构、OneBot 适配差异、配置 schema 一致性。
- **多编号参数与命令匹配器冲突**：`/撤回 1 3 5` 需确认 AstrBot 把整串当 `arg_str` 还是按空格拆。

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

### 4.16 语音 STT + 违规词自动撤回/禁言（Issue #127、#128，新增横切关注点）

- **场景**：维护者本人发起，语音消息 STT 转写 → 命中关键词 → 撤回 + 禁言，复用 `_moderation_dispatch` / `_handle_violation`。属非文本消息类型的违规检测扩展。
- **分类与优先级**：`enhancement` + `medium`。**误触发风险**（语音转写误识别 × 关键词模糊匹配 = 双重误判 → 误撤回/误禁言）使优先级不低于 medium；**隐私与生物特征风险**（语音 = 敏感生物特征）需 README 显著告知。
- **核心标签**（新增 `stt`/`voice`/`moderation` 模块标签）：`enhancement` + `stt`/`voice`/`speech-to-text` + `moderation` + `group-management` + `configuration` + `onebot`/`compatibility` + `permission` + `privacy`/`compliance` + `documentation` + `needs-discussion`；条件性 `breaking-change`（若复用 `profanity_keywords` 对老用户构成隐性行为变更）。`needs-info` ≤0.2、`needs-discussion` ≥0.8（决策缺失为主）；`help wanted` ≤0.1。
- **可行性分支变量**：AstrBot 是否暴露 STT provider 接口（消息 segment `type='record'` 是否携带转写文本）决定分支 A/B 工作量差距 ±50%（A: 100-150 行 / 2-3 天；B: 200-300 行 + endpoint 配置 + 流式 + 大文件 + 错误 + 配额 / 5-7 天）。Whisper large-v3 约 3GB 依赖体积是显著部署障碍，建议优先选云端 API 或 small/base 模型。
- **STT 类强制检查项（11 维标准模板）**：① 触发场景（`record`/`ptt` segment）② STT 调用（同步/异步、超时阈值）③ 语音文件获取（OneBot `get_record`/`get_file`、silk/opus/amr/mp3 解码、字段差异 `file`/`url`/`file_size`/`duration`）④ 关键词匹配（大小写/全半角/繁简/谐音/正则/白名单、空列表语义）⑤ 撤回时限（2 分钟硬约束 vs STT 耗时——必先撤回再尝试禁言）⑥ 禁言权限（bot 是否管理员、群主/管理员/触发者豁免）⑦ 降级策略（STT 不可用/超时/失败/未配置 → 跳过本条或禁用功能）⑧ 性能限流（每日上限、每分钟上限、API 成本）⑨ 隐私边界（转写内容缓存、日志、审计、撤回后清理）⑩ 配置 schema（全局 + 群覆盖、空值语义、旧配置迁移；默认禁用而非启用）⑪ 文档同步（README 隐私告知 + 误伤风险 + CHANGELOG）。
- **多模态违规检测标准模式（新增横切关注点）**：消息类型（文本/语音/图片/文件/转发）→ 转文字/转写/标准化层 → 关键词匹配 → 标准处置。`_moderation_dispatch` 中应建立"输入源 → 转写/标准化 → 文本违规检测 → 处置"标准流水线，新增输入源只需补"转写/标准化"环节，避免双份匹配逻辑。
- **异步链路约束**：`on_group_message` 必为纯 `async def + await`，禁 yield（参 §4.1）；STT 异步转写必须 `asyncio.create_task` 包裹 + 异常不外抛；跨事件边界校验（消息 ID 时效性、操作时限）——用户发完语音立即撤回群内其他消息、STT 还没转完，需明确"放弃撤回但仍记录违规次数"的兜底语义。
- **撤回命令族五处同步清单扩展为七处**（涉及多媒体转写层）：`main.py` + README + 帮助命令 + 配置 schema + CHANGELOG + **STT 配置文件/字段**（如 AstrBot 框架 STT 配置项的位置） + **误伤率文档说明**（README 风险提示）。
- **重复检测关键词**（新增）：`voice`、`语音`、`stt`、`speech-to-text`、`transcrib`、`whisper`、`asr`、`voice_violation`、`voice_recall`、`音频`、`语音转文字`、`撤回语音`。
- **关联追溯**：与本仓库现有 `_check_image`（图片 AI 审核）模式同源（多模态内容审核），可作为同类扩展参考。

### 4.17 Issue #130 权限模型重构（移除 plugin_admins，自动继承群原生身份）

- 维护者自提"将插件管理员改为群管/群主自动继承，取消 plugin_admins 设置"。属权限模型重构 + 接口删除（breaking change）。
- 分类 `enhancement` + `breaking-change` + `medium`：删除既有配置项是用户可见 breaking change；横切所有管理类命令但有迁移路径，绝不可降 low。
- 核心标签：`enhancement` + `breaking-change` + `permission`/`permission-model`（建议新建）+ `configuration` + `group-management` + `onebot` + `bot-role`/`sender-role`（建议新建）+ `cleanup`/`deprecation`（建议新建）+ `command`。`needs-discussion` 中高，`needs-info` ≤0.25，`help wanted` ≤0.1。
- sender 角色 vs 配置项本质差异：① 私聊无 `group_id` 降级 ② 匿名消息 `sender.role` 不准 ③ bot 自身角色降级 ④ `get_group_member_info` 缓存策略 ⑤ 跨适配器字段（NapCat/Lagrange/go-cqhttp）。
- 必查 6 项：① 待删除配置项影响范围 ② 跨适配器 API 差异 ③ 缓存与失效 ④ 权限提升风险审计 ⑤ 配置迁移路径 ⑥ API 失败兜底（拒绝 vs 放行）。
- 五处同步清单扩展为六处：`main.py` + `_conf_schema.json` + README + 帮助命令 + CHANGELOG + **迁移指南**。
- 同类配置项扫描：分析时主动检查 `title_admins`/`group_admin_admins`/`kick_admins` 是否同步迁移。
- 建议新标签：`bot-role`/`sender-role`、`permission-model`、`deprecation`（按仓库习惯映射或注明"需维护者确认新增"）。

### 4.18 Issue #129 加群申请拒绝自定义理由（双重需求 + 跨适配器）

- 维护者自提加群申请拒绝时支持自定义理由（**填写**或**配置**两种路径并存）。属 owner-driven UX 增强，与 #57（引用回复同意/拒绝）同工作流扩展。
- 分类 `enhancement` + `medium`：不可降 low（涉及代为拒绝加群申请，存在误拒/理由不当风险）。
- 核心标签：`enhancement` + `group-management` + `join-request`/`join-approval`（建议新建）+ `configuration` + `onebot` + `ux` + `needs-info`（中高：OneBot 适配器版本）+ `needs-discussion`（中：填写策略）+ `related` 指向 #57。`help wanted` ≤0.05。
- OneBot `reason` 字段跨适配器矩阵（建议沉淀）：NapCat ≤10 字符；Lagrange ≤10-20 字符；go-cqhttp 部分 ≤30 字符、部分不限制；空串/None/特殊字符处理各实现可能不同。建议 schema 暴露 `join_reject_reason_max_length` 避免硬编码。
- 双重路径：① 填写（引用回复时输入）→ 解析引用 + 剥离关键词 + 长度截断 + 敏感词过滤；② 配置（全局默认 + 按群覆盖 + 模板列表）→ 五处同步同 `get_group_setting` 模式。复用 `_handle_group_request` 入口避免并行通道。
- 工作量陷阱：看似 60-100 行，实际 80-120 行（解析 + 截断 + L2660/L2709/L2721 三调用点同步 + 五处配置 + 同意侧 `reason` 透传校验）。
- 高频改动点沉淀：`pending_join_requests` + `_handle_group_request` 是高频改动点（#57 + #129 已两次扩展），未来可能再有"同意附言"/"批量审批"/"审批历史"。建议固化调用点地图。
- **未来防御（记忆幻觉警告）**：引用项目记忆 § 编号前必须确认存在（本次反思曾编造"§4.13 UX 增强低估"——§4.13 实际是撤回默认行为/按用户指定编号 Issue #124 而非 UX 估算）。

### 4.19 校验失败整体降级反模式（Issue #130、#131 三轮、#132）

- **场景特征**：原始输出含 `reserved tag syntax in USERNAME` / `expected <SUGGESTED_TITLE>` 等字段校验错误提示，分析流程把校验失败退化为全部"无法评估"/`other`/空标签/无建议。
- **核心反模式**：结构化输出校验失败 ≠ 信息不足。看到字段校验错误时，应**仅修复字段输出格式**，**不得把所有判断都退化为"无法评估"/`other`/空标签/无建议**——这是仓库反复出现的反模式（PR #123 第六轮审查 + Issue #130 + Issue #131 三轮 + Issue #132 五次触发的同一根因）。
- **Pre-check 强制规则**：在任何字段出现"无建议/无法评估/空/未检测到重复"前，必须先确认是否源于校验失败——校验失败应**局部修复**而非**整体降级**。建议固化"校验失败短路器"到反思流程。
- **优先级章节必须显式化决策路径**：owner-driven breaking-change 决策应写出 ① 横切重写 + breaking-change → 最低 medium；② 维护者本人发起 + 已有标准化模式 → 不升 high；③ 工作量可控 + 迁移路径明确 → 不升 high；④ 跨适配器风险已识别但有兜底方案 → 维持 medium。
- **行号引用必须前置声明**：批量行号引用（如 L398-401、L454-468、L607-620、L2266-2296、L2387-2433）前必须声明"基于项目记忆 + 既有 PR 模式推断，建议 PR 提交前以最新 main.py 行号为准"，避免被怀疑是猜测。
- **正确输出保底模板**（校验失败时仍须输出）：分类 + 优先级 + 摘要 + 建议标签列表 + 重复检测（"暂未发现"+ 关键词 + ⚠️措辞核对）+ 标题改写（"可保留"或轻量规范化）。

### 4.20 权限模型重构类 Issue 标签基线 v2（Issue #132 反思）

- **必给标签基线**（与 §4.17 配套的标签清单）：`enhancement` + `breaking-change`（置信度 ≥0.90）+ `deprecation`（≥0.75）+ `permission-model`（≥0.80，新建）+ `configuration`（≥0.85）+ `group-management`（≥0.85）+ `bot-role`/`sender-role`（≥0.70，新建）+ `onebot`/`compatibility`（≥0.65）+ `command` + `needs-discussion`（升 0.75）+ `needs-info`（≤0.45，owner-driven 决策待确认）。
- **应移除标签**：`question`（置信度应 ≤0.05，owner-driven 增强类有明确诉求，非询问）。
- **重复检测必须分类前置过滤**：若两 Issue 的主分类标签不同（一个 bug 一个 enhancement），duplicate 置信度上限 0.3；自动检测算法可能仅基于关键词相似度未结合分类差异（Issue #132 曾把 #125 bug 误判为 #132 enhancement 的重复，置信度 0.95 完全失真）。
- **权限提升风险审计必须给具体命令示例**：至少 2-3 个示例（如 `/踢人`、`/全员禁言`、`/改群名`），并建议"是否需要为这些命令保留 super-admin 概念"作为决策点。
- **同类配置项扫描决策**：主动检查 `title_admins`/`group_admin_admins`/`kick_admins` 是否同步迁移，建议一次性重构而非分散迁移。
- **工作量估算需更保守**：18+ 调用点 + 五处同步 + 迁移路径 + 测试验证 → 实际 200-350 行、3-5 天（不是 150-250 行、1-3 天）。

### 4.21 OneBot 群待办类 Issue 分析模板（Issue #131 三轮反思沉淀）

- **触发场景**：维护者本人发起新增 `/添加群待办` 命令，引用消息回复即可设为群待办。属 owner-driven 命令新增。
- **关键技术事实**：OneBot v11 标准协议**并未定义** `set_group_todo` 或 `send_group_todo`——这是 go-cqhttp/NapCat/Lagrange 等实现的**非标准扩展**。表面与 `/设精` 同构（都是 reply_id + 单 API 调用），实质 API 可用性本身就是个未解问题——是分析中最严重的可行性误判来源。
- **跨适配器差异**（必须列矩阵）：NapCat `_set_group_todo(group_id, message_id)`；Lagrange `set_group_todo(group_id, message_id)`；go-cqhttp 无标准群待办 API（需 HTTP API 插件扩展）。与"群公告"（`set_group_announce`）是不同入口，不可混用。
- **权限风险（被低估）**：QQ 群中**只有群主**能设置群待办（部分客户端允许管理员），与"群管理员可设精"不同——必须建议复用 `_is_group_owner` 而非 `_is_group_admin_or_owner`。
- **"API 返回 ok ≠ UI 生效"专项警示**：QQ 群待办的特殊性：API 返回成功 → QQ 服务端写入 → 客户端 UI 异步刷新（1-2 秒），部分适配器（尤其旧版 go-cqhttp）API 接受但实际不写入。建议指令提示"已设为群待办，请打开群消息顶部查看（约 1-2 秒后生效）"以降低误判。
- **必查项**：① OneBot 适配器是否暴露 `set_group_todo` ② 消息 ID 跨适配器识别 ③ 引用消息中的 `message_id` 提取路径 ④ 权限模型（群主专属 vs 群管即可）⑤ 错误反馈（消息已过期/不是机器人发送的消息）⑥ 撤回场景下的待办撤销。
- **新增命令七处同步清单**（owner-driven 命令新增）：main.py + README + 帮助命令 + `_conf_schema.json`（若新增配置项）+ CHANGELOG + `_GM_COMMAND_NAMES` 元组注册 + 跨适配器兼容性文档。
- **新增标签建议**：`reply`/`quote-message`（标识依赖 reply_id 解析的命令）+ `bot-capability`（依赖 bot 特定能力的命令）+ `onebot-extension`（依赖 OneBot 非 v11 标准 API 的命令）。`todo`/`group-todo`（若仓库未建应建议新建）。
- **引用消息触发型命令分析模板**：OneBot API 标准性 + API 权限要求 + reply_id 解析路径兼容 + 跨适配器 fallback + 消息已撤回兜底。

### 4.22 owner-driven Issue 标签权重校准规则（Issue #131 三轮沉淀）

- **`needs-info` 调整**：owner-driven issue 缺的是"设计决策"而非"事实信息"，应降 `needs-info` ≤0.2-0.30（不是 0.4）。
- **`needs-discussion` 调整**：owner-driven 缺决策时 `needs-discussion` 应保持高权重（0.75-0.85），不是 0.55-0.65。
- **`good first issue` 慎用**：增强类涉及设计决策/兼容性时置信度 ≤0.15（不是 0.2）；涉及跨适配器差异和权限设计决策不应给 good first issue。
- **`help wanted` 几乎不适用**：owner-driven self-implementation（维护者本人提交 + 改法明确 + 工作量小）置信度 ≤0.05-0.1。
- **config 决策清单**（按群覆盖 vs 全局开关）：① 是否需要"某些群禁用"场景？② 是否需要"某些群仅特定人可用"？③ 默认值：全局 enabled，按群 override 关闭为主（与 `group_overrides` 模式一致）。

### 4.23 反思流程纪律性强化（Issue #130 教训）

- **USERNAME 等保留字校验错误的处置**：Issue 中"作者：unknown"、原标题"。"等异常输入不应触发整体降级。应：① 单独标注"作者信息缺失，建议人工补充"；② 对"。"标题进行主动改写（反模式明令）；③ 其他字段继续基于 Issue 正文评估。
- **重复触发同一反模式的根因诊断**：PR #123 第六轮 + Issue #130 + Issue #131 三轮 + Issue #132 + Issue #133 + Issue #134 **六次以上**触发"校验失败整体降级"同一根因。必须在反思流程 Pre-check 阶段固化"校验失败短路器"——若摘要提及字段校验错误，则：仅修复字段输出格式；实质性判断维持原始判断；标题字段在原标题清晰时直接给"可保留"。
- **失败案例的复用价值**：Issue #130、#131、#132、#133、#134 五类分析失误（整体降级 + 禁用措辞 + 标签遗漏）应固化到反思流程 Pre-check 步骤，作为新反思的强制核对项。

### 4.24 Issue #132 权限模型重构模板 v2（与 #130 同模式高频出现）

- **重复出现**："权限模型重构 + plugin_admins + 群原生身份"已成仓库高频模式（#130 + #132），应升级为强模板。
- **必给标签基线**（与 §4.17 配套）：`enhancement` + `breaking-change`（≥0.90）+ `deprecation`（≥0.75）+ `permission-model`（≥0.80，新建）+ `configuration`（≥0.85）+ `group-management`（≥0.85）+ `bot-role`/`sender-role`（≥0.70，新建）+ `onebot`/`compatibility`（≥0.65）+ `command` + `needs-discussion`（升 0.75）+ `needs-info`（≤0.45）。
- **应移除标签**：`question`（≤0.05，owner-driven 增强类有明确诉求，非询问）。
- **重复检测必须分类前置过滤**：若两 Issue 的主分类标签不同（一个 bug 一个 enhancement），duplicate 置信度上限 0.3——Issue #132 曾把 #125 bug 误判为 #132 enhancement 的重复，置信度 0.95 完全失真。
- **权限提升风险审计必须给具体命令示例**：至少 2-3 个示例（如 `/踢人`、`/全员禁言`、`/改群名`），并建议"是否需要为这些命令保留 super-admin 概念"作为决策点。
- **同类配置项扫描决策**：主动检查 `title_admins`/`group_admin_admins`/`kick_admins` 是否同步迁移，建议一次性重构而非分散迁移。
- **工作量估算需更保守**：18+ 调用点 + 六处同步 + 迁移路径 + 测试验证 → 实际 200-350 行、3-5 天（不是 150-250 行、1-3 天）。
- **优先级决策路径显式化**：① 横切重写 + breaking-change → 最低 medium；② 维护者本人发起 + 已有标准化模式 → 不升 high；③ 工作量可控 + 迁移路径明确 → 不升 high；④ 跨适配器风险已识别但有兜底方案 → 维持 medium。
- **行号引用必须前置声明**：批量行号引用前必须声明"基于项目记忆 + 既有 PR 模式推断，建议 PR 提交前以最新 main.py 行号为准"。

### 4.25 Issue #133 解禁/解除禁言类标准分析模板（与头衔类对等）

- **触发场景**：`/解禁 @用户` / `unmute_cmd` 提示成功但目标仍被禁言——属仓库"提示成功但实际未生效"通用模式的解禁子场景。Issue #133 用户用 `[bug][medium] /解禁 @用户 提示成功但疑似未实际生效` 命中该模式。
- **必查项（9 项）**：① Bot 在该群角色（部分协议要求群主专属解禁）② 目标用户是否仍在群内 ③ OneBot 实现版本（NapCat/Lagrange/go-cqhttp 对 `set_group_ban` / `delete_group_ban` 语义差异）④ `duration` 参数语义（`duration=0` vs 不传 vs `duration=-1`）⑤ `_extract_at_qq` 解析（必须按 segment/user_id，不按空格 split）⑥ `get_group_member_info` 回读校验（API 返回 ok ≠ 实际生效）⑦ 目标若已退群如何兜底 ⑧ 完整执行日志 ⑨ 最近配置变更。
- **必给标签**：`bug` + `command` + `group-management` + `unmute`/`lift-ban`（建议新建，对等头衔类）+ `onebot` + `compatibility` + `bot-role` + `needs-info`（0.85+，解禁类缺适配器版本/截图/目标身份是定位根因的硬阻塞）。
- **优先级**：`medium`（核心命令局部不可用 + 误判用户状态风险 + 跨适配器兼容风险已识别但有兜底）。
- **优先级决策路径显式化**：① 核心命令局部不可用 → 最低 medium；② 涉及禁言/解禁误判（用户可能不知道仍被禁言）→ 不降 low；③ 跨适配器兼容风险已识别但有兜底 → 维持 medium；④ 信息不全待根因确认 → 不升 high。
- **工作量需分支判定**：分支 A（API 层兼容问题，`duration=0` 语义差异）~20-40 行 + 1 天；分支 B（补完整状态回读链路）~50-100 行 + 1.5-2 天；分支 C（重构解禁入口或权限校验）~100-150 行 + 2-3 天。
- **falsy 判空陷阱**：`duration` 参数若用 `if not duration` 会把 `0` 误判为未传（`0` 是合法解禁值），必须用 `is None` 或 `== -1`。
- **早退语句吞噬共享逻辑陷阱**：解禁流程中权限早退/参数校验早退会导致回读/日志未执行，必须前置——这是 §PR 审查经验中明确指出的高频陷阱。
- **禁言/解禁三层语义**：A. 群管 API 禁言（`set_group_ban`）；B. 插件自怼（插件内部记录）；C. 审批工作流待审批禁言状态。分析解禁类 Issue 必须先确认用户指哪一层。
- **"提示成功但实际未生效"通用模板扩展（覆盖解禁/头衔/设精/改群名/全员禁言）**：通用必查项：① bot 权限 ② 目标用户身份 ③ OneBot 实现版本 ④ `_extract_at_qq` 解析 ⑤ API 参数语义（duration=0/""/None）⑥ 状态回读 ⑦ 适配器差异 ⑧ 提示语区分接口成功与实际生效。
- **建议新增细粒度动作标签**：`unmute`/`lift-ban`/`mute-action` 对等仓库已有 `title`/`special-title` 标签先例（#125）。

### 4.26 Issue #134 装饰字符 QQ / 视觉欺骗型用户名解析类 bug 模式（新增高频模式）

- **场景特征**：花体字（𝓒𝓪𝓷𝓬𝓮𝓻）、手写体、装饰字符、组合 Unicode 字母（𝐀、𝕒 等数学字母块）等"看起来是 QQ 号"但实际是字符串的输入，是命令解析类 Issue 的常见根因。本 Issue 中 `/解禁 @𝓒𝓪𝓷𝓬𝓮𝓻` 被解析为字面字符串导致误解禁（实际禁言未解除），命令"成功"但行为错误。
- **主分类**：`bug`（命令行为与意图不符）；辅助 `command` + `parser` + `at-parse`/`at-extract`（建议新建）+ `group-management` + `needs-info`。
- **优先级**：`medium`（核心禁言/解禁命令对群管理影响范围大，**误解禁安全影响大于误禁言**——用户已被禁言状态下，误解禁使其重新获得发言权，可能放大后续违规；但单群单次误操作不升 high）。
- **必查项（10 项）**：① `_extract_at_qq` 是否对装饰字符（数学字母、组合字符、Emoji 风格 QQ）做归一化 ② 装饰字符 QQ 经 AstrBot 事件框架后是原始字符串还是已规范化 ③ OneBot v11 `message` 段 `qq` 字段类型（字符串 vs 数字）④ 跨适配器对装饰字符 QQ 的处理 ⑤ 群号是否被装饰字符污染 ⑥ 是否有 `get_group_member_info` 回读校验 ⑦ OneBot 实现与版本 ⑧ AstrBot 版本与插件 commit ⑨ 完整命令与日志 ⑩ 近期配置变更。
- **修复方向**：在 `_extract_at_qq` 增加归一化层（`unicodedata.normalize('NFKC', s)` + 正则 `\d{5,12}` 强校验），或要求装饰字符 QQ 必须 `@真实QQ` 同时输入；修复时统一加"目标 QQ 格式不正确"硬校验提示。
- **工作量**：20-60 行（条件判断+测试用例），1-2 天；装饰字符 QQ 测试矩阵（NapCat/Lagrange/go-cqhttp × 数学字母/手写体/Emoji 风格）至少需半天构造测试用例。建议小修复工作量下限 1 天，包含最小适配器验证。
- **重复检测关键陷阱**："症状相似 ≠ 根因相似"——#125（头衔 `special_title` 传参与回读）与 #134（`_extract_at_qq` 输入解析）都用"获取信息问题"作为症状描述，但根因模块完全不同。**重复检测必须先按模块归类再判断重复**，不要按症状字符串相似度。
- **重复检测关键词必须包含模块名**：`解禁`、`@用户解析`、`_extract_at_qq`、装饰字符 QQ、NFKC 归一化。仅按症状相似度（如"获取信息问题"）会反复误报 #125。
- **项目记忆激活缺陷**：记忆 §头衔类模板必查项⑦ 已提及 "`_extract_at_qq` 解析"，但本次分析未激活——说明基于关键词的模板触发机制对"解禁/禁言"类命令不敏感，应扩展关键词覆盖范围。**遇到 `_extract_at_qq` 相关 Issue 必须主动激活该记忆**。
- **新增重复检测关键词**：`花体字`、`数学字母`、`组合字符`、`装饰字符 QQ`、`NFKC`、`unicodedata`、`visual spoofing`、`unicode-block`。

## 5. Issue 分析与标签经验（高层规则，详见 memory.md）

- 标题为"。"、"，"或信息极少时必须基于正文错误文本、复现命令和代码线索检索。
- **结构化输出校验失败 ≠ 信息不足**：应**修复字段输出**保留实质判断（分类/可行性/标签/关键问题列表），不得整体退化为"无法评估"——这是仓库反复出现的反模式（PR #123 第六轮审查即因此完全失败）。pre-check：任何字段出现"无建议/无法评估/空"前，确认是否源于校验失败。
- 不能因校验失败把 `bug`/`enhancement` 降级为 `other`、标签留空、可行性"无法评估"。
- 标签建议覆盖主类型、模块和风险；至少保留主标签与核心模块；高频模块标签：`recall`、`message-history`、`command`、`parser`、`onebot`、`group-management`、`moderation`、`stt`/`voice`、`title`/`special-title`。
- **重复检测措辞模板**：无历史列表时**必须**写"暂未发现（建议检索关键词：...）"，不得写"未检测到重复"/"无重复"/"可能是 #X 的重复"。方向相反但同主题（如 #124 增强 vs #126 删除）严格归为 `related` 而非重复。
- **撤回命令族五处同步清单**（高频踩坑）：`main.py` + `README.md` + `/撤回`/`/消息列表` 帮助文本 + `_conf_schema.json` + CHANGELOG；扩展为七处（涉及多媒体转写层）：+ STT 配置文件/字段 + 误伤率文档说明。
- **删除既有命令用法类 Issue 强制结构**（维护者自提减法）：① 精确删除目标（Path 分支/行号）② 保留目标边界 ③ 删除后旧语法处理 ④ 依赖解耦（如 `/消息列表` ↔ `/撤回 编号`）⑤ 用户迁移成本与告知 ⑥ CHANGELOG breaking-change 标注。
- **"功能裁剪"类优先级判定**：维护者自提 + 纯删减 + 改动局部化 → `low`~`medium`；涉及对外契约删减且与并行 Issue 方向冲突 → `medium` 且强化 `needs-discussion`。
- **路由语义歧义类 Issue**：必须显式列出候选语义并请求维护者确认，标 `needs-discussion`。
- 信息不足时可标 `needs-info`；头衔类 bug 还需 bot 群角色、目标用户角色、近期配置变更。
- **"默认行为"类改动**：UX 增强常被低估工作量，预留 40-80 行而非 20-40。
- **校验失败短路器（强制 Pre-check）**：在任何字段出现"无建议/无法评估/空/未检测到重复"前，必须先确认是否源于校验失败——校验失败应**局部修复字段输出格式**（如把"无建议"改成实际建议），**不得把所有判断都退化为"无法评估"/`other`/空标签/无建议**。**实质性判断（分类/可行性/标签/标题）维持原始判断**。
- **重复触发反模式的纪律性**：同一反模式若在多个反思中反复触发（如"校验失败整体降级"在 PR #123 + Issue #130 + #131 三轮 + #132 五次触发），说明反思流程缺乏自动化保护机制，必须固化 Pre-check 短路器到流程而非仅依赖记忆。
- **正确输出保底模板**（校验失败时仍须输出）：分类 + 优先级 + 摘要 + 建议标签列表 + 重复检测（"暂未发现"+ 关键词 + ⚠️措辞核对）+ 标题改写（"可保留"或轻量规范化）。

## 6. 开发约定与注意事项

- 逻辑集中在 `main.py`，修改时全局搜索相似命令模式，避免复制粘贴式遗漏。
- 管理员 QQ 号按字符串处理；群号统一 `str()` 归一化（缓存键、日志键、配置键一致）。
- QQ 操作依赖平台 API 和机器人群权限，必须处理接口失败、权限不足、消息超时和异常返回。
- 权限类改动必须覆盖：全局配置、群级覆盖、命令入口、权限判断函数、文档说明和回归测试。
- AstrBot API/命令解析兼容问题，应区分插件启动、命令注册、命令调用、特定输入触发四个阶段。
- 对群管理"成功提示"保持保守：设/取消头衔、设/取消管理、禁言、踢人、撤回、改群昵称等都应检查 API 返回与状态，失败时给明确提示；"API 返回 ok ≠ 实际生效"是已知反模式，必要时回读。
- 对依赖 OneBot 能力的命令，应在 README/帮助中标注依赖与替代方案。
- 新增跨私聊/群聊工作流时，必须先设计状态机、申请 ID、权限边界、持久化/过期、并发幂等、隐私和发送失败处理。
- 引入外部代码前评估：许可证兼容、依赖与框架版本、代码风格、维护责任、配置 schema 兼容性、是否应抽取通用逻辑而非直接复制。
- 撤回相关改动必须做**对称性检查**：`recall_cmd` 与 `recall_user_cmd` 在入口分流、缓存读写、用法提示上必须对称；`/撤回自身 N` 与新默认行为不得冲突；`message_history` 写入路径不得被业务早退链吞噬。
- **撤回类 PR 强制检查清单（9 项）**：时间窗（2 分钟）、限流、部分失败处理、自身消息排除、bot 消息处理、撤回目标过滤、缓存数据结构、OneBot 适配差异、配置 schema 一致性。**删除类反向清单（9 项，参 §4.15）**：精确删除路径 + 保留路径边界 + 调用点清空 + README 帮助文案清理 + yield 帮助文本同步 + 配置 schema 语义缩窄 + bot 回复模板措辞清理 + CHANGELOG breaking-change 标注 + 替代方案提示。
- 验证清单：`python -m py_compile main.py` ≥ `ast.parse`；本地缓存回退类改动应附最小单元测试；README/帮助/schema/CHANGELOG 必须在同一 PR 同步；提交信息避免批量重复 `chore` commit（属提交历史质量问题——参 §4.11、§4.14）；行号引用必须标注"已读取 main.py 验证"或用"约 Lxxxx"模糊表述。
- **AstrBot 消歧层选择**：撤回/计数类命令的参数语义修改必须明确是在 `@filter.command` 装饰器签名层（改类型注解/默认值）还是 handler 内部（先收 `str` 再分流）做消歧——后者要处理 `try/except int()` 已被 AstrBot 提前按注解转换的情况（参 §4.2、§4.15）。
- **OneBot 群待办类命令七处同步清单**（新增 owner-driven 命令模板，参 §4.21）：main.py + README + 帮助命令 + `_conf_schema.json` + CHANGELOG + `_GM_COMMAND_NAMES` 元组注册 + 跨适配器兼容性文档。
- **owner-driven Issue 标签权重校准**（§4.22）：`needs-info` ≤0.2-0.30（不是 0.4），`needs-discussion` 0.75-0.85（不是 0.55-0.65），`good first issue` ≤0.15（不是 0.2），`help wanted` ≤0.05-0.1。
- **权限模型重构类 Issue 必给标签基线**（§4.20、§4.24）：`enhancement` + `breaking-change` ≥0.90 + `deprecation` ≥0.75 + `permission-model` ≥0.80 + `bot-role`/`sender-role` ≥0.70 + `onebot` ≥0.65 + `needs-discussion` 升 0.75；移除 `question`。
- **解禁/解除禁言类 Issue 标准模板**（§4.25）：必查 9 项 + 必给标签（含新建 `unmute`/`lift-ban`）+ 分支判定（API 层/状态回读/重构入口）+ falsy 判空陷阱（`duration=0` 是合法解禁值）。
- **装饰字符 QQ / 视觉欺骗型用户名解析类 bug 模式**（§4.26）：`_extract_at_qq` 必须增加 NFKC 归一化层 + 正则 `\d{5,12}` 强校验；重复检测关键词必须包含模块名，避免症状相似误报 #125。

## 7. 协作与维护

README 维护功能表、安装、配置、权限说明和使用示例。Bug 与功能建议通过 GitHub Issue 管理；低到中等复杂度修复类 PR 优先合并；提交信息避免批量重复 `chore` commit 污染历史。项目仅供学习与交流使用，需遵守 QQ / QQ 群相关规范。