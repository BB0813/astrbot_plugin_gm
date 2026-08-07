# 项目概述：mjy1113451/astrbot_plugin_gm

> 累计反思 33 次

## 1. 项目简介

`astrbot_plugin_gm` 是 AstrBot 的 QQ 群管理插件，面向 QQ 群聊管理场景，提供插件管理员维护、禁言/解禁、踢人、撤回消息、群昵称、头衔、精华消息、官方群管理员设置等能力。项目主要逻辑集中在 `main.py`，依赖 AstrBot 插件体系与 aiocqhttp / OneBot API。

主要命令：`/设管`、`/取管`、`/禁言`、`/解禁`、`/禁我`、`/踢`、`/头衔`、`/取消头衔`、`/设管理`、`/取消管理`、`/设精`、`/设群昵称`、`/改昵称`、`/撤回`、`/撤回用户`。

## 2. 技术栈与结构

- **语言**：Python 3.10+
- **框架**：AstrBot 插件体系
- **平台接口**：aiocqhttp / OneBot action（`delete_msg`、`get_group_msg_history`、`set_group_special_title`、`set_group_ban` 等）
- **配置**：`_conf_schema.json` + `main.py` 运行时读取
- **许可证**：MIT

```text
astrbot_plugin_gm/
├── main.py              # 插件主逻辑：命令、权限、配置、OneBot API 兼容
├── metadata.yaml        # 插件元信息
├── _conf_schema.json    # AstrBot 配置 Schema
├── README.md            # 安装、配置、命令、权限说明
└── docs/                # 补充文档
```

## 3. 权限与配置模型

1. **插件管理员**：由 `plugin_admins` 或 `/设管` 动态维护；群主默认具备插件管理员身份。
2. **QQ 官方权限**：禁言、踢人、撤回、设精、设/取消管理员/头衔仍依赖机器人在群内的官方权限。
3. **专项权限/按群覆盖**：代码中存在 `title_admins`、`group_admin_admins`、`kick_admins`、`group_admins`、`group_overrides`、`get_group_setting` 及 `has_title_admin_rights` / `has_kick_admin_rights` / `has_group_admin_rights` 等机制；权限需求应先检查这些入口，避免只改命令层。
4. **全局默认 + 群级覆盖**：明确缺省回退、空列表/空对象/`0` 的语义。`0` 可能是合法配置（如关闭阈值），不能误当作缺失而回退。
5. **跨私聊审批权限边界**：若新增私信申请解禁等远程审批功能，必须明确插件管理员是否可对所有群代 bot 解禁，审批者是否需属于目标群或具备目标群专项权限，并记录可审计状态。

常见配置项：`show_recall_notice`、`reject_re_add`、`plugin_admins`、`mute_kick_threshold`、`group_overrides`；私聊申诉可能新增 `appeal_enabled`、`appeal_admin_qqs`、`appeal_admin_group`、`appeal_expire_minutes` 等。配置定义、业务逻辑、README、帮助文本和配置展示必须同步。

## 4. 近期反思沉淀

### 4.1 AstrBot async / yield / return 风险（PR #116）

- `async def` 内只要出现 `yield`，函数就变为 async generator，不能 `return True/False` 等非空值，也不能被普通 `await func()` 当作 coroutine 使用。
- 权限 helper（被 `await` 并返回业务值）函数体内不得出现 `yield`；需发送提示时统一使用 `_send` / `_build_text` 等封装。
- 顶层命令 handler 可使用 `yield event.plain_result(...)`，但不要在同一函数内混用两套响应机制。
- 语法级修复不能只看 AST：建议 `python -m py_compile main.py` 或 `python -m compileall .`，并至少验证插件加载、无权限提示、有权限继续。
- 审查固定项：搜索 `async def`、`yield`、`return <value>`，确认所有被 `await` 的 helper 不是 async generator。新增任何 helper 都要沿用此约束（与 Issue #121 风险叠加）。

### 4.2 `/撤回` count 参数解析（Issue #106）

