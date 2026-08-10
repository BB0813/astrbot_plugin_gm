# 项目记忆

累计反思 98 次

## 仓库背景

`mjy1113451/astrbot_plugin_gm` 是 AstrBot 群管理插件。**5 种高频模式已沉淀**：①权限模型重构（#130/#132/#139）②引用消息触发型命令（#131 群待办）③装饰字符 QQ 解析（#134/#136）④举报/通知路由（#140）⑤**动作联动型（#143 kick→clear-history）/撤回增强类（#142）/owner-driven 命令删除（#141）三类延伸**。出现关键词即套对应模板。

- **"删除功能"类 Issue 不应自动归 medium**：维护者本人纯减法 → low 组合（主动减法+owner 自实施+无横切关注点）。
- **`breaking-change` 独立标签**：删命令/改命令参数语义/改返回值/删配置项。
- **`recall_cmd` 高频改动点**：撤回类优先关注 Path 分支完整性、对称性、缓存写入、帮助文本同步。
- **撤回缓存三层链路**：`recent_messages` → `message_history` → `get_group_msg_history` 兜底。
- **跨适配器读取类群成员字段差异矩阵**（#135/#136 沉淀）：`role`、`shut_up_timestamp`/`ban_expire_time`/`mute_end_time` 等差异矩阵已建立——"读群成员 X 字段"类必先列对照表。

## 命令集重构 / 双向复合改动模板（#139 案例）

- **触发**："删除命令 A + 新增命令 B"复合诉求（典型对称对：add/remove、enable/disable、set/unset、start/stop、bind/unbind）。
- **拆分纪律**：两条诉求工作量/风险/决策点完全不同，**分析必须显式建议拆分为两个独立 Issue 跟踪**。
- **可行性分支 A/B/C + D（分阶段先 A 后 B）**：必显式四档。
- **分支A 必含七处同步**：main.py + `_GM_COMMAND_NAMES` + README + 帮助 + CHANGELOG/迁移指南 + metadata.yaml + 公告。
- **分支B 工作量 ≈ 1.2-1.5× 同方向既有 Issue**（参考 #131）。
- **breaking-change 子诉求分别评估置信度**：删除侧 0.90-0.95，新增侧 ≤0.30。
- **对称命令权限不对称风险**：撤销群待办通常需群主（QQ 原生），与添加侧群管权限不对称。
- **撤销类 vs 设精类差异表**：群待办 API 非 v11 标准、跨适配器差异更大、UI 异步刷新、reply_id 必要性更高。
- **CHANGELOG breaking-change 标注格式**：分 Breaking Changes / Added 两节明确。

## 举报/通知路由类 Issue 标准模板（#140 案例，**新沉淀，仓库第 4 种角色相关模式**）

- **触发场景**：`/举报`/告警类命令按举报人/被举报人角色分级路由通知；典型"举报 A→通知 X、举报 B→通知 Y、群主豁免"。
- **与权限模型重构差异**：#130 是全局权限模型替换（plugin_admins → 群原生），本模式是**单命令内通知路由分支**（保持现有权限模型，只改路由）。
- **必查项**：①举报人/被举报人角色获取 API 跨适配器差异（继承 #135/#136 矩阵）②扇出性能（500 人群群管+群主 × 每举报）③通知风暴 ④bot 自身被举报兜底 ⑤群主豁免检测 ⑥通知留痕 ⑦恶意互刷防护 ⑧隐私脱敏 ⑨举报记录入库语义 ⑩匿名 vs 实名。
- **权限矩阵 9 组合**：触发者 {群主,群管,普通成员} × 被举报者 {群员,群管,群主}。
- **必给标签**：`enhancement`(0.95) + `command`(0.95) + `permission-model`(0.80-0.85) + `notify`/`notification-routing`(0.80-0.85, 仓库新建) + `report`/`reporting`(0.85, 仓库新建) + `bot-role`/`sender-role`(0.70-0.80) + `group-management`(0.85-0.92) + `breaking-change`(0.65-0.75) + `onebot`/`compatibility`(0.55-0.70) + `configuration`(0.50-0.65) + `needs-discussion`(0.80-0.85) + `needs-info`(≤0.30)。
- **优先级**：`medium`（横切权限但有兜底，群主豁免 = 静默失败而非越权）。
- **可行性分支**：A 最小 40-80 行/0.5-1 天 / B 完整 120-200 行/2-3 天 / C 完整+跨适配器回读 200-300 行/3-5 天 / D 分阶段 250-400 行/4-5 天。
- **配置 schema 建议**：`report_enabled` / `report_notification_targets` / `report_cooldown_seconds` / `report_privacy_redact` / `report_max_per_user_per_day` / `report_allow_report_owner`(是否允许举报群主)。
- **优先级决策路径 4 条显式**：①横切权限 + breaking-change → 最低 medium ②owner-driven + 已标准化模式 → 不升 high ③工作量可控 + 迁移路径明确 → 不升 high ④跨适配器风险已识别但有降级 → 维持 medium。
- **标题范式**：`[enhancement][medium] /举报 命令按举报人/被举报人角色分级路由通知（群主豁免）` 或含"全员开放"关键信号。

