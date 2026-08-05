# 项目记忆

累计反思 11 次

## 仓库背景

仓库 `mjy1113451/astrbot_plugin_gm` 是 AstrBot 群管理类插件，Issue 常涉及命令解析、群管理权限、按群配置、配置 schema 与 README 同步。注意 Issue 中可能出现旧插件名或相近插件名（如 `astrbot_plugin_group_admin`），分析时需确认与当前仓库/插件注册名是否一致，避免把推断写成事实。

## Issue 分析经验

### 1. 分类与优先级

- 明确运行时报错、命令参数类型错误、用户反馈“更新后仍存在”、命令期望/实际行为不一致、命令返回成功但实际未生效时，主分类应为 `bug`；可辅助标 `command`、`parser`、`compatibility`、`regression/not fixed`、`needs info`。
- 权限/配置粒度调整如“头衔、管理、踢人权限按群独立配置”，通常是 `enhancement`；但若代码已有 `group_overrides/get_group_setting` 能力、只是 schema/UI/文档仍表现为全局配置，则更偏 `bug` + `configuration/schema/ui/documentation`。
- `medium` 适用于核心命令局部不可用、权限配置影响多群但非阻断、配置展示误导、群管理命令误报成功。启动/加载失败、安全越权、严重误撤大量消息可为 `high`；纯说明不清可降为 `low-medium`。
- 标题为空、“。”、“，”或结构化字段失败时，仍应从正文提炼分类、优先级、标签和标题，不能降为 `other` 或“无法评估”。

### 2. AstrBot 命令参数与解析

- 对 `@filter.command(...)`，要区分错误发生在启动/命令注册阶段，还是用户调用后的函数阶段。若 AstrBot 根据注解提前转换参数，函数体内 `try/except int(count)` 无法兜底。
- 遇到 `参数 count 类型错误`、`count(int)=0`、用户称“更新后仍存在”，优先检查签名如 `count: int = 0/1`，确认触发命令、堆栈、AstrBot/插件版本、是否旧缓存，并追踪最近 PR/commit，判断修复方向错误还是入口覆盖不全。
- 修复方向通常是命令入口用 `str`/可选原始参数接收，在函数内统一转换、校验并返回友好提示；需明确 `0`、空字符串、`None`、负数、过大值语义。
- 不要只修单一入口；全局搜索 `count: int`、`: int =`、`filter.command`，检查 `/撤回`、`/撤回用户` 等复制粘贴式问题，以及 `int/bool/float/At` 被框架预解析的风险。
- `/撤回 @用户 N` 与 `/撤回用户 @用户 N` 要区分“命令不存在”和“解析入口错误”。若文档/帮助暗示“撤回某人上一条不用引用”，则 `/撤回 @用户 N` 被普通 `/撤回` 分支吞掉更偏 bug/UX。实现别名时必须复用同一权限、数量限制、群聊检查和错误提示。
- `@用户` 不应简单按空格 split；昵称可能包含空格。优先依赖消息 segment、user_id 或框架 At 类型解析，并处理无 @、多个 @、非法数量、0、负数。

### 3. 撤回命令与消息历史

- `/撤回 1` 在群管理语境中通常意味着撤回“当前命令之前的 1 条消息”，不是撤回指令自身。若用户说“撤回了指令本身”，即使正文很短也是明确 bug，标题可改为：`/撤回 1 应撤回上一条消息而非指令本身`。
- 分析 `recall_cmd`：是否先撤回触发命令自身、是否把当前 `event.message_id` 纳入候选、count 是否从目标消息开始计数、历史消息排序正/倒序、当前指令是否出现在历史中。
- 修复建议：先获取群消息历史并过滤当前命令 message_id，只撤回命令之前 N 条可撤回消息；历史接口不可用时返回明确提示，通常不要回退为撤回指令自身以免误报成功。
- OneBot/适配器风险：`get_group_msg_history` 可能不可用，返回顺序/字段/message_id 类型不同；机器人可能因权限不足、消息超时、非自身消息而无法撤回；引用撤回语义应优先且不能被破坏。
- 测试覆盖 `/撤回 1/2/3`、无参默认、回复撤回、@用户+数量、消息不足、权限不足、历史接口不可用、群聊/私聊、不同 AstrBot/OneBot 实现。

### 4. 头衔与群管理 API 成功但未生效

- “命令提示成功但实际没取消/没设置”属于 bug，常见于群头衔、管理员、踢人、禁言、群名片等外部 API 调用。分析链路应固定为：命令解析 → 权限判断 → API 参数 → 适配器兼容 → API 返回值 → 状态回读 → 用户提示。
- `/取消头衔` 需检查 `unset_group_title_cmd`、`_clear_group_title`、OneBot `set_group_special_title` 参数：`special_title=""`、`duration=-1/0/不传` 在 NapCat/Lagrange/go-cqhttp 中语义可能不同；API 返回 ok 不代表业务生效。
- 修复建议应同时考虑参数兼容、权限失败和缓存延迟：机器人是否为管理员/群主、目标是否群主或更高权限、平台是否吞权限错误、QQ 客户端是否延迟展示。
- 可加入 `get_group_member_info` 回读确认，但要说明回读也可能受缓存/字段差异影响；必要时短延迟回读，或提示“已发送取消请求，请稍后确认”，避免从误报成功变成误报失败。
- 标签候选：`bug, command, group-management, title/special-title, compatibility, needs-info`；需补充 AstrBot、插件 commit、OneBot 实现、机器人权限、目标身份和日志。

