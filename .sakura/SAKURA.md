# 项目概述：mjy1113451/astrbot_plugin_gm

> 累计反思 82 次

## 1. 项目简介

`astrbot_plugin_gm` 是 AstrBot 的 QQ 群管理插件，提供插件管理员维护、禁言/解禁、踢人、撤回消息、群昵称、头衔、精华消息等能力。逻辑集中在 `main.py`，依赖 AstrBot 插件体系与 aiocqhttp / OneBot API。

主要命令：`/设管`、`/取管`、`/禁言`、`/解禁`、`/禁我`、`/踢`、`/头衔`、`/取消头衔`、`/设精`、`/撤回`、`/撤回用户` 等。

## 2. 技术栈与权限模型

- **栈**：Python 3.10+ / AstrBot / aiocqhttp / OneBot；**配置**：`_conf_schema.json` + 运行时读取；**许可证**：MIT；主目录：`main.py`、`metadata.yaml`、`_conf_schema.json`、`README.md`、`docs/`。
- **两层权限**：① 插件管理员（`plugin_admins` 或 `/设管` 动态维护，群主天然具备）；② QQ 官方权限（禁言/踢人/设精/管理/头衔依赖）。专项权限按群覆盖：`title_admins`、`group_admin_admins`、`kick_admins`、`group_overrides`。
- **全局 + 群级覆盖**：`0` 可能是合法配置（关闭阈值），不能误当缺失回退。

## 3. 近期反思沉淀（核心经验）

### 3.1 AstrBot async/yield/return（PR #116）
`async def` 内 `yield` 变 async generator，不可 `return`；权限 helper 必须纯 `async def + await`；验证至少 `python -m py_compile main.py`。

### 3.2 `/撤回` count 解析（#106）
签名 `count: int = 0/1` 时 AstrBot 提前转换，函数体内 `try/except int()` 捕获不到；改 `str` 接收 + 函数内解析。

### 3.3 本地缓存回退骨架（PR #123、#109/#110/#117/#118）
① `deque(maxlen)` + 最小化字段；② `setdefault(key, factory())` 优于 `defaultdict`；③ **bot 消息写入必须独立于业务早退链**（`if not enabled: return` 之前）；④ 排除命令自身 `message_id`；⑤ 写入失败 try/except；⑥ OneBot `get_group_msg_history` 空返回不可一概写"不支持"；⑦ `recall_cmd`/`recall_user_cmd` 必须对称。

### 3.4 `/取消头衔` "成功但未生效"（#111/#119/#125）
严格判空 `title is None or title == ""`（`strip()` 反模式）；`special_title=""`/`" "`/`None` 在 NapCat/Lagrange/go-cqhttp 语义不同；必查：bot 权限、目标为群主（协议限制）、状态回读。

### 3.5 私信申请解禁 / 群待办 / 装饰字符 QQ 三类高频模式
- **私信解禁（#120/#121）**：`needs-discussion` 高，自动解禁是敏感动作；唯一识别审批者 `sender.user_id`；最小实现到完整实现两档。
- **群待办（#131）**：OneBot v11 **不定义** `set_group_todo`（非标准扩展）；**只有群主可设**（用 `_is_group_owner`）；API 返回 ok ≠ UI 生效（1-2 秒延迟）。
- **装饰字符 QQ（#133/#134/#136）**：花体字 𝓒𝓪𝓷𝓬𝓮𝓻 / 数学字母 U+1D400-U+1D7FF **不适用 NFKC**（仅处理全角数字兼容性），需白名单 `\d{5,12}` + NFKD + 自定义映射表；`_extract_at_qq`/`_extract_at_qqs`/`_parse_qq_list` 三函数族统一加固；误解禁**不可见**>误禁言**可见**，优先级不降。
  - **#136 同根因（第二次触发）**：与 #134 同属 `_extract_at_qq` 入口解析 bug，触发命令不同（解禁 vs 踢人）。优先级保持与 #134 一致（medium）；决策路径：① 核心解禁命令解析错误（high 倾向）② 仅特定装饰字符场景触发（降一档）③ 单群单次未扩散（降一档）④ 已有 #134 模板可复用（不算新风险）→ medium。同根因不同症状的重复检测置信度上限 0.75-0.85，不直接打 `duplicate`，打 `related-to`/`same-root-cause`。
  - **传染性测试成本**：13+ 调用点扫描 + 适配器差异测试 + 边界场景（混装饰+半数字、中间夹装饰）构造，总成本 +1 天，工作量下限 2-3 天。
  - **OneBot 协议层风险**：NapCat/Lagrange 可能预处理装饰字符 AT 段（无法识别直接丢弃）；v11 标准 `data:{qq:"xxx"}` vs 扩展 `data:{user_id:"xxx"}` 字段差异会污染修复方案，需建立"装饰字符 AT 段跨适配器矩阵"。

### 3.6 标签基线（owner-driven 命令新增）
读类（#135 禁言列表）与写类（#131 群待办）：`enhancement` (0.95) + `command` (0.95) + `group-management` (0.85-0.90) + 模块标签 + `onebot`/`compatibility` + `needs-discussion` (0.65-0.85，**owner-driven 缺决策非信息**) + `needs-info` ≤0.20-0.30 + `help-wanted` ≤0.10。

