# 项目概述：mjy1113451/astrbot_plugin_gm

> 累计反思 102 次

## 1. 项目简介

`astrbot_plugin_gm` 是 AstrBot 的 QQ 群管理插件，提供插件管理员维护、禁言/解禁、踢人、撤回消息、群昵称、头衔、精华消息、官方群管理员设置、群违规检测、自动撤回等能力。逻辑集中在 `main.py`，依赖 aiocqhttp / OneBot API。

主要命令：`/设管` `/取管` `/禁言` `/解禁` `/禁我` `/踢` `/头衔` `/取消头衔` `/设管理` `/取消管理` `/设精` `/取消设精` `/设群昵称` `/改昵称` `/撤回` `/撤回用户` `/撤回自身` `/消息列表` `/鞭尸` `/宵禁` `/解除宵禁` `/发群公告` `/删群公告` `/改群头像` `/设群配置` `/查看群配置` `/清除群配置` `/群违规检测状态` `/排名` `/清除数据` `/举报` `/status`。

## 2. 核心沉淀（高频引用，详细子节见 memory.md）

### 2.1 AstrBot async / yield / return 风险
`async def` 内 `yield` 即 async generator，不可 `return True/False`；被 `await` 的 helper 不得含 `yield`；验证至少 `python -m py_compile main.py`。

### 2.2 `/撤回` count 参数解析
`count: int = 0/1` 时 AstrBot 按注解提前转换，函数体内 `try/except int(count)` 捕获不到；入口用 `str` 接收再解析。

### 2.3 本地缓存回退骨架（PR #123）
`{str(group_id): deque[dict]}` + `deque(maxlen)`；bot 消息写入**必须独立于业务早退链**（置于 `if not enabled: return` 之前）；`maxlen ≥ 4 × N`；排除命令自身；写入失败 try/except + debug；README 明示重启不可恢复。

### 2.4 "提示成功但实际未生效"通用模式
覆盖解禁 `set_group_ban`、头衔 `set_group_special_title`、设精 `set_essence_msg`、改群名 `set_group_name`；必查：bot 权限/目标身份/OneBot 版本/`_extract_at_qq` 解析/API 参数语义/状态回读/适配器差异。

### 2.5 `_extract_at_qq` 高频解析入口
NFKC 对花体字/数学字母（U+1D400-U+1D7FF）无效；正确方案：白名单 `\d{5,12}` 强校验 + NFKD + 自定义映射表；不按空格 split 昵称（昵称可含空格）。

### 2.6 撤回类 PR 强制检查清单（9 项）
时间窗（2 分钟）/限流/部分失败处理/自身消息排除/bot 消息处理/撤回目标过滤/缓存数据结构/OneBot 适配差异/schema 一致性。**删除类反向清单（9 项）**：精确删除路径/保留路径边界/调用点清空/README 帮助文案清理/yield 帮助文本同步/schema 语义缩窄/bot 回复模板措辞清理/CHANGELOG breaking-change/替代方案提示。

### 2.7 校验失败短路器（强制 Pre-check 第一优先级）
字段校验失败 ≠ 信息不足；**仅局部修复字段输出格式**，**不得把所有判断都退化为"无法评估"/`other`/空标签/无建议**。已触发 9+ 次，固化 Pre-check：校验失败扫描/空标签扫描/标题扫描/重复检测措辞扫描/可行性分支扫描/优先级决策路径扫描。

### 2.8 重复检测措辞强制模板
无历史列表时**必须**写"暂未发现（建议检索关键词：...）"，**禁止**"未检测到重复"/"无重复"/"可能是 #X 的重复"/"无建议"/"无法评估"（已触犯 9+ 次）。

### 2.9 撤回命令族同步清单
五处（main.py + README + 帮助 + schema + CHANGELOG）；多媒体层/owner-driven 命令扩展为七处（+ `_GM_COMMAND_NAMES` 元组注册 + 跨适配器文档）。

## 3. Issue 分析沉淀（仓库 6 大标准模式）