### 5. 权限与按群配置需求

- “按群独立配置”不只是新增配置项，而是权限模型调整。区分功能权限、配置权限、插件管理权限；遵循最小权限原则，避免用泛化“插件管理员”替代具体动作授权。
- 关键点：`plugin_admins`、`group_overrides`、`get_group_setting`、`title_admins`、`group_admin_admins`、`kick_admins`、`group_admins`，以及 `has_title_admin_rights`、`has_kick_admin_rights`、`has_group_admin_rights`。
- 评估按群配置时检查：是否已有全局项、按群覆盖读取、权限函数是否统一使用、命令是否操作正确层级、状态/帮助输出是否一致、`_conf_schema.json` 和 README 是否同步。
- 删除/废弃旧“按群插件管理”要考虑迁移、兼容读取、deprecated 过渡、命令语义变化和用户习惯。
- 风险：空列表是覆盖为空还是回退全局、超级管理员/群管理员继承、多群隔离、安全误授权、合法管理员失效、`group_admins` 与 `group_admin_admins` 命名混淆。

### 6. 配置 schema/UI 与禁言踢出阈值

- 按群配置 Issue 要分三层：业务读取是否走 `get_group_setting`；命令管理是否能写入/查看/清除 `group_overrides[group_id][key]`；配置 UI/schema/README 是否表达“全局默认 + 群级覆盖”。
- 对 `mute_kick_threshold`，若 `_record_mute_and_maybe_kick` 已用 `get_group_setting(group_id, "mute_kick_threshold", 0)`，核心逻辑可能已支持群级阈值，问题更可能在 `_conf_schema.json`、AstrBot 配置 UI、`config_cmd` 或 README 未暴露/解释群级覆盖。
- 顶层配置项存在不必然是 bug。保留全局默认值合理；schema 描述应改为“全局默认禁言踢出阈值，可被群级覆盖”，状态/配置展示显示“有效值 + 来源（群级覆盖/全局默认）”。不宜简单删除全局项。
- 需确认用户说“还在插件配置设置”是 AstrBot 控制台 UI，还是插件内 `/配置`/状态命令；两者修复路径不同。若框架 UI 不支持动态群号键，应通过 schema 描述、群级命令和 README 示例弥补。
- 覆盖语义重点：`0` 很可能表示关闭自动踢出，必须能显式覆盖全局值，不能被 `dict.get` 或假值判断误当成未配置回退；空值/缺失才回退全局。

### 7. 标签、标题与重复检测

- 标签优先贴合仓库现有体系；未知时给通用候选并注明需映射，不能留空。撤回类可候选 `bug, command, recall/message-recall, group-management, onebot, message-history`；配置类可候选 `bug, configuration, schema, group-config/per-group-config, ui/config-ui, documentation`。
- 标题无意义时必须改写，保留原始错误片段或具体对象。示例：`修复 count(int)=0 导致的命令参数类型错误`、`/撤回 @用户 N 被误解析为普通撤回命令`、`禁言踢出阈值未在按群配置中暴露`、`取消头衔命令提示成功但实际未清空群头衔`。
- 避免把推断写成事实。Issue 未明确命令来源/环境时，写“疑似/需确认”，并要求补充完整日志、触发命令、AstrBot 版本、插件版本、OneBot 实现、是否启动即报错。
- 重复检测不能只依赖标题。同样涉及 `/撤回` 不一定重复，需区分参数解析、撤回自身、按用户撤回入口、权限不足、数量错误、引用逻辑、API 不支持。只有症状、触发路径和修复点高度一致才判重复，否则标关联。
- 缺少历史列表时，“未检测到重复”只能写“暂未发现”。检索关键词：`count(int)=0`、`参数 count 类型错误`、`撤回指令本身`、`/撤回 1`、`/撤回 @用户`、`recall_cmd`、`recall_user_cmd`、`get_group_msg_history`、`取消头衔`、`special_title`、`duration`、`禁言阈值`、`mute_kick_threshold`、`group_overrides`。

### 8. 流程注意

- 结构化输出字段校验失败（如 milestone 单行、缺少 `<SUGGESTED_TITLE>`）只能局部降级，不能导致分类 `other`、标签置空、可行性“无法评估”。
- 信息不足的 Issue 仍应给出有条件可行性：说明需补证据，以及常见代码结构下的预估工作量与风险。
- 对“版本已更新仍存在”，要追踪最近相关 commit/PR：可能是修复方向错误、覆盖入口不全、插件目录/缓存未更新，不能仅重复原修复建议。
