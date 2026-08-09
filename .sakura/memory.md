# 项目记忆

累计反思 79 次

## 仓库背景

仓库 `mjy1113451/astrbot_plugin_gm` 是 AstrBot 群管理类插件，Issue/PR 常涉及命令解析、撤回、群管理权限、按群配置、OneBot 适配器兼容、配置 schema 与 README 同步。**高频模式**：权限模型重构（#130/#132）、引用消息触发型命令（#131 群待办）、撤回/STT/头衔/加群申请、装饰字符 QQ 解析（#134/#136）、解禁/解除禁言（#133）、禁言列表查询（#135 读类）、**/解禁 @装饰字符 误识别（#136）**——出现关键词即套对应模板。

- **"删除功能"类 Issue 不应自动归 medium**：维护者本人纯减法性质的功能裁剪 → low 组合（主动减法+owner 自实施+无横切关注点）。
- **`breaking-change` 应作为独立标签**：删除既有命令语法、修改既有命令参数语义、修改既有命令返回值、删除既有配置项都属 breaking change。
- **`recall_cmd` 是高频改动点**：撤回类 PR 多次出现，未来分析应优先关注 Path 分支完整性、对称性、本地缓存写入、帮助文本同步。
- **撤回类改动清单（五处→七处同步）**：main.py + README + 帮助 + schema + CHANGELOG；扩展再加 STT/转写配置 + 误伤率文档。
- **撤回类 PR 强制检查清单**：① `/撤回 1 3 5` 多编号与命令匹配器冲突 ② `after_message_sent` 钩子可用性 ③ 缓存并发/重启丢失/过期 ④ `retcode=1200` 跨适配器 ⑤ `batch_max_count` vs `max_message_history` ⑥ bot 权限校验（QQ 2 分钟）⑦ schema 一致性 ⑧ 旧配置/缓存升级兼容 ⑨ README+帮助+docstring 三处同步。
- **撤回缓存三层链路优先级**：`recent_messages`（旧）→ `message_history`（新）→ `get_group_msg_history`（OneBot 兜底）。
- **删减类 issue 检查清单**：调用点清空、帮助/README/docstring 同步、CHANGELOG/公告、剩余路径边界、用户迁移路径。
- **跨适配器读取类群成员字段差异矩阵（#135/#136 沉淀）**：`role`、`shut_up_timestamp`（NapCat/go-cqhttp）、`ban_expire_time`（Lagrange）、`mute_end_time`（部分实现）、`last_sent_time`、`join_time`、`level`、`special_title` 的跨实现差异矩阵已正式建立——所有"读群成员 X 字段"类 issue 必须先列该字段对照表。

### 头衔类 Issue 标准分析模板（#125 案例）

- **触发场景**：`/取消头衔 @用户` 提示成功但头衔仍存在。
- **必查项**：① Bot 在该群角色 ② 目标用户身份（是否群主）③ OneBot 实现版本 ④ AstrBot/插件版本与 commit ⑤ 完整执行日志 ⑥ 最近配置变更 ⑦ `_extract_at_qq` 解析 ⑧ `special_title` 传参（`""` vs `" "` vs 空白）⑨ `get_group_member_info` 回读。
- **必给标签**：`bug` + `command` + `group-management` + `title`/`special-title` + `onebot`/`compatibility` + `needs-info`（主分类 0.90+）。

### 装饰字符 QQ / 视觉欺骗型用户名 Issue 标准分析模板（#134/#136 案例，**高频解析类 bug 模式，已第 5-6 次触发校验失败短路**）