- 命令签名用 `count: int = 0/1` 时，AstrBot 可能按注解提前转换参数，函数体内 `try/except int(count)` 捕获不到。
- 稳健策略：复杂命令入口用 `str` 或原始参数接收，在函数内统一解析、校验并给友好提示。
- 同类入口要一起排查：`recall_cmd`、`recall_user_cmd` 及所有 `: int =`、`count: int` 命令参数。
- 测试重点：`/撤回`、`/撤回 3`、`/撤回 abc`、引用撤回、带 @ 用户和数量的撤回用户场景、空字符串、负数、过大数字、中文数字。

### 4.3 `/撤回 N` 语义与历史接口（Issue #109、#118）

- `/撤回 1` 用户期望撤回"当前指令上方一条消息"，不应撤回指令自身。先获取群历史，过滤当前命令 `message_id`，只撤回命令之前的 N 条可撤回消息。
- 历史接口不可用时应明确提示，不能回退成"撤回指令自身"并误报成功；引用撤回优先级必须保持。
- 依赖 `get_group_msg_history`，部分 OneBot 实现不支持则不可用。fallback：插件侧按群维护最近消息缓存（`message_id`、发送者、时间），优先历史接口，失败回退缓存，或配置选择优先级。
- 缓存方案风险：仅覆盖机器人在线后收到的消息，重启丢失；需按群隔离、限制容量、不缓存内容（隐私）；需处理并发顺序、消息超时、权限、消息 ID 类型差异、自身过滤、缓存不足提示。

### 4.4 `/撤回 @用户 N` 与 `/撤回用户`（Issue #110、#117）

- `/撤回 @用户 N` 进入普通 `/撤回` 兜底提示属命令路由/解析 bug，应复用 `recall_user_cmd` 或抽 helper，不复制两套撤回逻辑。
- `/撤回 @用户 N` 和 `/撤回用户 @用户 N` 依赖群历史并按 `user_id` 筛选；引用撤回已有明确 `message_id`，不依赖历史。
- 历史返回空不一定等于"不支持接口"：也可能是参数不兼容、权限限制、返回结构差异、历史数量不足或错误被吞。提示语可写"可能不支持或未返回群消息历史"。
- @ 解析不应按空格拆昵称（昵称可能含空格），优先用消息 segment、`user_id` 或 `_extract_at_qq(raw)`。
- README/帮助应说明：`/撤回 N`、`/撤回 @用户 N` 依赖 OneBot `get_group_msg_history`；不支持时请用引用撤回或切换支持群历史接口的实现。

### 4.5 `/取消头衔` 提示成功但实际未清空（Issue #111、#119）

- 链路：`/取消头衔` → `unset_group_title_cmd` → `_clear_group_title` → OneBot `set_group_special_title`。
- 归为 `bug + medium`：已有命令提示成功但效果错误，不是 `other` 或"无法评估"。
- 高风险点：`special_title=""`、`" "`、`None`、不传字段、`duration=-1/0/不传` 在 NapCat / Lagrange / go-cqhttp 语义可能不同；API 返回 ok 不代表实际生效。
- 若代码用 `special_title=" "` 兜底会把头衔设为空格；若回读时 `strip()`，会把空格误判为清空成功。严格区分 `""`、`" "`、`\t`、`None`、字段缺失。
- 接口失败、权限不足、异常被吞后仍提示成功是禁止项。必要时用 `get_group_member_info` 回读 `special_title`/`title`，但注意缓存、字段差异和刷新延迟。
- 需排查 @ 解析、`user_id`/`group_id`、目标是否在群、机器人权限、目标为群主/管理员、平台限制或客户端缓存。

### 4.6 禁言踢出阈值按群配置/展示（Issue #107）

- 核心是配置 UI/Schema/展示未体现"全局默认 + 群级覆盖"，归 `bug`，辅以 `configuration`、`schema`、`ui/config-ui`、`documentation`、`group-config`。
- 不删除全局 `mute_kick_threshold`；它应说明为"全局默认禁言踢出阈值"，可被群级覆盖。
- 展示建议显示"有效值 + 来源"，如"禁言踢出阈值：3，来源：当前群覆盖；全局默认：5"。
- 缺失 key 回退全局；显式配置 `0` 表示关闭/覆盖，不能当未配置。

