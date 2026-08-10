# 项目记忆

累计反思 103 次

## 仓库背景

`mjy1113451/astrbot_plugin_gm` 是 AstrBot 群管理插件。**高频模式**：权限模型重构（#130/#132/#139/#140）、引用消息触发型命令（#131 群待办）、撤回/STT/头衔/加群申请、装饰字符 QQ 解析（#134/#136）、解禁（#133）、禁言列表查询（#135 读类）、命令别名/重命名（#138）、举报/通知路由（#140）、**owner-driven 纯减法（#141：删 /取消头衔）**、**撤回增强类（#142：踢→批量撤回被踢者历史）**、**动作联动型（#143：踢→清历史等 A 成功后触发 B）**。出现关键词即套对应模板。

- **"删除功能"类 Issue 不应自动归 medium**：维护者本人纯减法 → low 组合（主动减法+owner 自实施+无横切关注点）。
- **`breaking-change` 独立标签**：删命令/改命令参数语义/改返回值/删配置项。
- **`recall_cmd` 高频改动点**：撤回类优先关注 Path 分支完整性、对称性、缓存写入、帮助文本同步。
- **撤回缓存三层链路**：`recent_messages` → `message_history` → `get_group_msg_history` 兜底。
- **跨适配器读取类群成员字段差异矩阵**（#135/#136 沉淀）：`role`、`shut_up_timestamp`/`ban_expire_time`/`mute_end_time` 等差异矩阵已建立——"读群成员 X 字段"类必先列对照表。
- **`breaking-change` 4 档精细化（#142 沉淀）**：新增配置+默认 false ≤0.30 / 新增配置+默认 true 0.55-0.65（silent behavior change）/ 修改既有默认值 0.70-0.80 / 删除既有配置或命令 0.90-0.95。
- **跨适配器 `delete_msg` + `get_group_msg_history` 差异矩阵（#142/#143 沉淀）**：NapCat/Lagrange/go-cqhttp 三家 delete_msg 限速（1-5/s 差异）+ `get_group_msg_history` 最大返回条数差异。
- **OneBot `notice` 事件跨适配器差异矩阵（#142 沉淀）**：`group_decrease`/`group_member_leave` 字段名差异（sub_type/event/notice_type）。
- **撤回 ≠ 清除（#142 沉淀）**：撤回对其他群员仍可见"XXX 撤回了一条消息"通知，并非真正清除，分析必须明示该区分。
- **缓存骨架集成度必须查证（#142 沉淀）**：PR #123 `message_history` 的 merge 状态、容量、跨群隔离语义必须查证而非假设。
- **新增标签首次使用置信度上限（#142 沉淀）**：生僻标签首次使用 ≤0.75，避免误导检索。
- **owner-driven 纯减法 vs 对外契约删减边界（#141 沉淀）**：纯内部清理才适用 `low`；对外可见命令删除应保留 `medium`。

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

## 动作联动型 Issue 标准模板（#143 新增，仓库第 5 种）

- **触发场景**：动作 A 成功后自动触发动作 B（kick→clear-history、ban→notify、mute→log 等），A 与 B 共享配置与权限。
- **与 #130/#140 差异**：#130 权限模型重构、#140 单命令内通知路由分支、**#143 事件钩子驱动的自动副作用 + 配置扩展**（新增事件层，不影响现有命令）。
- **#142/#143/#145 三者关系索引**（#145 补充）：
  - #142：动作 A → 动作 B（A=踢人, B=撤回）——**撤回方向**
  - #143：动作 A → 动作 B（A=踢人, B=清历史）——**清历史方向**
  - #145：与 #143 几乎一致 —— **建议合并**
  - 未来类似 Issue 需显式互引并判断是否重复