- **触发场景**：用户用花体字/数学字母/手写体/装饰 Unicode（如 `@𝓒𝓪𝓷𝓬𝓮𝓻` `@𝐀` `@𝕒`）等"看起来是 QQ"但实际是字符串的输入触发命令，导致 bot 误将字面量解析为 QQ 号。#136 是解禁场景（同根因），#134 是禁言场景。
- **触发关键词**：`@用户` + `解禁`/`禁言`/`踢人`/`设管`/`取管` + 装饰字符/数学字母/花写体/手写体/Emoji 风格。
- **必查项**：① `_extract_at_qq` 是否 NFKC/NFKD 归一化 ② OneBot 适配器是否对装饰字符 QQ 拒绝/截断 ③ 群号是否也被装饰字符污染 ④ 是否需在输入层加"QQ 必须是纯数字"硬校验 ⑤ 装饰字符 QQ 跨适配器命令成功率矩阵（NapCat/Lagrange/go-cqhttp × 数学字母/手写体/Emoji 风格）⑥ 完整执行日志 ⑦ `_extract_at_qq` 解析路径（必须按 segment/user_id，不按空格 split）⑧ 同类命令传染性（`/禁言` `/踢人` `/设管` `/取管` 都共享 `_extract_at_qq`，修复需同步）⑨ 多 `@` 取首个 vs 拒绝多目标的语义边界。
- **NFKC vs NFKD 技术细节（#136 沉淀关键盲区）**：装饰字符 Mathematical Alphanumeric Symbols（U+1D400-U+1D7FF）/ Enclosed Alphanumerics（U+2460-U+24FF）**不适用于 NFKC**——NFKC 仅能处理兼容性分解字符（全角数字 ０-９ → 0-9），**不会把花体字 𝓒𝓪𝓷𝓬𝓮𝓻 拆成 ASCII**。正确方案：①白名单 `\d{5,12}` 纯数字 ②NFKD + 自定义映射表 ③直接拒绝任何非纯数字输入并提示。**笼统说"加 NFKC 归一化"是错误技术建议**。
- **修复建议**：在 `_extract_at_qq` 顶部加白名单 `\d{5,12}` 强校验 + 错误提示"目标 QQ 格式不正确"。NFKC 只能作为辅助。
- **必给标签清单（必须逐项勾选，#136 曾遗漏 at-parse/unmute）**：`bug`(0.95) + `command`(0.95) + `parser`(0.85) + `at-parse`/`at-extract`(0.85, 仓库可新建) + `group-management`(0.80) + `onebot`(0.35-0.50) + `compatibility`(0.35-0.50) + `mute`/`unmute`/`mute-action`(0.85, 仓库可新建) + `unicode`/`unicode-normalization`(仓库可新建) + `input-validation`(仓库可新建) + `needs-info`(≤0.30 owner-driven 模板已沉淀)。
- **优先级**：`medium`（核心命令行为错误 + 误解禁比误禁言影响更严重，但单群单次未升 high）。#136 应在优先级章节显式做"误解禁 vs 误禁言"风险对比。
- **工作量**：小修复下限 1 天；含 3×4=12 个测试矩阵组合（NapCat/Lagrange/go-cqhttp × 数学字母/手写体/Emoji 风格）需 1.5-2 天。
- **同症状不同模块陷阱**：与 #125（头衔类）症状字符串都含"获取信息问题"，但根因模块完全不同——重复检测必须**按模块归类**而非按症状相似度，避免误报 #125。

### 解禁/解除禁言类 Issue 标准分析模板（#133 案例，与头衔类对等）

- **触发场景**：`/解禁 @用户` 提示成功但目标仍处于禁言状态。
- **必查项**：① Bot 在该群角色（部分协议要求群主专属解禁）② 目标用户是否仍在群内 ③ OneBot 实现版本（NapCat/Lagrange/go-cqhttp 对 `delete_group_ban` 语义差异）④ `duration` 参数语义（`duration=0` vs 不传 vs `duration=-1`）⑤ `_extract_at_qq` 解析 ⑥ `get_group_member_info` 回读校验（API 返回 ok ≠ 实际生效）⑦ 目标若已退群如何兜底 ⑧ 完整执行日志 ⑨ 最近配置变更。
- **必给标签**：`bug` + `command` + `group-management` + `unmute`/`lift-ban`/`mute-action`（仓库可新建）+ `onebot` + `compatibility` + `bot-role` + `needs-info`（0.85+，缺适配器版本/截图/目标身份是硬阻塞）。
- **优先级**：`medium`（核心解禁命令局部不可用 + 误判用户状态风险 + 跨适配器兼容风险已识别但有兜底）。
- **falsy 判空陷阱**：`duration` 参数必须用 `is None` 或 `== -1`，**严禁用 `if not duration`**——会把合法的 `0`（解除禁言）误判为未传。
- **可行性显式分支判定**：解禁类必须显式给分支A（API 层兼容，20-40 行/1 天）/分支B（补状态回读链路，50-100 行/1.5-2 天）/分支C（重构解禁入口或权限校验，100-150 行/2-3 天），禁止只给范围估算。
- **可行性分支**：分支A（API 层 `duration=0` 语义差异）~20-40 行/1 天；分支B（补完整状态回读链路）~50-100 行/1.5-2 天；分支C（重构解禁入口或权限校验）~100-150 行/2-3 天。
- **三层语义对应**（与禁言 3 层语义对称）：A. 解除群管 API 禁言（最常见，`set_group_ban` duration=0）；B. 解除"禁我"自怼状态；C. 解除审批工作流中"待审批禁言状态"。
- **建议标题**：`[bug][medium] /解禁 @用户 提示成功但未实际生效（禁言状态未解除）`，"疑似"措辞应去掉。

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