### 4.7 专项权限按群配置（Issue #105）

- "头衔、管理、踢人等专项权限按群独立配置"属权限模型增强，通常标 `enhancement`，重点是按动作授权、符合最小权限原则。
- 改变 `group_admins` 语义要考虑迁移、废弃期或兼容读取。
- 敏感操作（踢人、设/取消管理、头衔）必须做越权和误授权测试。

### 4.8 私信申请解禁与管理员审批流程（Issue #120、#121）

- 归 `enhancement` / `feature`，优先级 `medium`：增强而非修复，但涉及自动解禁敏感动作，存在越权/误解禁/并发竞态风险，不宜降为 low。
- 标签建议：`enhancement`、`group-management`、`moderation`、`mute`、`private-message`、`approval-flow`、`permission`、`configuration`、`needs-discussion`；标签体系简单时至少保留主标签与核心模块。
- 最小可用实现：私聊命令 `申请解禁 群号 说明` → 生成申请 ID → 转发固定管理员 QQ → 编号同意/驳回 → 复用 `_unmute_member` / `set_group_ban(duration=0)` → 私信通知。
- 完整可靠实现：管理员 QQ + 管理群、引用/编号/专用命令审批、状态持久化、重启恢复、过期、重复申请去重、多管理员并发幂等、群成员/bot 权限校验、README/schema/帮助同步。
- 私聊无 `group_id`：必须由用户输入群号或复用最近禁言/禁我记录；必须校验用户是否在目标群、是否真被禁言。
- "禁言"与"禁我"是不同状态：OneBot 群禁言 vs 插件内部自怼存储；确认 `/解禁` 是否覆盖两者，否则流程会分叉。
- 审批不能仅靠"同意/驳回"关键词（管理群易误触发）。应优先申请编号、引用申请消息或 `/解禁审批 同意 <id>`，并校验审批者 `sender.user_id`（非 `event.user_id`）。
- 隐私：申请说明可能敏感，只转发可信管理员/管理群；私信/群通知可能因风控、好友关系、bot 被禁言、不在群失败，需处理。
- 自动解禁是敏感动作：只有配置的插件管理员或授权群管理员可审批；管理群消息来源不等于审批者可信；记录审批日志；失败反馈原因。
- 重复检测：写"暂未发现"，列关键词（`申请解禁`、`禁言申诉`、`禁我`、`私信`、`审批`、`解除禁言`、`set_group_ban`、`unmute`、`appeal`）；只有完整用户故事（私聊申请 + 管理员审批 + 自动执行/通知）一致才判重复，主题相近应标"关联"。
- 工作量：最小可用版中等偏低；完整版中等到中高。
- PR #116 风险叠加：新增 helper 必须纯 `async def`，避免在 `await` 业务 helper 中混 `yield`。

### 4.9 合入外部仓库与批量撤回增强（Issue #122）

- 标题为"。"、正文仅给 URL+命令形式时，不能依赖标题分类；必须从正文重建需求。
- 分类 `enhancement`（辅以 `merge-request` / `external-repo`），优先级 `medium`：撤回是常用功能但批量非核心刚需，工作量中等。
- 可行性维度：外部仓库代码质量评估、OneBot 适配兼容、与本仓库命令注册/权限模型集成点、`_conf_schema.json` 是否需扩展、bot 权限要求、缓存策略选择（短期内存 vs 持久化）、撤回时间窗（普通成员 2 分钟内）、限流保护、bot 自身消息处理、部分失败处理。
- 标签建议：`enhancement`、`recall`、`command`、`message-history`、`compatibility`、`onebot`、`needs-info`、`external-integration` / `merge-request`。`help wanted` 置信度应据"是否需要外部贡献"判断，避免泛用。
- 信息严重不足时应主动追问：当前命令失败行为、目标 OneBot 适配器（NapCat/go-cqhttp/Lagrange）、外部仓库代码细节、期望行为（正/倒序、是否排除机器人消息）。
- 标题改写示例：`[enhancement][medium] 合入 astrbot_plugin_batchrecall，提供 /撤回 数量 与 /撤回 @用户 数量 批量撤回能力`；或更柔和的"参考 astrbot_plugin_batchrecall，新增批量撤回能力"。
- 外部代码合入需关注：代码归属、许可证（LICENSE 兼容性）、依赖与框架版本、代码风格统一、维护责任、submodule/copy/vendor 选择、后续同步策略。
- 复用了 §4.2–§4.4 已有沉淀：`recall_cmd` / `recall_user_cmd` 参数解析、自身 `message_id` 排除、OneBot 适配差异、@ 解析等。

