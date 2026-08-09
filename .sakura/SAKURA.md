# 项目概述：mjy1113451/astrbot_plugin_gm

> 累计反思 77 次

## 1. 项目简介

`astrbot_plugin_gm` 是 AstrBot 的 QQ 群管理插件（`main.py` 单文件，Python 3.10+，MIT），依赖 aiocqhttp/OneBot API。命令：`/设管`、`/取管`、`/禁言`、`/解禁`、`/禁我`、`/踢`、`/头衔`、`/取消头衔`、`/设管理`、`/取消管理`、`/设精`、`/设群昵称`、`/改昵称`、`/撤回`、`/撤回用户` 等。

## 2. 权限与配置模型

1. **插件管理员**：`plugin_admins` 或 `/设管` 动态维护；群主天然具备。
2. **QQ 官方权限**：禁言/踢人/撤回/设精/设取消管理/头衔依赖机器人群内官方权限。
3. **专项权限/按群覆盖**：`title_admins`/`group_admin_admins`/`kick_admins`/`group_admins`/`group_overrides`/`has_*_admin_rights`。
4. **全局默认+群级覆盖**：`0` 可能是合法配置，不能误当缺失回退。
5. **跨私聊审批**：新增私信申请解禁功能必须明确插件管理员是否可对所有群代 bot 解禁、审批者所属与可审计状态。

## 3. 关键反思沉淀

### 3.1 AstrBot async/yield 风险（PR #116）

`async def` 内 yield 变 async generator 不可 `return`，不能被 `await`。权限 helper 不得含 yield；顶层 `yield event.plain_result(...)` 不与 `return` 混用。验证至少 `python -m py_compile main.py`。

### 3.2 `/撤回` 解析与本地缓存回退（#106/109/110/117/118、PR #123）

- `count: int = 0/1` 时 AstrBot 按注解提前转换，`try/except int()` 捕获不到，改用 `str` 接收再解析。
- `/撤回 1`：取群历史过滤当前命令 `message_id`，只撤回之前 N 条；历史接口不可用不可回退为"撤回指令自身"。
- 本地缓存回退：按群隔离 `deque(maxlen)` + 工厂 `{}`+`setdefault`（优于 `defaultdict`）；**bot 消息写入必须独立于业务早退链**（PR #123 阻断性 bug 根因）；写入失败 try/except+debug；README 明示重启不可恢复。
- **recall_cmd/recall_user_cmd 对称性**：不复制两套撤回逻辑；只审 diff 易漏缓存回退对称性。
- **9 项 PR 强制检查**：时间窗（2 分钟）、限流、部分失败处理、自身消息排除、bot 消息处理、撤回目标过滤、缓存数据结构、OneBot 适配差异、配置 schema 一致性。

### 3.3 "提示成功但实际未生效"通用模板（#111/119/125/133）

从头衔扩展到解禁/设精/改群名/全员禁言全群管理动作。`""`/`" "`/`None`/不传与 `duration=-1/0/不传` 跨 NapCat/Lagrange/go-cqhttp 语义不同；`strip()` 把单空格误判为空（反模式）；严格判空用 `is None / == ""`。排查：bot 权限 → 目标身份（群主协议限制）→ 适配器差异 → API 成功但回读缓存未刷新。

### 3.4 装饰字符 QQ 高频解析 bug 模板（#134 + #136）

`_extract_at_qq` 未对装饰字符 Unicode（花体字/数学字母 U+1D400-U+1D7FF、Enclosed Alphanumerics U+2460-U+24FF）做归一化和纯数字硬校验。