### 权限模型重构类 Issue 标准模板 v2（#130 + #132 案例，**仓库高频模式**）

- **触发关键词扫描**：`权限模型`、`plugin_admins`、`群管理员`、`群主`、`权限重构`、`/设管`、`/取管`、`sender.role`。出现任一关键词即触发本模板。
- **标签基线（必给）**：`enhancement`(0.95) + `breaking-change`(≥0.90) + `deprecation`(≥0.75) + `permission-model`(≥0.80) + `configuration`(0.85) + `group-management`(0.85) + `bot-role`/`sender-role`(≥0.70) + `onebot`/`compatibility`(≥0.65) + `needs-discussion`(0.75-0.85) + `needs-info`(≤0.45)。
- **优先级决策路径显式化**：① 横切重写+breaking-change → 最低 medium ② owner-driven+已有标准化模式 → 不升 high ③ 工作量可控+迁移路径明确 → 不升 high ④ 跨适配器风险已识别但有兜底 → 维持 medium。
- **工作量保守估算**：18+ 调用点 + 五处同步 + 迁移指南 + 测试验证 → 200-350 行、3-5 天（不要低估）。
- **权限提升风险审计必给具体示例**：至少列 2-3 个原本不该被群主执行的命令（如 `/踢人`、`/全员禁言`、`/改群名`），并建议"是否需保留 super-admin 概念"作为决策点。
- **同类配置项扫描**：`title_admins`/`group_admin_admins`/`kick_admins` 等是否一并迁移？避免分散实施。
- **维护者连续发起同类 Issue**（#130+#132）：应主动建议合并或互相引用，避免分散精力。
- **首次合并引用**：在"建议优先级"章节显式写"参 §权限模型重构模板 v2"作为决策依据。

### 引用消息触发型命令 / OneBot 群待办类 Issue 标准模板（#131 案例）

- **触发关键词**：群待办 / todo / 待办 / set_group_todo / _set_group_todo / 引用消息 + 群管理。
- **OneBot 协议分层警示（关键）**：群待办 API 在 OneBot v11 标准协议中**未定义**，属扩展能力。NapCat 提供 `_set_group_todo`，Lagrange 多不支持，go-cqhttp 需 HTTP API 插件扩展。**必须明确"非 v11 标准"**，否则误导实现者。
- **QQ 群待办 vs 群公告 语义区分**：群待办（`set_group_todo` 部分实现为 `set_group_notice`）与群公告（`set_group_announce`）是不同入口，插件需明确选型。
- **标签建议**：`command`(0.95) + `group-management`(0.85-0.92) + `enhancement`(0.95) + `onebot`(0.55) + `compatibility`/`onebot-extension`(0.75-0.85) + `permission`(0.40) + `configuration`(0.35)。建议仓库新增 `reply`/`quote-message`(0.85) + `bot-capability` + `onebot-extension` 标签。
- **owner-driven 标签校准**：`needs-info` ≤0.30（缺决策非信息）、`needs-discussion` 0.75-0.85（设计决策待定）、`help wanted` ≤0.1、`good first issue` ≤0.10（跨适配器差异+权限决策）。
- **必查项**：① API 标准性（v11 标准 vs 扩展）② bot/调用者权限（群主专属 vs 群管即可）③ `_get_reply_id` reply_id 解析与 None 校验 ④ 跨适配器支持矩阵 ⑤ 引用消息已撤回兜底 ⑥ 配置 schema 五处同步（含 CHANGELOG）。
- **API 返回 ok ≠ UI 生效**：QQ 客户端 UI 异步刷新，建议指令提示加"请打开群消息顶部查看（约 1-2 秒后生效）"。
- **配置 schema 默认值**：全局 enabled，按群 override 关闭为主（与现有 `group_overrides` 模式一致）。
- **典型误判警示**：与 `/设精` 表面同构（都是 reply_id+单 API），但 `/设精` 用 v11 标准 `set_essence_msg`，群待办用扩展 API——可行性差异巨大。

