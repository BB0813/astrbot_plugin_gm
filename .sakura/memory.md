# 项目记忆

累计反思 22 次

## 仓库背景

仓库 `mjy1113451/astrbot_plugin_gm` 是 AstrBot 群管理类插件，Issue/PR 常涉及命令解析、撤回、群管理权限、按群配置、OneBot 适配器兼容、配置 schema 与 README 同步。Issue 中可能出现旧插件名或相近插件名（如 `astrbot_plugin_group_admin`），分析时需确认与当前仓库/插件注册名是否一致，避免把推断写成事实。

## Issue 分析经验

### 1. 分类、优先级、标签与标题

- 明确运行时报错、命令参数类型错误、用户反馈“更新后仍存在”时，主分类应为 `bug`；若是命令参数解析，可辅助 `command`、`parser`、`compatibility`、`needs-info`。
- 权限/配置粒度调整（如头衔、管理、踢人权限按群独立配置）应归为 `enhancement`，不是 `other`；辅助 `configuration`、`permission`、`group-management`、`needs-discussion`，若移除旧机制需评估 `breaking-change`。
- `/撤回 N` 或 `/撤回 @用户 N` 因 OneBot 不支持 `get_group_msg_history` 而不可用时，核心是 `compatibility`：若请求增加本地缓存/回退，通常为 `enhancement + medium`；若只是询问提示含义/能力限制，可为 `question` 或 `documentation + low`；若文档承诺通用支持而常见环境不可用，也可视为兼容性 bug。
- `medium` 适用于核心命令局部不可用、权限配置影响多群但非阻断、群管理命令提示成功但实际未生效。插件启动/加载失败、导入失败、装饰器注册失败、越权、误踢/误撤大量消息等应考虑 `high`。
- 标题中 `[bug][medium]`、`[enhancement][medium]` 是信号但需结合正文和代码。标题为空、“。”等无意义时必须改写；标题字段不能写“无建议”。若原标题已清晰，应写“可保留”或给轻量规范化版。
- 标签推荐要贴合模块和根因；未知标签体系时也应给通用候选并注明需映射，不能留空。撤回历史接口类常用：`enhancement`/`question`/`documentation`、`compatibility`、`command`、`recall`、`message-history`、`onebot`、`group-management`、`needs-info`。
- 不应因结构化输出字段校验失败，就把分类降为 `other`、标签置空、可行性写“无法评估”、标题写“无建议”。格式失败应局部修复，保留可判断信息。

### 2. AstrBot 命令参数与撤回逻辑

- 对 `@filter.command(...)` 命令，必须区分错误发生在启动/插件加载/命令注册阶段，还是用户调用后的业务函数阶段。若 AstrBot 根据函数注解提前转换参数，函数体内 `try/except int(count)` 无法兜底；复杂语法入口优先用字符串/原始事件解析。
- 遇到 `参数 count 类型错误`、`count(int)=0` 等，应优先检查命令函数签名、类型注解和默认值（如 `count: int = 0/1`），并确认触发命令、堆栈、AstrBot 版本、插件版本/commit、旧缓存。
- 修复方向通常是命令入口用 `str`/可选原始参数接收，内部统一转换、校验并给友好提示，同时明确 `0`、空字符串、`None`、负数、过大值等边界。
- `/撤回 N` 应理解为撤回“当前命令之前的 N 条消息”，不能优先撤回命令自身；`count=1` 是最小必测。历史或缓存结果都必须排除当前 `event.message_id`，注意消息 ID 类型、正/倒序、消息不足、超时/权限不足。
- 撤回类要区分：参数解析问题、业务语义问题（撤回上一条还是命令自身）、历史接口问题（`get_group_msg_history` 不支持/返回结构差异）、引用撤回、按用户撤回。
- `/撤回 @用户 N` 与 `/撤回用户 @用户 N` 要区分“功能缺失、入口未路由、参数解析失败、文档/提示不清”。若已有 `recall_user_cmd`、`_extract_at_qq` 等，修复宜抽取共享 helper，避免复制分叉。`@用户` 解析应基于消息 segment/user_id/At 对象，不要按昵称文本或空格 split。
- 非引用撤回依赖消息来源：普通 `/撤回 N` 需要最近群历史；`/撤回 @用户 N` 还要按 `user_id` 过滤。`get_group_msg_history` 返回空不一定等于“不支持”，也可能是参数、权限、数量不足、返回结构或适配器行为差异，应谨慎提示。
- 历史接口不可用时，引用撤回只是短期替代提示，不等于真正 fallback。若实现插件侧缓存，需按群维护最近消息元数据（尽量只存 `message_id`、群号、发送者、时间/顺序，避免缓存完整内容），设置上限/过期，处理重启丢失、在线后才可用、并发顺序、多群隔离、当前命令过滤、message_id 类型、撤回时限、bot 权限和隐私边界。工作量通常中等。
- 撤回命令测试覆盖：`/撤回`、`/撤回 1`、`/撤回 @用户 1`、`/撤回用户 @用户 1`、引用撤回、无/非法/负数/0/过大数量、多个 @、非群聊、bot 权限不足、历史消息不足/接口不可用/返回结构差异、本地缓存不足或重启后缓存缺失。

### 3. 权限、群管理 API 与按群配置