**#135 读类命令扩展标签**：建议仓库新增 `mute`/`ban-list`/`ban-list`(0.85) + `read-permission`/`viewer-role`(0.70-0.85，写权限的对等标签) + `mute-action`(0.80，与 #133 解禁对称) + `onebot-extension`(0.75-0.85，`shut_up_timestamp` 非 v11 标准字段) + `configuration`(0.65-0.75，新增配置项时)。

**#135 跨适配器读取字段矩阵（执行要点）**：`shut_up_timestamp`(NapCat/go-cqhttp) / `ban_expire_time`(Lagrange) / `mute_end_time`(部分实现)；同属待整理范围：`role`/`level`/`special_title`/`join_time`/`last_sent_time`。

**#135 读类命令必查项**：① 大群分页（500+ 人 `get_group_member_list` 行为）② 缓存策略与失效 ③ 隐私/侦察工具风险（昵称+QQ 展示范围）④ 时间格式边界（>30 天、永久）⑤ 空状态友好提示 ⑥ 读权限分级（群主/群管/普通成员/插件管理员）。

### 3.7 撤回命令族五/七处同步清单（高频踩坑）
`main.py` + README + 帮助命令 + `_conf_schema.json` + CHANGELOG；扩展为七处（多媒体转写）：+ STT 配置 + 误伤率文档。

### 3.8 校验失败短路器 + 模板对齐强制 Pre-check
**反复触发的根因（PR #123 + #130 + #131 ×3 + #132 + #134 + #135 + #136 ≥7 次）**：校验失败应**局部修复字段输出格式**而非整体退化为"无法评估"/空标签；实质性判断维持。**#135 是典型案例**：分类被退化为 `other`、可行性为 `无法评估`、标签空、标题 `无建议`、重复检测 `未检测到重复`——实质性判断（owner-driven 新增读类命令）完全清晰，被整体降级是反模式。

**重复检测禁词**：❌"未检测到重复"/"无重复"/"无高度重复"/"可能是 #X 的重复"/"疑似重复"。✅"暂未发现（建议检索关键词：...）+ ⚠️ 措辞核对"。每次重复检测输出末**必须**加注"⚠️ 措辞核对：是否使用了禁用的'未检测到重复'/'无重复'/'可能是#X的重复'？"

**可行性章节硬约束**：必须显式分支判定（分支A/B/C），不允许混合叙述；分支描述需避免重叠（#135 分支B与分支A描述重叠被识别为缺陷）。

**决策路径显式化**：优先级章节必须在开头列出决策树（写/读权限、breaking change、工作量、owner-driven 性质等判定点），不允许"隐含表达"。

**模板对齐硬约束**：分析前扫描项目记忆，若有该 Issue 编号专属模板，实质性判断必须对齐；装饰字符 QQ / @解析 / 禁言类首步对照 §3.5 模板；权限模型重构对照 #130 模板；读类群管理命令对照 #135 沉淀的"读类必查项"。

**反模式 Pre-check 6 条硬约束**（反思落笔前必过）：① 字段校验错误仅触发输出修复 ② 标题/标签/可行性/重复检测不可写禁用措辞 ③ 实质性判断不得连带退化 ④ 重复检测末必须加措辞核对 ⑤ owner-driven 涉及字段差异/权限/性能时 `needs-discussion` ≥ 0.65 ⑥ 同类 issue 优先级/工作量必须显式横向对比。

## 4. 开发约定

- 逻辑集中 `main.py`，修改时全局搜索相似命令模式；管理员 QQ/群号统一 `str()` 归一化。
- QQ 操作处理接口失败、权限不足、消息超时；"API 返回 ok ≠ 实际生效"需回读（适用：禁言、头衔、设精、改群名、全员禁言）。
- 撤回类 PR 强制检查清单（9 项）：时间窗（2 分钟）、限流、部分失败、自身消息排除、bot 消息处理、撤回目标过滤、缓存数据结构、OneBot 适配差异、配置 schema。
- 装饰字符类修复（#133/#134/#136）传染性测试：必须计入 `/禁言`/`/解禁`/`/踢人`/`/设管`/`/取管` 同类命令扫描成本，小修复下限 1 天（含最小适配器验证）。
- 验证：`python -m py_compile main.py` ≥ `ast.parse`；README/帮助/schema/CHANGELOG 同步；提交避免批量重复 `chore` 噪音；行号引用标注"已读取 main.py 验证"或"约 Lxxxx"模糊表述。
- 仓库标签体系建议新增：`mute`/`ban-list`/`mute-action`（禁言子体系，与 `title`/`recall`/`vote` 并列）、`read-permission`/`viewer-role`（与 `permission` 区分的读权限维度）、`at-parse`/`at-extract`（装饰字符 @解析专用）、`decorative-unicode`/`unicode-normalization`（装饰字符特化）。
- 同根因 issue 处理：根因相同但症状/触发命令不同时（#134 踢人 vs #136 解禁），不直接打 `duplicate`，应打 `related-to`/`same-root-cause`，置信度上限 0.75-0.85，并在优先级章节显式对比说明一致性。

## 5. 协作与维护

README 维护功能表、安装、配置、权限说明与示例。Bug 与功能建议通过 GitHub Issue；低到中等复杂度修复类 PR 优先合并。详细反思见 `memory.md` 及 `memory/`。