### 3.1 模式一：权限模型重构类（#130/#132/#139）
删除既有配置项是用户可见 breaking change；横切所有管理类命令但有迁移路径，`medium` 不可降 `low`。必给标签：`enhancement`+`breaking-change`(≥0.90)+`deprecation`(≥0.75)+`permission-model`(≥0.80)+`bot-role`/`sender-role`(≥0.70)+`onebot`(≥0.65)+`needs-discussion`(升 0.75)；移除 `question`。

### 3.2 模式二：引用消息触发型（#131 群待办）
OneBot v11 未定义 `set_group_todo`（非标准扩展）；群主专属权限；API 返回 ok ≠ UI 生效（异步刷新 1-2 秒）。新增标签：`reply`/`quote-message`+`bot-capability`+`onebot-extension`。

### 3.3 模式三：装饰字符 QQ（#134/#136）
花体字/数学字母输入解析失败；`_extract_at_qq` 顶部加 NFKC + `\d{5,12}` 强校验。同根因重复检测置信度上限 0.75-0.85，**禁止**"可能是 #X 的重复"措辞。

### 3.4 模式四：举报/通知路由类（#140）
`needs-discussion` ≥0.80（owner-driven ≠ 无决策点）；2 维权限矩阵（举报人×被举报人 9 组合）；通知三要素（通道/对象/形式）；7 项必查含通知风暴与隐私脱敏；配置 schema 扩展 `report_*` 系列。

### 3.5 模式五：owner-driven 纯减法类（#141 命令删除）
默认起点 `low`（owner-driven + 主动减法 + 无横切）；破例维持 `medium` 需显式说明。第 5 条决策路径：命令有外部用户依赖→不降 low。必给 `command-removal`/`cleanup`；可行性 A/B/C+D 分阶段（D 是 breaking-change 减法必备风险缓冲）；九项反向清单+grep 残留检测。

### 3.6 模式六：动作联动型（#143/#145 新建）
动作 A 成功后触发动作 B（kick→clear-history / ban→notify 等），共享配置与权限。必查项 10 项含回执一致性/通知风暴/限流/权限双校验/可观测性分类回执/去重。与 PR #123 缓存骨架强关联需显式声明依赖状态。

**动作联动型 Issue 必给标签硬清单（14 项）**：
- `group-management`(0.90) ✅ 硬约束必给
- `needs-info`(≤0.30) ✅ 硬约束必给（owner-driven 缺决策非缺信息）
- `needs-discussion`(0.70-0.80) ✅ 硬约束必给（多决策点）
- `compatibility`(0.55-0.70) ✅ 硬约束必给
- `permission-model`(0.75-0.85) ✅ 硬约束必给
- `auto-action`(0.75) ✅ 动作联动特征
- `privacy`(0.70-0.80) ⚠️ **P0 缺失警告**：清历史涉及用户数据清除必给
- `onebot`(0.55-0.70)
- `onebot-extension`(0.55-0.65) ⚠️ 涉及非标准 API 必给
- `throttling`(0.75) ⚠️ 批量操作需速率控制
- `notification-storm`(0.75-0.80) ⚠️ 批量操作触发通知风暴
- `breaking-change`(0.55-0.65) 新增配置项
- `external-reference`(0.85-0.90) 或 `merge-request`(0.90) 外部仓库参考必给
- `kick`(0.85) 核心触发场景

**动作联动型 Issue 可行性分支细化必含 4 项**：
1. 撤回时限（2 分钟时间窗检测，约 20-30 行）
2. 通知风暴抑制（约 10-20 行）
3. 去重（message_id 循环 `set` 去重）
4. 回执一致性（"成功 N / 跳过 X / 失败 Y"三类计数）

**隐私合规必查 4 项**（分支 C/D 强制）：
- 审计日志（操作者、消息 ID、时间戳）
- 用户通知（被清历史用户私聊告知）
- 撤回通知抑制（避免群内风暴）
- 失败回滚（部分失败时回执 N/M）

### 3.7 合入外部仓库类精细化（#143 新建）
区分**"参考实现"**与**"直接合入"**：
- 参考实现：`external-repo`(0.90) + `reference`(0.80) + 无需 `license-check`
- 直接合入：`merge-request`(0.90) + `external-repo`(0.90) + `license-check`(0.70-0.80)
- **必须先访问外部仓库验证实现路径**，不能仅基于 Issue 链接
- 外部实现可能仅覆盖 OneBot 路径，需在"跨适配器风险"章节显式说明