- “按群独立配置”通常是权限模型调整。需区分功能权限、配置权限、插件管理权限；遵循最小权限原则，避免用泛化“插件管理员”替代具体动作授权。
- 关键点包括：`plugin_admins`、`group_overrides`、`get_group_setting`、`title_admins`、`group_admin_admins`、`kick_admins`、`group_admins`，以及 `has_title_admin_rights`、`has_kick_admin_rights`、`has_group_admin_rights` 等。
- 按群配置要看三层：业务读取层是否统一走 `get_group_setting`；命令管理层是否正确写入/查看/清除 `group_overrides[group_id][key]`；配置 UI/schema/README 是否表达“全局默认 + 群级覆盖”。Schema/UI 问题也可能是 bug。
- 顶层配置项可能是全局默认，不一定是 bug。更稳妥做法是保留全局默认，在 `_conf_schema.json` 和 README 标注可被群级覆盖；状态展示应显示“有效值 + 来源 + 全局默认值”。动态群号键若受 AstrBot UI 限制，至少用说明和示例弥补。
- 配置边界：`0` 可能表示关闭且必须能覆盖全局，不能被 `dict.get`/假值判断误当缺失；空列表是覆盖为空还是回退全局，`None`、缺失 key、空字符串要区分；旧配置迁移和兼容读取不能忽略。
- 群管理 API “返回成功但实际未生效”（取消头衔、设管理员、踢人/禁言、改群名片等）按链路排查：命令解析 → 权限判断 → API 参数 → 适配器兼容 → API 返回值 → 状态回读 → 用户提示。OneBot/NapCat/Lagrange/go-cqhttp 对 `special_title=""`、`duration=-1/0/不传`、返回值和缓存刷新语义可能不同。
- `/取消头衔` 等不能仅根据 action 返回值提示成功；需考虑机器人是否管理员/群主、权限是否高于目标、目标是否群主、QQ 限制、客户端缓存/延迟。可用 `get_group_member_info` 回读确认，但提示回读也可能受缓存和字段差异影响。
- 权限类改动必须测试：全局配置、按群覆盖、未配置回退、空列表/0 覆盖、多群隔离、普通用户不得获得踢人/管理/头衔权限、旧配置升级后行为。

### 4. PR/代码审查经验

- 加载级问题（`SyntaxError`、导入失败、装饰器注册失败）影响高，即使改动小也应高优先级审查。建议至少要求 `python -m py_compile main.py`、`python -m compileall .` 或最小 AstrBot 插件加载验证。
- `async def` 中一旦出现 `yield` 就变为 async generator，不能 `return <value>`，也不能按普通 coroutine `await func()` 获取返回值。被调用方以 `await func(...)` 获取业务值的 helper，函数体内不得出现 `yield`。
- 命令 handler 与普通 helper 的响应方式要区分：顶层 AstrBot 命令 handler 可使用 `yield event.plain_result(...)`；普通 helper 如需发送消息，优先统一调用 `_send`；返回 `True/False` 的 `require_*` 权限 helper 不应使用 `yield`。
- 审查从 `yield event.plain_result(...)` 改为 `await self._send(...)` 时，不能只确认语法消失，还要验证行为等价：事件类型支持、是否真的发送、异常处理、响应时机、与 handler 调用链兼容。
- 对集中式权限 helper（如 `_moderation_require_admin_msg`）要抽样所有调用语义：成功返回 `True`，失败发送提示并返回 `False`，调用点 `if not await ...: return` 短路正确；若有 18 处调用点，影响面广，不宜只看单点。
- 针对此仓库固定搜索 async generator 风险：搜索 `async def`、`yield`、同一函数内 `return <非空值>`、所有被 `await` 的 helper 是否误变 async generator。不要完全依赖 PR 描述的 AST 扫描，应抽查或验证。
- approve 可以，但若缺少真实 AstrBot 加载和命令验证，尤其涉及框架消息发送方式变化，评分不宜给满分；可评为“修复方向正确、风险较低，但建议补充加载与无权限命令测试”。

### 5. 重复检测与流程注意

- 重复检测不能只依赖标题。参数错误搜：`count(int)=0`、`参数 count 类型错误`、`撤回`、`recall_cmd`、`recall_user_cmd`、`filter.command`。撤回自身搜：`/撤回 1`、`撤回指令本身`、`上一条消息`、`get_group_msg_history`、`message_id`。
- 历史接口/兼容性搜：`get_group_msg_history`、`group_msg_history`、`消息历史`、`当前 OneBot 实现不支持`、`引用消息撤回`、`按用户撤回`、`@用户`、`message-history`、`delete_msg`。
- 按群权限/配置搜：`按群配置`、`群独立`、`权限`、`踢人`、`管理`、`头衔`、`禁言阈值`、`mute_kick_threshold`、`group_overrides`、`group_admins`、`配置显示`；头衔问题搜：`取消头衔`、`special_title`、`set_group_special_title`、`duration`、`NapCat`、`成功但没生效`。
- “未检测到重复”在缺少历史 Issue 列表时只能写“暂未发现”，并列出建议检索关键词；同命令/同模块但症状、触发路径、修复点不同的 Issue 应标关联而非重复。
- 对信息不足的 Issue，仍应给有条件的可行性判断：说明需要补充哪些证据，以及常见代码结构下的预估工作量与风险。
- 对“版本已更新仍存在”的问题，应追踪最近相关 commit/PR：可能是修复方向错误、覆盖入口不全、插件目录/缓存未更新，不能仅重复原修复建议。