## 5. Issue 分析与标签经验

- 标题为"。"、"，"或信息极少时，不能依赖标题分类；必须基于正文错误文本、复现命令和代码线索检索。
- **结构化输出校验失败 ≠ 信息不足**：看到 `expected <SUGGESTED_TITLE>` 等校验错误时，应优先修复字段输出（如把"无建议"改成实际建议），不得把所有判断都退化为"无法评估"。这正是仓库反复出现的反模式。
- 不能因校验失败把明确的 `bug` / `enhancement` 降级为 `other`、标签留空、标题"无建议"、可行性"无法评估"。
- 标题带 `[bug][medium]`、`[enhancement][medium]` 可作信号，但仍需结合正文和代码验证；标题已清晰时写"原标题可保留"或给轻量规范化版本。
- 标签建议覆盖主类型、模块和风险，不应只给单个 `enhancement` 或因校验失败留空；至少保留主标签与核心模块；复杂功能补 `permission`、`configuration`、`needs-discussion`、`needs-info`。
- 重复检测：写"暂未发现"或"疑似关联"，并给检索关键词；同命令/同主题不等于同问题，只有完整用户故事一致才判重复。声称"可能重复 #35"等具体编号前必须核实该 Issue 是否包含完整链路；只涉及相近主题应标"关联/可参考"而非重复。关键词：撤回（`/撤回`、`/撤回用户`、`@用户`、`get_group_msg_history`、`message_id`、`delete_msg`、`batch recall`、`批量撤回`）；头衔（`取消头衔`、`special_title`、`空格头衔`、`set_group_special_title`）；解禁审批（`申请解禁`、`禁言申诉`、`私信`、`审批`、`禁我`、`appeal`、`unmute`）。
- 信息不足时可标 `needs-info`，要求补充 AstrBot 版本、OneBot 实现与版本、插件 commit、完整命令、日志和权限；但不应掩盖明确的命令行为缺陷或功能请求。

## 6. 开发约定与注意事项

- 插件逻辑集中在 `main.py`，修改时全局搜索相似命令模式，避免复制粘贴式遗漏。
- 管理员 QQ 号建议按字符串处理，避免数字精度或格式问题。
- QQ 操作依赖平台 API 和机器人群权限，必须处理接口失败、权限不足、消息超时和异常返回。
- 权限类改动必须覆盖：全局配置、群级覆盖、命令入口、权限判断函数、文档说明和回归测试。
- AstrBot API/命令解析兼容问题，应区分插件启动、命令注册、命令调用、特定输入触发四个阶段。
- 对群管理"成功提示"保持保守：设/取消头衔、设/取消管理、禁言、踢人、撤回、改群昵称等都应检查 API 返回与状态，失败时给明确提示。
- 对依赖 OneBot 能力的命令，应在 README/帮助中标注依赖与替代方案，避免用户把平台能力限制误认为插件崩溃。
- 新增跨私聊/群聊工作流时，必须先设计状态机、申请 ID、权限边界、持久化/过期、并发幂等、隐私和发送失败处理。
- 引入外部代码（合入/submodule/copy/vendor）前评估：许可证兼容、依赖与框架版本、代码风格、维护责任、配置 schema 兼容性、是否应抽取通用逻辑而非直接复制。

## 7. 协作与维护

README 维护功能表、安装方法、配置说明、权限说明和使用示例。Bug 与功能建议通过 GitHub Issue 管理；低到中等复杂度修复类 PR 优先合并。项目仅供学习与交流使用，需遵守 QQ / QQ 群相关规范。