### 仓库"群管理动作新增"标准模板（#131/#135 复用）

1. 权限校验：`_is_group_admin_or_owner` + `is_plugin_admin`（注意群待办可能需群主专属）
2. 引用提取：`_get_reply_id(event)` + None 校验
3. 参数转换：`_execute_action` 已处理 group_id/user_id/message_id int
4. API 三段式：标准名 → 带下划线变体 → 降级提示
5. 失败回退：返回成功 ≠ UI 生效
6. 元组注册：`_GM_COMMAND_NAMES` 加入新指令名
7. 五处同步：main.py + schema + README + 帮助 + CHANGELOG

### 群管理动作模板 v2：写类 vs 读类细分（#131 + #135）

- **写类**（#131 群待办、禁言/解禁/头衔/踢人）：关注写权限、API 返回、UI 生效延迟、回执。
- **读类**（#135 禁言列表）：关注读权限、字段差异、数据脱敏、缓存策略、可见范围控制。
- **读类额外必查项**（#135）：① 大群分页/分批（`get_group_member_list` 在 500+ 人群是否分页）② 成员列表缓存策略与失效 ③ 空状态友好提示（"当前群无被禁言成员"）④ 时间格式显示边界（>30 天、永久）⑤ 隐私考虑（昵称+QQ号展示范围）⑥ **侦察工具风险**（是否需限制可见范围，可被滥用为成员名单泄露工具）。
- **读类命令标签基线**：`enhancement`(0.95) + `command`(0.95) + `group-management`(0.85) + `read-permission`/`viewer-role`(0.70-0.85, 新) + `mute`/`ban-list`(0.85, 新) + `mute-action`(0.80, 新) + `onebot`(0.65-0.70) + `compatibility`/`onebot-extension`(0.70-0.85) + `needs-discussion`(0.65-0.75) + `configuration`(0.65-0.75 若新增配置) + `needs-info`(≤0.30) + `help-wanted`(≤0.10) + `good-first-issue`(≤0.10)。
- **可行性分支显式判定**（#135 必须显式三档）：分支A 最小实现（~80-150 行，1.5-2 天）/ 分支B 完整实现（分页+缓存+脱敏+读权限分级+五处同步，~200-350 行，3-5 天）/ 分支C 与 #131 群待办合并实施（~300-500 行，5-7 天）。**禁止只给范围估算不显式分支**。
- **建议仓库新增 `mute`/`ban`/`ban-list`/`unmute`/`mute-action`/`read-permission`/`viewer-role` 标签子体系**：与 `title`、`recall`、`vote` 并列，便于禁言/读权限类 issue 检索。

## 反模式（最关键警示）