## 装饰字符 QQ / 视觉欺骗型用户名模板（#134/#136 高频解析类 bug，#139/#140 多次触犯）

- **必查项**：① `_extract_at_qq` 是否 NFKC/NFKD 归一化 ② OneBot 适配器是否对装饰字符 QQ 拒绝/截断 ③ 群号是否也被装饰字符污染 ④ 是否需在输入层加"QQ 必须是纯数字"硬校验 ⑤ 装饰字符 QQ 跨适配器命令成功率矩阵 ⑥ 完整执行日志 ⑦ `_extract_at_qq` 解析路径（必须按 segment/user_id，不按空格 split）⑧ 同类命令传染性 ⑨ 多 `@` 取首个 vs 拒绝多目标的语义边界。
- **NFKC vs NFKD 技术细节**：Mathematical Alphanumeric Symbols（U+1D400-U+1D7FF）/ Enclosed Alphanumerics（U+2460-U+24FF）**不适用于 NFKC**——NFKC 仅处理全角数字。**笼统说"加 NFKC 归一化"是错误技术建议**。正确方案：①白名单 `\d{5,12}` 纯数字 ②NFKD + 自定义映射表 ③直接拒绝非纯数字。
- **修复建议**：在 `_extract_at_qq` 顶部加白名单 `\d{5,12}` 强校验 + 错误提示。
- **必给标签**：`bug`(0.95) + `command`(0.95) + `parser`(0.85) + `at-parse`(0.85) + `group-management`(0.80) + `onebot`(0.35-0.50) + `compatibility`(0.35-0.50) + `mute`/`unmute`(0.85) + `unicode-normalization`(新建) + `input-validation`(新建) + `needs-info`(≤0.30)。
- **优先级**：`medium`，**显式做"误解禁 vs 误禁言"风险对比**。

## 动作联动型 Issue 模板（#143 新沉淀 · 仓库第 5 种模式）

