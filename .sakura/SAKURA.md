# 项目概述：mjy1113451/astrbot_plugin_gm

> 累计反思 77 次

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

### 3.6 标签基线（owner-driven 命令新增）
读类（#135 禁言列表）与写类（#131 群待办）：`enhancement` (0.95) + `command` (0.95) + `group-management` (0.85-0.90) + 模块标签 + `onebot`/`compatibility` + `needs-discussion` (0.65-0.85，**owner-driven 缺决策非信息**) + `needs-info` ≤0.20-0.30 + `help-wanted` ≤0.10。

### 3.7 撤回命令族五/七处同步清单（高频踩坑）
`main.py` + README + 帮助命令 + `_conf_schema.json` + CHANGELOG；扩展为七处（多媒体转写）：+ STT 配置 + 误伤率文档。

### 3.8 校验失败短路器 + 模板对齐强制 Pre-check
**反复触发的根因（PR #123 + #130 + #131 ×3 + #132 + #134 + #135 + #136 ≥7 次）**：校验失败应**局部修复字段输出格式**而非整体退化为"无法评估"/空标签；实质性判断维持。

**重复检测禁词**：❌"未检测到重复"/"无重复"/"无高度重复"/"可能是 #X 的重复"/"疑似重复"。✅"暂未发现（建议检索关键词：...）+ ⚠️ 措辞核对"。

**模板对齐硬约束**：分析前扫描项目记忆，若有该 Issue 编号专属模板，实质性判断必须对齐；装饰字符 QQ / @解析 / 禁言类首步对照 §3.5 模板；权限模型重构对照 #130 模板。

## 4. 开发约定

- 逻辑集中 `main.py`，修改时全局搜索相似命令模式；管理员 QQ/群号统一 `str()` 归一化。
- QQ 操作处理接口失败、权限不足、消息超时；"API 返回 ok ≠ 实际生效"需回读（适用：禁言、头衔、设精、改群名、全员禁言）。
- 撤回类 PR 强制检查清单（9 项）：时间窗（2 分钟）、限流、部分失败、自身消息排除、bot 消息处理、撤回目标过滤、缓存数据结构、OneBot 适配差异、配置 schema。
- 装饰字符类修复（#133/#134/#136）传染性测试：必须计入 `/禁言`/`/解禁`/`/踢人`/`/设管`/`/取管` 同类命令扫描成本，小修复下限 1 天（含最小适配器验证）。
- 验证：`python -m py_compile main.py` ≥ `ast.parse`；README/帮助/schema/CHANGELOG 同步；提交避免批量重复 `chore` 噪音；行号引用标注"已读取 main.py 验证"或"约 Lxxxx"模糊表述。

## 5. 协作与维护

README 维护功能表、安装、配置、权限说明与示例。Bug 与功能建议通过 GitHub Issue；低到中等复杂度修复类 PR 优先合并。详细反思见 `memory.md` 及 `memory/`。