- **结构化输出校验失败 ≠ 信息不足**：看到 `expected <SUGGESTED_TITLE>` 等字段校验错误时，应**仅修复字段输出**（如把"无建议"改成实际建议），**不得把所有判断都退化为"无法评估"/`other`/空标签/无建议**。**字段校验失败仅触发输出修复，不得影响分类/可行性/标签/标题等实质性判断**。**Pre-check 规则**：在任何字段出现"无建议/无法评估/空/未检测到重复"前，必须先确认是否源于校验失败——校验失败应**局部修复**而非**整体降级**。**#135 已第 5 次整体降级，校验失败短路器必须升级为前置自检门槛**。
- **校验失败短路器（必须固化，已第 5-6 次触发 #131/#132/#133/#134/#135/#136）**：若反思摘要提及字段校验错误（如 `reserved tag syntax`/`expected <SUGGESTED_TITLE>`/`expected <REASON>`/`expected <LABEL>`），则只修复字段格式，**实质性判断（分类/优先级/标签/可行性/标题、重复检测）维持原始判断，不得连带退化**为 `other`/空标签/无建议。**反思指令硬约束**：字段校验错误仅触发输出修复，不得影响实质性判断。**执行优先级**：作为反思的**第一优先级自检项**，落笔前必须扫描。
- **重复检测措辞强制模板**：无历史列表时**写"暂未发现"并列出建议检索关键词**，"未检测到重复"/"无重复"/"可能是 #X 的重复"均被明令禁止。每次重复检测输出末加注"⚠️ 措辞核对：是否使用了禁用的'未检测到重复'/'无重复'/'可能是#X的重复'？"。**#134/#135/#136 三次连续触犯**，必须作为反思 checklist 必检项。
- **重复检测前置过滤**：若两 Issue 主分类不同（一个 bug 一个 enhancement），置信度上限 0.3，避免基于关键词表面相似度的误报（#132 曾误报 #125）。同类主分类（都是 enhancement）但 API 不同时置信度上限 0.30（#131 vs #135 案例）。
- **重复检测的"症状相似 ≠ 根因相似"陷阱**：#125（头衔）与 #134（禁言）都用"获取信息问题"作症状描述，但根因模块完全不同。下次遇到"获取信息问题"+"命令解析错误"模板时，**先按模块归类再判断重复**，不要按症状字符串相似度。
- **重复检测的"主分类+API"双过滤（#135 沉淀）**：#131（群待办）与 #135（禁言列表）主分类同是 enhancement 但 API 完全不同（`set_group_todo` vs `get_group_member_list`），不应机械按表面相似度标重复，置信度上限 0.30。
- **同类 Issue 显式互引**：同类/同工作量 issue 应在优先级章节显式对比说明一致性（如 #135 与 #131 群待办对比），避免读者横向对比产生质疑。**给出"与 §X 同级，因 Y 原因定 medium"的对比句**。
- **必给标签逐项核对（#136 沉淀）**：项目记忆模板给出"必给标签清单"时，**第一步必须对照清单逐项勾选**，不允许遗漏（#136 漏给 `at-parse`、`unmute`）。这是对装饰字符 QQ 模板的强制应用纪律。
- **可行性分支必须显式 A/B/C 三档**（#133/#135 沉淀硬约束）：禁止只给范围估算不显式分支。
- **优先级决策路径必须显式列出**（#133 沉淀硬约束）：4 条判定路径显式列出，让后续读者能追溯判定逻辑。
- **"quick"策略不能成为零审查的借口**：涉及权限/撤回/缓存等横切关注点的 PR，最低限度必须覆盖安全相关检查和结构性检查（schema 一致性、命令签名、关键风险点）。
- **PR 描述数字与实际 diff 不一致**需主动指出（如声称 +520/-103 实际 +494/-52）。
- **chore/reflection 批量 commit 污染提交历史**：多个相同信息的 chore commit 应在审查中标记为提交历史质量问题。增量审查时优先识别哪些是"有价值的代码变更"、哪些是"chore 噪音"。
- **`ast.parse` ≠ 真实加载**：PR 用 `ast.parse` 验证是错误认知，应替换为 `python -m py_compile main.py` 至少保证编译通过，最好有最小 AstrBot 启动验证。
- **记忆引用必须可溯源**：引用具体编号（如"§4.13"）前必须确认该编号存在；模糊记忆时用"参 §X 章节关于 Y 的讨论"而非编造编号/原文。
- **审查评分校准**：撤回/缓存核心命令回退路径 bug，无论代码量大小，影响面涉及「绝大多数未启用某配置的群组」时，评分上限不超过 5/10，决策应为 request_changes 或 comments。
- **owner-driven ≠ 无决策**（#135 沉淀）：维护者自实施不等于"无决策"。任何涉及"权限/字段差异/性能"的命令新增都至少有 2-3 个决策点，`needs-discussion` ≥ 0.65。
- **读权限 vs 写权限区分**（#135 沉淀）：本仓库 issue 多关注"谁能执行"（写权限），但"群管理列表查询"涉及"谁能查看"（读权限）。仓库标签体系若仅有 `permission`，应细化为 `write-permission` / `read-permission` / `viewer-role`。读权限可能被滥用为侦察工具，需评估可见范围。
- **标题字段**禁止写"无建议"；原标题已清晰应标"可保留"或给轻量规范化版。标题为空、"。"等无意义时必须改写。
- **标签在不确定体系时也应给通用候选并注明需映射**，**不能留空**；可行性在信息不足时也应有条件判断，不能写"无法评估"。