- **必查项 12 条**（#145 扩展）：①事件钩子获取（AstrBot `group_decrease` / 适配器层 / 轮询）②副作用边界（清自己/清被踢者/清缓存）③**回执一致性**（B 部分失败如何回执 A 成功状态）④**通知风暴**（批量撤回触发通知）⑤**速率限制**（throttling，分批执行）⑥配置粒度（可关闭/可调上限/按群覆盖）⑦**权限双校验**（A/B 各自权限对齐 + bot 自身权限边界）⑧时间窗约束（OneBot 2 分钟）⑨跨适配器差异矩阵 ⑩**去重**（本地缓存与服务端历史可能重复 message_id）⑪**隐私合规**（删除用户数据涉及 GDPR/个人信息）⑫**合规红旗**（主流平台 Bot API 通常不允许运营方清空他人消息）。
- **必给标签硬清单**（#145 补漏 P0）：`enhancement`(0.95) + `command`(0.85-0.95) + `configuration`(0.80-0.90) + `group-management`(0.85-0.92) + `permission-model`(0.80-0.85) + `kick`(0.85-0.90) + `message-history`(0.75-0.85, 新建) + `auto-action`(0.70-0.80, 新建) + `privacy`(0.75-0.85, **漏标 P0**) + `onebot`(0.55-0.90) + `compatibility`(0.55-0.75) + `onebot-extension`(0.55-0.65, 新建, **漏标 P0**) + `throttling`(0.75, 新建, **漏标 P0**) + `notification-storm`(0.80, 新建) + `breaking-change`(0.40-0.65) + `needs-discussion`(0.70-0.85, **漏标 P0**) + `needs-info`(≤0.30, **漏标 P0**) + `external-reference`(0.85, 参考) **或** `merge-request`(0.90, 合入) **不可混用**。
- **"参考外部仓库"vs"外部合入"标签区分**：
  - **参考借鉴**（"按这个仓库的代码实现"）→ `external-reference` + `external-repo`，**不**加 `merge-request`/`license-check`
  - **真正合入**（"把这个仓库的代码合入"）→ `merge-request` + `license-check` + `external-repo`
  - **必须先访问外部仓库验证实现路径**，不能仅基于 Issue 文本链接判断
  - 外部实现可能仅覆盖 OneBot 路径，需显式说明
- **外部参考仓库清单**（#143/#145 沉淀）：zcj-ui/astrbot_plugin_group_guardian 已被多次参考，建议维护许可证、活跃度、API 兼容性记录。
- **优先级决策路径 5 条**：①横切权限 + breaking-change → 最低 medium ②owner-driven + 已标准化模式 → 不升 high ③工作量可控 + 迁移路径明确 → 不升 high ④跨适配器风险已识别但有降级 → 维持 medium ⑤**默认值决策（默认 false → 维持；默认 true → 升 high/silent behavior change）**。
- **可行性分支细化**（#145 补充）：
  - A 80-150 行/1-2 天（缺七处同步建议 1-1.5 天）
  - B 150-250 行/2-3 天（需含：撤回时限逐条检测约20-30行、通知抑制约10-20行、set去重）
  - C 250-400 行/3-5 天（需含：审计日志30-50行、撤回通知脱敏20-30行、用户私聊通知15-25行）
  - D 分阶段 4-6 天
- **可观测性回执**：成功 N/M、跳过 X 条因时间窗、失败 Y 条因限流 的分类回执。
- **红旗**：
  - "清历史/清记录"涉及隐私合规风险，必须显式评估滥用/合规/不可逆性
  - 双校准 `needs-info` ≤0.30 + `needs-discussion` ≥0.75-0.80
  - 重复检测前置过滤：主分类不同→0.3；主分类同但 API 不同→0.30
- **标题范式**：`[enhancement][medium] 踢人事件自动清除/撤回被踢用户本群历史（按群覆盖配置 + 独立指令）`。

## owner-driven 纯减法类模板（#141 新增，仓库第 6 种）