- **NFKC vs NFKD 红线**：NFKC 仅处理兼容性分解字符（不拆花体字）。正确方案：`\d{5,12}` 纯数字白名单 + NFKD + 自定义映射表，或直接拒绝并提示。**分析中不能笼统说"加 NFKC 归一化"。**
- **必给标签**：`bug`≥0.90 + `command`≥0.90 + `parser`≥0.85 + `at-parse`/`at-extract`(≥0.85，新建) + `group-management`(≥0.80) + `mute`/`unmute`/`mute-action`(≥0.85，新建) + `onebot`/`compatibility`(0.50-0.70) + `security`/`input-validation`(0.50-0.65，新建) + `needs-info`(0.30-0.40，**避免偏高**)。
- **误解禁 vs 误禁言**：误解禁**不可见**（检测延迟）+ 修复成本更高；同根因下略偏重，但通常维持 `medium`。
- **修复传染性**：`_extract_at_qq`/`_extract_at_qqs`/`_parse_qq_list` 函数族系统性问题，应推动统一重构为单一解析入口。
- **回读判定**：修复后装饰字符被拦截，`_unmute_member` 不会被错误调用，**修复本身已消除误解禁路径**，无需额外回读——分析中应显式说明。

### 3.5 语音 STT + 违规词自动撤回（#127/128）

`medium`：误触发风险（转写误识别 × 关键词模糊匹配）+ 隐私/生物特征风险。STT 11 项强制检查：触发场景/STT 调用/语音文件获取/关键词匹配/撤回时限（先撤回再尝试禁言）/禁言权限/降级策略/性能限流/隐私边界/配置 schema（默认禁用）/文档同步。建立"输入源 → 转写/标准化 → 文本违规检测 → 处置"标准流水线。

### 3.6 权限模型重构（#130/132，`enhancement+breaking-change+medium`）

必备：`deprecation`≥0.75 + `permission-model`≥0.80（新建）+ `configuration`≥0.85 + `group-management`≥0.85 + `bot-role`/`sender-role`≥0.70 + `onebot`/`compatibility`≥0.65 + `needs-discussion` 升 0.75；移除 `question`。同类配置项（`title_admins`/`group_admin_admins`/`kick_admins`）主动建议同步迁移。删 `plugin_admins` 涉及 18+ 调用点+迁移路径+测试 → 200-350 行、3-5 天。

### 3.7 新增 owner-driven 命令模板（#131 群待办 / #135 禁言列表）

**OneBot v11 关键事实**：未定义 `set_group_todo`/`send_group_todo`——非标准扩展。`/添加群待办` 仅群主可设（部分允许管理员），复用 `_is_group_owner`；API 返回 ok ≠ UI 生效，提示"约 1-2 秒后生效"。

**七处同步清单**：`main.py`+README+帮助命令+`_conf_schema.json`+CHANGELOG+`_GM_COMMAND_NAMES` 元组注册+跨适配器兼容性文档。

**读类 vs 写类区分**（#135 沉淀）：写类关注写权限/API 返回/UI 生效延迟/回执；读类关注读权限/字段差异/数据脱敏/缓存策略/**侦察工具滥用风险**。读类 7 项：大群分页、字段差异 fallback、隐私、时间格式化边界（>30 天/永久/负值/字段缺失）、空状态友好提示（"无被禁言成员" vs "适配器未返回禁言字段"语义不可混用）、缓存策略、跨适配器回读兜底。

**跨适配器字段矩阵**（首次沉淀）：`role`/`shut_up_timestamp`（NapCat/go-cqhttp）/`ban_expire_time`（Lagrange）/`mute_end_time`（部分实现）/字段缺失（非静默失败，须降级提示）。

**owner-driven 标签基线**：`needs-discussion` ≥ 0.65-0.75、`needs-info` ≤ 0.20-0.30、`good first issue` ≤ 0.10-0.15、`help wanted` ≤ 0.05-0.10。

### 3.8 删除既有命令用法（#126）

`enhancement+breaking-change+medium`。与并行 Issue 方向相反（如 #124 增强 vs #126 删除）→ 必须强化 `needs-discussion` + 先解决冲突再实施。**9 项反向清单**：精确删除路径（行号 ±验证）/保留路径边界/调用点清空/README 帮助清理/yield 帮助同步/schema 语义缩窄/bot 回复措辞清理/CHANGELOG breaking-change/替代方案提示。

### 3.9 加群申请拒绝自定义理由（#129）