## Issue 分析经验

### 1. 分类、优先级、标签与标题

- 明确运行时报错、命令参数类型错误、用户反馈"更新后仍存在"时，主分类应为 `bug`；辅助 `command`、`parser`、`compatibility`、`needs-info`。
- 权限/配置粒度调整应归为 `enhancement`（不是 `other`）；辅助 `configuration`、`permission`、`group-management`、`needs-discussion`，移除旧机制需评估 `breaking-change`。
- `medium` 适用于核心命令局部不可用、权限配置影响多群但非阻断、群管理命令提示成功但实际未生效。插件启动失败、越权、误踢/误撤大量消息应考虑 `high`。
- 标题中 `[bug][medium]`、`[enhancement][medium]` 是信号但需结合正文和代码。涉及"禁言/禁我申请解禁"标题要覆盖两种状态；涉及批量撤回要覆盖普通与按用户两种形式；涉及删除命令用法标题要明确"删除"动作与具体被删路径。
- **`needs-info` vs `needs-discussion` 区别**：前者用于"缺关键事实才能评估"，后者用于"决策待定/方向冲突"。owner-driven issue 缺的是决策而非信息，应降 `needs-info` ≤0.2，`needs-discussion` 保持高权重。不要把"系统能力待确认"等同于 `needs-info` 高权重——此时 `needs-info` 0.35-0.50，`needs-discussion` 0.80+。
- **"good first issue"慎用**：仅适合"明确小重构/纯文档/小功能"；增强类涉及设计决策/兼容性时置信度 ≤0.15。
- **`help wanted` 对 owner-driven self-implementation 几乎不适用**：维护者本人提交 + 改法明确 + 工作量小时置信度 ≤0.1。
- **行号引用必须可溯源**：精确行号若无"已读取 main.py 验证"说明，会让读者怀疑是猜测；要么读取验证，要么用"约 L2000-2060"等模糊表述。建议在可行性章节开头明示"以下行号基于项目记忆与既有 PR 模式推断，PR 实际编写时以最新 main.py 行号为准"。
- **同期并行 Issue 方向冲突要纳入优先级判定**：扫描同期相关 Issue 是否方向冲突，冲突则升级 `needs-discussion` 高权重。
- **语音/STT/语音违规检测类 Issue 标准标签**：`enhancement` + `stt`/`voice`（核心模块标签，仓库若未建立应主动建议）+ `moderation` + `recall` + `profanity` + `configuration` + `permission` + `onebot`/`compatibility` + `privacy` + `needs-discussion` 高权重 + `needs-info` ≤0.45。
- **小型修复工作量下限**（#134 沉淀）：对"小修复"（<50 行）也要避免低估为 1 天内——装饰字符 QQ 测试矩阵（NapCat/Lagrange/go-cqhttp × 数学字母/手写体/Emoji 风格）至少需要半天构造测试用例。建议小修复工作量下限 1 天，包含最小适配器验证。
- **可行性分支显式判定**（#133 沉淀）：可行性章节必须显式分支判定（分支A/B/C），不要只给范围估算。
- **优先级决策路径显式列出**（#133 沉淀）：优先级决策路径必须在分析中显式列出（4 条判定路径），让后续读者能追溯判定逻辑。

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