### 3.8 校验失败短路器强制 Pre-check（强化）
字段校验失败 ≠ 信息不足；**仅局部修复字段输出格式**，**禁止**把字段级校验失败传导为整体分析降级为 `other`/`无法评估`/`无建议`。

**落笔前必扫描**（与重复检测并列 P0 前置）：
1. 校验失败扫描：所有输出字段是否含"无法评估/无建议/空/未检测到重复"任一关键词？
2. 若含，回溯至字段层面定位校验失败点
3. 实质性判断维持原始判断，仅修复该字段输出格式
4. 重复检测措辞扫描：结果行第一行必须写"暂未发现"

### 3.7 撤回增强族第 5 种（#142 自动+手动批量撤回）
与 #140 决策路径同构需显式互引；`breaking-change` 置信度精细化 4 档（新增 false ≤0.30 / 新增 true 0.55-0.65 silent behavior / 修改默认 0.70-0.80 / 删除 0.90-0.95）。撤回 ≠ 清除语义边界必明示。触发源区分（仅 `/踢` vs 任意踢出事件需订阅 OneBot `notice`）。

## 4. 标签与权限配置

- 标签建议覆盖主类型/模块/风险；高频模块：`recall`/`message-history`/`command`/`parser`/`onebot`/`group-management`/`moderation`/`stt`/`voice`/`title`/`permission-model`/`onebot-extension`。
- **⚠️ `privacy` 标签 P0 级强制**：涉及用户数据删除/修改时（清历史、清除记录等），必须添加 `privacy`(0.70-0.80)。已触发 P0 缺失警告 2 次。
- **owner-driven 标签权重校准**：`needs-info` ≤0.2-0.30（缺决策非信息），`needs-discussion` 0.75-0.85，`good first issue` ≤0.15，`help wanted` ≤0.05-0.1。
- **插件管理员**：`plugin_admins` 或 `/设管` 维护，群主天然具备。QQ 官方权限（禁言/踢人/撤回/设精）依赖机器人群内官方身份。专项权限按群覆盖：`title_admins`/`group_admin_admins`/`kick_admins`；`group_overrides` 嵌套结构 + `0` 是合法配置语义。

## 5. 开发约定

- 逻辑集中在 `main.py`，修改时全局搜索相似命令模式。
- 管理员 QQ/群号按 `str()` 归一化（缓存键、日志键、配置键一致）。
- 撤回相关改动必须做**对称性检查**：`recall_cmd` 与 `recall_user_cmd` 在入口分流/缓存读写/用法提示上对称；`message_history` 写入路径不得被业务早退链吞噬。
- **⚠️ 隐私合规强制检查**：涉及用户数据删除/修改时，必须评估滥用风险、合规风险、不可逆性，并添加 `privacy` 标签。
- **⚠️ 外部仓库参考必验证**：引用外部仓库实现前，必须先访问验证，不能仅基于 Issue 链接给出工作量估算。
- 验证清单：`python -m py_compile main.py` ≥ `ast.parse`；本地缓存回退类应附最小单元测试；README/帮助/schema/CHANGELOG 必须在同一 PR 同步；提交信息避免批量重复 `chore` commit（参 §2.7/2.8）；行号引用必须标注"已读取 main.py 验证"或"约 Lxxxx"模糊表述。
- 新增跨私聊/群聊工作流时，先设计状态机/申请 ID/权限边界/持久化/过期/并发幂等/隐私。
- `ast.parse` ≠ 真实加载：装饰器注册、命令注册等不会在 ast 阶段触发，**PR 验证应替换为最小 AstrBot 启动验证**。

## 6. 协作与维护

README 维护功能表/安装/配置/权限说明/使用示例。Bug 与功能建议通过 GitHub Issue 管理；低到中等复杂度 PR 优先合并；提交信息避免批量重复 `chore` commit。项目仅供学习与交流使用，需遵守 QQ / QQ 群相关规范。