- **触发**：维护者本人发起删除既有命令/功能/配置项。
- **与 #138（重命名）/ #139（双向复合）差异**：保留能力 vs 完全删除 vs 删+增复合。
- **必查项**：①七处同步（main.py + `_GM_COMMAND_NAMES` + README + 帮助 + CHANGELOG + metadata.yaml + 公告）对纯减法也强制 ②grep 全仓库残留（`grep -rn "_clear_group_title"`）③i18n/测试用例同步清理 ④用户替代路径评估 ⑤已知 bug 与删除动机耦合 ⑥AstrBot 装饰器注册残留检测。
- **必给标签**：`enhancement`(0.95) + `breaking-change`(0.90) + `command-removal`/`cleanup`(新建) + `command`(0.95) + `documentation`(0.85) + `needs-discussion`(0.80-0.85) + `onebot`(≥0.55, #140 硬约束) + `needs-info`(≤0.30) + `migration`(若分支 B/C)。
- **优先级**：默认 `low`（owner-driven + 主动减法 + 无横切），例外（对外契约删减 + 教程/脚本引用）才显式说明维持 `medium`。
- **可行性分支 A/B/C/D**：A 纯删除 5-15 行/0.25-0.5 天 / B 删+替代入口 60-100 行/1-2 天 / C 删+README 提示 25-55 行/0.5 天 / **D 分阶段（先废弃警告一版本周期→再删）30-50 行/0.5-1 天**。
- **`deprecation` vs 直接删除**：仅"标记废弃但保留过渡期"才适用 `deprecation`；直接删除应给 `command-removal`/`cleanup` 而非 `deprecation`。

## 撤回增强类 Issue 模板（#142 沉淀，#122/#124/#126 族系延伸）

- **触发场景**：`/踢` + 自动/手动批量撤回被踢用户本群全部历史。
- **必查项**：①OneBot `get_group_msg_history` 跨适配器最大返回差异 ②`delete_msg` 限速差异 ③2 分钟撤回时限逐条检测 ④缓存骨架（PR #123）真实容量与重启语义 ⑤自身消息排除（`after_message_sent` 早退前写入）⑥业务早退链吞噬共享逻辑规避 ⑦跨群隔离 vs 共享（缓存 key 设计）⑧"全量"语义在 README 诚实告知 ⑨节流方案（全局 sleep vs 令牌桶）⑩`group_overrides` 嵌套结构与生效顺序。
- **必给标签**：`enhancement`(0.95) + `recall`(0.95) + `command`(0.95) + `message-history`(0.90) + `group-management`(0.88) + `configuration`(0.85) + `onebot`(0.80-0.85) + `onebot-extension`(0.55-0.65, 仓库新建) + `throttling`/`rate-limit`(新建) + `pagination`(新建) + `silent-behavior`(默认 true 时) + `partial-failure`(新建) + `needs-discussion`(0.85) + `needs-info`(≤0.30) + `breaking-change`(0.30-0.40 默认 false 时)。
- **优先级**：`medium`（默认关闭 + owner-driven + 工作量可控 + 风险有兜底）。
- **可行性分支**：A 80-120 行/1.5-2 天 / B 200-350 行/3-5 天 / C 350-500 行/5-7 天 / D 分阶段先 A 后 B/C。
- **跨 Issue 决策路径同构互引模板（#142 新增）**：当两个 Issue 决策路径同构（如 #142 与 #140），应在优先级章节**显式互引**——"与 #X 决策路径同构（横切权限但有兜底 / owner-driven + 已标准化模式 / 工作量可控 + 迁移路径明确 / 风险已识别但有降级），维持 medium"。
- **踢出事件触发源区分（#142 沉淀）**：维护者执行 `/踢` 才触发 vs 任意踢出事件（机器人踢/用户自助退群/管理员 QQ 移动端踢人）都要触发——前者简单（命令 handler 内即可），后者需订阅 OneBot `notice` 事件，工作量翻倍。

## 装饰字符 QQ / 视觉欺骗型用户名模板（#134/#136 高频解析类 bug，#139/#140 多次触犯）

- **必查项**：① `_extract_at_qq` 是否 NFKC/NFKD 归一化 ② OneBot 适配器是否对装饰字符 QQ 拒绝/截断 ③ 群号是否也被装饰字符污染 ④ 是否需在输入层加"QQ 必须是纯数字"硬校验 ⑤ 装饰字符 QQ 跨适配器命令成功率矩阵 ⑥ 完整执行日志 ⑦ `_extract_at_qq` 解析路径（必须按 segment/user_id，不按空格 split）⑧ 同类命令传染性 ⑨ 多 `@` 取首个 vs 拒绝多目标的语义边界。
- **NFKC vs NFKD 技术细节**：Mathematical Alphanumeric Symbols（U+1D400-U+1D7FF）/ Enclosed Alphanumerics（U+2460-U+24FF）**不适用于 NFKC**——NFKC 仅处理全角数字。**笼统说"加 NFKC 归一化"是错误技术建议**。正确方案：①白名单 `\d{5,12}` 纯数字 ②NFKD + 自定义映射表 ③直接拒绝非纯数字。
- **修复建议**：在 `_extract_at_qq` 顶部加白名单 `\d{5,12}` 强校验 + 错误提示。
- **必给标签**：`bug`(0.95) + `command`(0.95) + `parser`(0.85) + `at-parse`(0.85) + `group-management`(0.80) + `onebot`(0.35-0.50) + `compatibility`(0.35-0.50) + `mute`/`unmute`(0.85) + `unicode-normalization`(新建) + `input-validation`(新建) + `needs-info`(≤0.30)。
- **优先级**：`medium`，**显式做"误解禁 vs 误禁言"风险对比**。

## 反模式（P0 硬约束，#142/#143/#145 第 9-11 次触发）

- **校验失败短路器（P0）**：字段校验失败**仅修复字段输出**，**不得整体降级为"无法评估"/`other`/空**。**Pre-check**：含"无建议/无法评估/空/未检测到重复"前必先确认是否源于校验失败——校验失败应**局部修复**。**实质性判断不得连带退化**。**#143 整体降级**。**"#143/#145 恢复模式"**：下次遇整体降级，**先恢复实质性判断再修复字段输出**。
- **重复检测措辞（P0）**：无历史列表写"**暂未发现**"+建议检索关键词；"未检测到重复"/"无重复"/"可能是 #X 的重复"均被禁止。末加注"⚠️ 措辞核对"。**#142/#143 触犯**。
- **删除+新增对称命令复合诉求必须显式拆分**（#139）。
- **breaking-change 4 档评估**（#139/#142）。
- **七处同步对纯减法也强制**（#139），`_GM_COMMAND_NAMES` 元组注册是易错点（#142）。
- **owner-driven 纯减法主动降 low**（#130/#132/#138），显式说明理由。
- **重复检测前置过滤**：主分类不同→0.3；主分类同但 API 不同→0.30。
- **同类 Issue 显式互引**（#142 升级为硬约束）。
- **必给标签逐项核对（P0）**：常见遗漏 `at-parse`/`unmute`（#136）、`onebot-extension`/`reply`（#139）、`bot-role`/`notification`（#140）、`group-management`/`needs-info`/`compatibility`/`external-reference`（#142/#143）。**`parser` 仅在装饰字符/`_extract_at_qq`/`_get_reply_id` 场景给**（#138/#143 多次误标）。
- **`needs-info` vs `needs-discussion` 双校准（P0）**：owner-driven 缺决策非信息 → `needs-info` ≤0.30 与 `needs-discussion` ≥0.80 **必同时满足**（#140/#142/#143 多次违反）。
- **可行性 A/B/C（+D 分阶段）**（#133/#135/#139/#142）；**优先级决策路径 4 条（#142 升级 5 条含默认值）**（#133/#142）。
- **模板对齐检查**（#136/#139/#140/#142/#143）：装饰字符/禁言/群待办/举报/动作联动/撤回增强类 Issue，**第一步对照模板逐项勾选**。
- **`ast.parse` ≠ 真实加载**（用 `python -m py_compile`）；**记忆引用可溯源**（参 §X 章节）；**审查评分**（撤回/缓存回退路径影响"绝大多数未启用配置群组"时 ≤5/10）。
- **owner-driven ≠ 无决策**（#135/#140），`needs-discussion` ≥0.65-0.85。
- **标签误标**（#138）：`parser`/`recall` 不涉及应删。**标题禁止"无建议"**：清晰原标题"可保留"或给轻量版，"。"必须改写。
- **红旗**（#140/#142/#143）：双校准 `needs-info` ≤0.30/`needs-discussion` ≥0.80；`bot-role` 角色查询必给；`onebot`/`compatibility` API 调用必给（≥0.55）；`group-management` ≥0.85 对群管类必给。

## Issue 分析经验

### 分类、优先级、标签与标题
- 报错/参数错误→`bug`；权限/配置粒度→`enhancement`；移除旧机制→评估 `breaking-change`。
- `medium`：核心命令局部不可用/权限影响多群但非阻断；启动失败/越权/误踢/误撤→`high`。
- **`needs-info` vs `needs-discussion` 双校准**：缺关键事实 vs 决策待定；owner-driven 缺决策非信息 → `needs-info` ≤0.30，`needs-discussion` ≥0.75-0.85。
- **"全员可 X"是重大权限变更**：显式对比"原本谁能做 vs 现在谁能做"，评估滥用风险。
- **行号引用**：无"已读取验证"则"约 L2000-2060"模糊表述。
- **可行性 A/B/C（+D）**（#133/#135/#139/#142）；**优先级决策路径 4 条（#142 升级 5 条含默认值）**（#133）。
- **小型修复工作量下限 1 天**（#134）。
- **"动作联动型"（#143）vs"命令集重构"（#139）**：先判断属本模板还是 #139，不可混用。
- **"撤回增强类"（#142）**：踢→批量撤回被踢者历史更接近 #122/#124/#126 撤回族系，不归 #143 动作联动型。
- **`external-reference` vs `merge-request`（#143）**：参考借鉴 vs 真正合入，标签不可混用。

### AstrBot 命令参数与撤回逻辑
- `@filter.command(...)` 区分启动 vs 运行；AstrBot 提前转换参数，函数体内 `try/except int(count)` 无法兜底。
- `/撤回 N` = 撤回当前命令之前 N 条；`count=1` 最小必测；排除 `event.message_id`。
- **本地缓存撤回骨架 8 条**：按群隔离 / `message_id+user_id` / deque maxlen / 写入入口对称 / 回退标识 / 文档明示重启不可恢复 / 写入失败 try/except+debug / 提示语区分。
- **早退语句吞噬共享逻辑**：基础设施写入置于业务早退**之前**。
- **`defaultdict(factory)` 陷阱**：`.get()` 安全，但 `if k in d`/`dict(d)`/`copy.copy(d)`/`json.dumps` 无差别创建空条目。**推荐 `{}` + `setdefault(key, factory())`**。
- **falsy 判空陷阱**：`duration` 必须 `is None`/`== -1`（#133）。
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
分类 `enhancement` + `merge-request`/`external-repo` + `license-check`。评估：外部代码质量、依赖兼容、许可证兼容、维护责任、配置 schema 扩展、bot 权限要求。

**#143 精细化**：
- **参考借鉴**（"按这个仓库的代码实现"）→ `external-reference` + `external-repo`，**不**加 `merge-request`/`license-check`。
- **真正合入**（"把这个仓库的代码合入"）→ `merge-request` + `license-check` + `external-repo`。
- 无论哪种必须**先访问外部仓库验证实现路径**，不能仅基于 Issue 文本链接判断。
- 外部实现可能仅覆盖 OneBot 路径，需在"跨适配器风险"章节显式说明。