- **触发场景**：动作 A 成功后自动触发动作 B（kick→clear-history / ban→notify / mute→log），A 与 B 共享配置与权限。
- **必查 10 项**：①回执一致性（B 部分失败时 A 状态如何回执）②通知风暴（B 触发群内撤回提示是否影响体验）③限流策略（B 高成本 API 调用如何分批）④配置粒度（可关闭/可调上限/按群覆盖）⑤权限双校验（A/B 各自权限对齐 + bot 自身权限边界）⑥时间窗约束（OneBot 2 分钟）⑦跨适配器差异矩阵 ⑧本地缓存兜底 ⑨可观测性（成功 N/M、跳过 X、失败 Y 分类回执）⑩去重（本地缓存 vs 服务端历史 message_id）。
- **必给标签**：`enhancement`(0.95) + `command`(0.85) + `configuration`(0.80) + `group-management`(0.90, #140 硬约束) + 对应动作标签如 `recall`(0.85) + `permission`(0.80) + `message-history`(0.75) 或对应数据源 + `onebot`(0.85) + `compatibility`(0.75) + `external-reference`(0.85, 参考外部仓库时) + `needs-discussion`(0.80) + `needs-info`(≤0.30, #140 双校准硬约束)。
- **优先级**：`medium`（默认关闭 + owner-driven + 工作量可控 + 风险有兜底）。
- **可行性分支**：A 最小 / B 完整 / C 完整+跨适配器回读 / D 分阶段（先 A 后 B/C）。
- **工作量下限**：涉及"本地缓存+协议兜底+配置 schema+指令入口"4 件套的 A 分支**至少 1 天**起步。
- **红旗**："owner + 清除他人数据"必须显式评估滥用风险/合规风险/不可逆性。

## 撤回增强类延伸模板（#142 沉淀）

- **触发场景**：`/踢` 后按配置自动/手动批量撤回被踢用户本群全部历史。
- **必查 10 项**：①OneBot `get_group_msg_history` 跨适配器最大返回差异 ②`delete_msg` 限速差异 ③2 分钟撤回时限逐条检测 ④PR #123 缓存骨架的容量/重启语义 ⑤自身消息排除（早退前写入）⑥业务早退吞噬共享逻辑规避 ⑦跨群隔离 vs 共享 ⑧"全量"语义 README 诚实告知 ⑨节流方案（全局 sleep vs 令牌桶）⑩`group_overrides` 嵌套结构与生效顺序。
- **必给标签**：`enhancement`(0.95) + `recall`(0.95) + `command`(0.95) + `message-history`(0.90) + `group-management`(0.88) + `configuration`(0.85) + `onebot`(0.80-0.85) + `onebot-extension`(0.55-0.65) + `throttling`/`pagination`/`partial-failure`(新建) + `needs-discussion`(0.85) + `needs-info`(≤0.30) + `breaking-change`(0.30-0.40 默认 false 时)。
- **核心区分**：撤回 ≠ 清除（对其他群员仍可见撤回提示）；维护者命令触发 vs 任意踢出事件触发（后者需订阅 OneBot `notice`）。
- **OneBot notice 事件跨适配器字段差异矩阵待沉淀**（`sub_type`/`event`/`notice_type` 命名差异）。
- **工作量估算**：A 80-150 行/1.5-2.5 天 → 实际 120-200 行/2-3 天（被低估）。

## owner-driven 命令删除类模板（#141 沉淀）

- **触发**：维护者自提删除既有对外命令契约（区别于 #138 重命名 = 保留能力）。
- **关键边界**：纯内部清理才适用 `low`；对外可见命令删除应保留 `medium`（教程/脚本/外部依赖）。
- **必查 6 项**：①是否被其他命令依赖（grep 调用点）②用户依赖度（文档/教程/外部脚本）③跨适配器历史问题（删除动机）④替代方案需求评估 ⑤迁移路径 ⑥公告发布。
- **必给标签**：`enhancement`(0.95) + `command`(0.95) + `breaking-change`(0.90) + `cleanup`/`removal`(0.80) + `documentation`(0.85) + `needs-discussion`(0.80) + `migration`(分支 B/C 时)。
- **可行性分支**：A 硬删 / B 删+引导 / C 删+替换 / D 分阶段。
- **跨 Issue 互引硬约束**：同类反复失败 Issue（#111/#119/#125）应在可行性章节**显式互引**，强化删除动机论证。
- **`deprecation` 标签语义边界**：仅"标记废弃但保留过渡期"时使用；A 分支硬删不应给。
- **`onebot` 标签语义边界**（#141 沉淀）：实际调用或修改 OneBot API 时使用；纯文档/纯内部清理/删除不涉及新 API 调用 ≤0.35 或删除。

## breaking-change 置信度 4 档精细化（#142 新增）

| 情形 | 置信度 |
|------|--------|
| 新增配置项 + 默认 false/缺省 | ≤0.30 |
| 新增配置项 + 默认 true（silent behavior change） | 0.55-0.65 |
| 修改既有配置项默认值 | 0.70-0.80 |
| 删除既有配置项/命令 | 0.90-0.95 |

## 优先级决策路径 5 条（#142 升级为 5 条）

1. 横切权限 + breaking-change → 最低 medium
2. owner-driven + 已标准化模式 → 不升 high
3. 工作量可控 + 迁移路径明确 → 不升 high
4. 跨适配器风险已识别但有兜底 → 维持 medium
5. **默认值决策（默认 false → 维持；默认 true → 升 high/silent behavior change）**

## 跨 Issue 决策路径同构显式互引规则（#142 新沉淀）

当两个 Issue 决策路径同构时（如 #142 与 #140），应在优先级章节显式互引："本 Issue 与 #X 决策路径同构（...），维持同优先级。"

## `message_history` 本地缓存应用通用提示模板（#143 沉淀）

PR #123 引入的本地缓存至今应用于自动撤回、踢人清除等多个场景。**必须在 README/帮助统一明示**："本地缓存仅进程内有效，重启丢失；服务端撤回受 2 分钟时间窗限制。"

## 反模式（最关键警示，#141/#142/#143 第 10 次触发）

- **结构化输出校验失败 ≠ 信息不足**：字段校验失败应**仅修复字段输出**，**不得把所有判断退化为"无法评估"/`other`/空标签/无建议**。**校验失败仅触发输出修复，不得影响实质性判断**。**Pre-check 规则**：任何字段出现"无建议/无法评估/空/未检测到重复"前，必须先确认是否源于校验失败——校验失败应**局部修复**而非**整体降级**。**#140 第 9-10 次整体降级，校验失败短路器必须升级为前置自检门槛第一优先级**。
- **校验失败短路器（已第 10+ 次触发 #131-#143）**：若反思摘要提及字段校验错误，**实质性判断维持原始判断，不得连带退化**。**作为反思第一优先级自检项**，落笔前必须扫描。
- **重复检测措辞强制模板（第 10 次触发 #141/#142/#143）**：无历史列表时**写"暂未发现"并列出建议检索关键词**，"未检测到重复"/"无重复"/"可能是 #X 的重复"均被明令禁止。每次重复检测输出末加注"⚠️ 措辞核对"。**已升级为前置第一优先级自检门槛**——每个 Issue 分析第一步加"重复检测措辞预检"。
- **删除既有命令 + 新增对称命令复合诉求必须显式建议拆分**（#139 硬约束）：禁止混合 PR。
- **breaking-change 子诉求必须分别评估置信度**（#139 硬约束）：删除侧 0.90-0.95，新增侧 ≤0.30。
- **七处同步清单对"删除既有命令"强制适用**（#139 硬约束）：纯减法也不能跳过。
- **owner-driven 纯减法应主动降 `low`**（#130/#132/#138 硬约束）：必须在优先级章节显式说明"为何维持 medium / 降 low"。
- **重复检测前置过滤**：主分类不同 → 上限 0.3；主分类同但 API 不同 → 上限 0.30。
- **"症状相似 ≠ 根因相似"陷阱**：先按模块归类再判断重复。
- **同类 Issue 显式互引**：在优先级章节对比说明"与 §X 同级，因 Y 原因定 medium"。
- **必给标签逐项核对**（#136 硬约束）：模板给清单时**第一步逐项勾选**，不允许遗漏（#136 漏 `at-parse`/`unmute`；#139 漏 `onebot-extension`/`reply`；#140 漏 `bot-role`/`notification`）。
- **可行性分支必须显式 A/B/C（#139 加 D 分阶段）**（#133/#135/#139 硬约束）：禁止只给范围估算。
- **优先级决策路径必须显式列出 4 条**（#133 硬约束）：让后续读者能追溯判定逻辑。
- **项目记忆模板对齐检查**（#136/#139/#140 沉淀）：装饰字符/@解析/禁言类/群待办/举报类 Issue，**第一步必须对照模板逐项勾选**。
- **`ast.parse` ≠ 真实加载**：应用 `python -m py_compile` 至少保证编译通过。
- **记忆引用必须可溯源**：模糊记忆用"参 §X 章节关于 Y 的讨论"而非编造编号。
- **审查评分校准**：撤回/缓存核心命令回退路径 bug，影响面涉及"绝大多数未启用配置的群组"时，评分上限不超过 5/10。
- **owner-driven ≠ 无决策**（#135/#140 沉淀）：涉及权限/字段差异/性能的命令新增都有 2-3+ 决策点，`needs-discussion` ≥ 0.65-0.85。
- **标签误标识别**（#138 沉淀）：`parser` 仅在 `_extract_at_qq`/`_get_reply_id`/装饰字符场景；`recall` 仅在撤回场景。两者均不涉及应**删除**。
- **标题字段禁止"无建议"**：清晰原标题应标"可保留"或给轻量规范化版。"。"等无意义标题必须改写。
- **标签在不确定体系时也应给通用候选并注明需映射，不能留空**；可行性在信息不足时也应有条件判断。
- **#140+#142+#143 新增红旗**：`needs-info` ≤0.30 与 `needs-discussion` ≥0.80 双校准对 owner-driven Issue 必同时满足；涉及 bot/被操作者角色查询时 `bot-role` 必给；OneBot API 查询/调用时 `onebot`/`compatibility` 必给（≥0.55）；`group-management` ≥0.85 对群管理命令硬约束；动作联动型/撤回类/参考外部仓库时分别必给 `message-history`/`onebot-extension`/`external-reference`。
- **新建标签置信度上限**（#142 沉淀）：仓库新标签首次使用建议 ≤0.75，避免误导后续检索（如 `message-history` 0.82 偏高应 0.65-0.75）。
- **`breaking-change` 评估对 owner-driven 默认值必查**（#142）：默认 false → 维持；默认 true → silent behavior change 升 0.55-0.65。

## Issue 分析经验

### 分类、优先级、标签与标题
- 运行时报错/参数错误/`更新后仍存在`→ `bug`；权限/配置粒度调整→ `enhancement`；移除旧机制→评估 `breaking-change`。
- `medium`：核心命令局部不可用/权限影响多群但非阻断/提示成功但未生效；启动失败/越权/误踢/误撤→ `high`。
- 标题 `[bug][medium]`、`[enhancement][medium]` 是信号但需结合正文。
- **"`needs-info` vs `needs-discussion` 双校准**：缺关键事实 vs 决策待定/方向冲突；owner-driven 缺决策非信息 → `needs-info` ≤0.30，`needs-discussion` ≥0.75-0.85。
- **"全员可 X"是重大权限变更信号**：必须在优先级章节显式对比"原本谁能做 vs 现在谁能做"，并评估恶意滥用风险。
- **通知类命令三要素**：通道（私聊/群内）+ 对象（哪些 QQ）+ 形式（@全体/单发/群待办）。
- **行号引用**：无"已读取验证"说明则用"约 L2000-2060"模糊表述。
- **同期并行 Issue 方向冲突**：升级 `needs-discussion` 高权重。
- **小型修复工作量下限 1 天**（#134 沉淀）。
- **可行性分支显式 A/B/C（#139 加 D）**（#133/#135/#139 硬约束）。
- **优先级决策路径 4 条显式**（#133 硬约束）。

### AstrBot 命令参数与撤回逻辑
- `@filter.command(...)` 必须区分启动 vs 运行；AstrBot 提前转换参数，函数体内 `try/except int(count)` 无法兜底；复杂语法入口优先字符串/原始事件解析。
- `/撤回 N` = 撤回当前命令之前 N 条，不能撤回命令自身；`count=1` 最小必测；排除 `event.message_id`。
- **本地缓存撤回模式骨架**：①按群隔离 ②`message_id+user_id` ③deque maxlen ④写入入口对称 ⑤回退标识 ⑥文档明示重启不可恢复 ⑦写入失败 try/except+debug ⑧提示语区分。
- **早退语句吞噬共享逻辑**：基础设施写入必须置于业务早退**之前**。
- **注释即承诺**：注释与代码不符都标记。
- **`defaultdict(factory)` 陷阱**：`.get()` 安全，但 `if k in d`/`dict(d)`/`copy.copy(d)`/`json.dumps` 会无差别创建空条目。**推荐 `{}` + 显式 `setdefault(key, factory())`**。
- **falsy 判空陷阱**：`duration` 必须 `is None`/`== -1`，严禁 `if not duration`（#133 沉淀）。
- **`async def` 中 `yield` 即变 async generator**，不能 `return <value>`/`await func()`。

### 权限、群管理 API 与按群配置
- "按群独立配置"是权限模型调整，区分功能/配置/插件管理权限，遵循最小权限。
- 关键：`plugin_admins`/`group_overrides`/`title_admins`/`group_admin_admins`/`kick_admins` 及 `has_*_admin_rights` helper。
- **"返回成功但未生效"链路**：命令解析→权限判断→API 参数→适配器兼容→返回值→**状态回读**→用户提示。
- 头衔清空严格区分 `""`/`" "`/空白/`None`；`strip()` 会把空格头衔误判为已清空。
- **"禁言/禁我"3 层语义**：①群管 API 禁言 ②"禁我"自怼 ③申请解禁工作流"待审批"。

### PR/代码审查经验
- **增量审查先识别"有价值的代码变更"与"chore 噪音"**；不能仅看新增 commit 而忽略被改动的接口。
- 命令 handler 可 `yield event.plain_result(...)`；普通 helper 统一 `_send`。
- 集中权限 helper 抽样所有调用：成功 `True`，失败发送提示并 `False`。
- **PR 描述数字与实际 diff 不一致**需主动指出。
- **chore/reflection 批量 commit** 标记为提交历史质量问题。
- **`ast.parse` ≠ 真实加载**：用 `python -m py_compile main.py`。
- approve 可以，但撤回/缓存路径变化缺真实 AstrBot 加载验证，评分不宜满分。

### 私聊申请与审批工作流
- 私聊事件无 `group_id` 是硬约束：必须要求用户提供群号或复用禁言记录。
- 审批必须用申请 ID / 引用回复 / 专用命令，**不能只靠关键词**。
- 申请说明可能含隐私，只转发到配置的可信管理员或管理群。
- 建议预列配置：`appeal_enabled`/`appeal_admin_qqs`/`appeal_admin_group`/`appeal_expire_minutes`/`appeal_max_concurrent`/`appeal_privacy_redact`。

### 合入外部仓库类
分类 `enhancement` + `merge-request`/`external-repo`。评估：外部代码质量、依赖兼容、许可证兼容、维护责任、配置 schema 扩展、bot 权限要求。标签加 `license-check`。