`enhancement+medium`。OneBot `reason` 矩阵：NapCat ≤10 字符/Lagrange ≤10-20 字符/go-cqhttp 部分 ≤30/空串+None+特殊字符处理各实现不同；建议 schema 暴露 `join_reject_reason_max_length`。`pending_join_requests`+`_handle_group_request` 是高频改动点（#57+#129 已两次扩展）。

### 3.10 私信申请解禁（#120）

`enhancement+medium`：私聊无 `group_id` 必须用户输入或复用最近禁言/禁我记录；审批不能仅靠"同意/驳回"关键词（管理群易误触发），优先申请编号+校验 `sender.user_id`。

## 4. 反思流程硬约束（§4.29）

### 4.1 校验失败短路器（强制 Pre-check）

校验失败 ≠ 信息不足。看到字段校验错误时**仅修复字段输出格式**，**实质性判断（分类/优先级/标签/可行性/标题/重复检测）必须独立完成**，不得整体退化为"无法评估"/`other`/空标签/无建议。

**保底输出模板**：分类+优先级+摘要+建议标签列表+重复检测（"暂未发现"+关键词+⚠️措辞核对）+标题改写（"可保留"或轻量化）。

**触发频率**（已 5+ 次）：PR #123 + #130 + #131 三轮 + #132 五次 + #133 + #134 + #136。

### 4.2 项目记忆模板对齐硬约束

分析前**必须先扫描项目记忆是否存在该 Issue 专属模板**；若有，实质性判断**必须与模板对齐**，仅在模板未覆盖时增量分析。bug 类已第四次触发模板对齐失败反模式（#131/#132/#133/#134）。

### 4.3 重复检测措辞红线

禁用：`未检测到重复`/`无重复`/`可能是 #X 的重复`。**必须**用：`暂未发现（建议检索关键词：...）` + ⚠️ 措辞核对尾注。"症状相似 ≠ 根因相似"，先按模块归类再判断重复。

### 4.4 优先级/可行性/行号引用硬约束

- 优先级四条判定：① 横切+兜底→medium；② 安全语义（不可见副作用）→medium（不升 high 因为…）；③ 修复小+模板沉淀→不升 high；④ 用户可手动修复→不升 high。
- 可行性必须显式 A/B/C 分支（不要只给范围估算）；影响 PR 拆分与回滚成本。
- 行号必须前置声明"基于项目记忆+既有 PR 模式推断"或"基于 commit XXXX，以最新为准"。避免批量重复 `chore` commit 污染历史。

## 5. Issue 分析高层规则

标题极少信息时基于正文错误文本/复现命令/代码线索检索。标签覆盖主类型+模块+风险：高频 `recall`/`message-history`/`command`/`parser`/`onebot`/`group-management`/`moderation`/`stt`/`title`/`mute`/`at-parse`/`onebot-extension`/`read-permission`（建议新建细分）。方向相反但同主题严格归为 `related` 而非重复。"默认行为"类改动预留 40-80 行而非 20-40。路由语义歧义类：必须显式列出候选语义并请求维护者确认。

## 6. 开发约定与注意事项

`main.py` 单文件集中，修改全局搜索相似命令模式。QQ 号统一 `str()` 归一化（缓存键/日志键/配置键一致）。"API 返回 ok ≠ 实际生效"是已知反模式，必要时回读。新增跨私聊/群聊工作流必须先设计状态机、申请 ID、权限边界、持久化/过期、并发幂等、隐私和发送失败处理。外部代码合入前评估许可证/依赖版本/submodule/copy/vendor。撤回类改动必须做对称性检查（`recall_cmd`/`recall_user_cmd`/`/撤回自身 N` 与新默认行为不冲突；`message_history` 写入路径不被业务早退链吞噬）。验证：`python -m py_compile main.py` ≥ `ast.parse`；README/帮助/schema/CHANGELOG 必须在同一 PR 同步。

## 7. 协作与维护

README 维护功能表/安装/配置/权限说明；Bug 与功能建议通过 GitHub Issue 管理；低到中等复杂度修复类 PR 优先合并。仅供学习与交流使用，遵守 QQ/QQ 群相关规范。
