# 项目概述：mjy1113451/astrbot_plugin_gm

> 累计反思 48 次

## 1. 项目简介

`astrbot_plugin_gm` 是 AstrBot 的 QQ 群管理插件，提供插件管理员维护、禁言/解禁、踢人、撤回消息、群昵称、头衔、精华消息、官方群管理员设置等能力。逻辑集中在 `main.py`，依赖 AstrBot 插件体系与 aiocqhttp / OneBot API。

主要命令：`/设管`、`/取管`、`/禁言`、`/解禁`、`/禁我`、`/踢`、`/头衔`、`/取消头衔`、`/设管理`、`/取消管理`、`/设精`、`/设群昵称`、`/改昵称`、`/撤回`、`/撤回用户`。

## 2. 技术栈与结构

- **语言**：Python 3.10+；**框架**：AstrBot 插件体系；**接口**：aiocqhttp / OneBot action；**配置**：`_conf_schema.json` + 运行时读取；**许可证**：MIT。
- 主目录：`main.py`（命令、权限、配置、OneBot 兼容）、`metadata.yaml`、`_conf_schema.json`、`README.md`、`docs/`。

## 3. 权限与配置模型

1. **插件管理员**：`plugin_admins` 或 `/设管` 动态维护；群主天然具备。
2. **QQ 官方权限**：禁言、踢人、撤回、设精、设/取消管理/头衔仍依赖机器人群内官方权限。
3. **专项权限/按群覆盖**：`title_admins`、`group_admin_admins`、`kick_admins`、`group_admins`、`group_overrides`、`get_group_setting` 及 `has_*_admin_rights` 机制；权限变更应优先检查这些入口。
4. **全局默认 + 群级覆盖**：明确缺省回退、空列表/空对象/`0` 的语义。`0` 可能是合法配置（如关闭阈值），不能误当缺失回退。
5. **跨私聊审批**：若新增私信申请解禁等远程审批功能，必须明确插件管理员是否可对所有群代 bot 解禁、审批者所属与可审计状态。

## 4. 近期反思沉淀

### 4.1 AstrBot async/yield/return 风险（PR #116）

- `async def` 内 `yield` 即变 async generator，不可 `return True/False`，不能被 `await` 当 coroutine。
- 权限 helper（被 `await` 并返回业务值）不得含 `yield`；发送提示走 `_send`/`_build_text`。
- 顶层 handler 可 `yield event.plain_result(...)`，但不与 `return` 混用。
- 验证至少 `python -m py_compile main.py`（`ast.parse` ≠ 真实加载）；审查搜 `async def`/`yield`/`return <value>`，确认被 `await` 的 helper 非 async generator（叠加 #121）。

### 4.2 `/撤回` count 参数解析与本地缓存回退（#106/#109/#110/#117/#118/PR#123）

- `count: int = 0/1` 时 AstrBot 可能按注解提前转换，函数体内 `try/except int(count)` 捕获不到；复杂命令入口用 `str` 或原始参数接收，统一函数内解析。
- `/撤回 1` 期望撤回"当前指令上方一条消息"而非指令自身：先取群历史，过滤当前命令 `message_id`，只撤回之前 N 条；历史接口不可用时不可回退为"撤回指令自身"误报成功；引用撤回优先级最高。
- **本地缓存回退骨架**：① 按群隔离 `{str(group_id): deque[dict]}`、最小化存储（`message_id`+`user_id`）、`deque(maxlen)` 上限；② 工厂函数优先 `{}`+`setdefault(key, factory())` 而非 `defaultdict`；③ **bot 消息写入必须独立于业务早退链**（置于 `if not enabled: return` 前，否则未启用群 `after_message_sent` 永不入缓存，PR #123 阻断性 bug 根因）；④ `maxlen ≥ 4 × N`；⑤ 排除命令自身 `message_id`，按时间倒序取 N 条；⑥ 缓存首次写入失败不阻塞主流程；⑦ 全局 key 可加 LRU 淘汰；⑧ README 明示重启不可恢复；⑨ 严格判空优先 `x is None`/`x == ""`（不要 `not x`，避免误丢 `0`/`[]`）。
- OneBot `get_group_msg_history` 部分实现不支持；空返回语义模糊（不支持/参数不兼容/权限/历史不足），提示语应写"可能不支持或未返回群消息历史"。
- @ 解析不按空格拆昵称（昵称可含空格），优先 segment/`user_id`/`_extract_at_qq(raw)`。
- `/撤回 @用户 N` 进入普通 `/撤回` 兜底属路由 bug，应复用 `recall_user_cmd`；`recall_cmd`/`recall_user_cmd` 在入口分流、缓存读写、用法提示必须对称。

### 4.3 `/取消头衔` 提示成功但实际未清空（#111/#119/#123/#125）

- 严格区分 `""`/`" "`/`\t`/`None`/字段缺失；`strip()` 把单空格误判为空（已知反模式）；严格判空 `title is None or title == ""`。
- `set_group_special_title(special_title=""` vs `" "` vs `None` vs 不传、`duration=-1/0/不传` 在 NapCat/Lagrange/go-cqhttp 语义可能不同；API 返回 ok ≠ 实际生效，必要时 `get_group_member_info` 回读（注意缓存、字段差异、刷新延迟）。
- 三段兜底后仍失败的根因链路（按概率）：① bot 权限不足（非群主）→ ② 目标为群主/管理员（QQ 协议硬限制）→ ③ OneBot 适配器对 `special_title=""` 语义差异 → ④ API 返回成功但客户端缓存未刷新。
- 修复方向：失败提示包含"已尝试策略 + 最可能环境原因 + 用户下一步"；README 显式说明限制（Bot 须为群主或目标非群主/管理员）。
- 标签：`bug` + `command` + `group-management` + `title`/`special-title` + `onebot` + `needs-info`（收集 bot 群角色、目标用户角色、OneBot 实现与版本、插件 commit、完整日志）。

### 4.4 配置与权限模型（#105/#107）

- **禁言踢出阈值按群配置（#107 bug）**：配置 UI/Schema/展示未体现"全局默认 + 群级覆盖"；不删全局 `mute_kick_threshold`，应说明"全局默认，可被群级覆盖"；展示建议"有效值 + 来源"；缺失 key 回退全局，显式 `0` 表示关闭/覆盖。
- **专项权限按群配置（#105 enhancement）**：按动作授权、最小权限；改 `group_admins` 语义需考虑迁移/废弃期/兼容读取；敏感操作必须做越权和误授权测试。

### 4.5 私信申请解禁（#120/#121）

- `enhancement` `medium`：涉自动解禁敏感动作，存在越权/误解禁/并发风险。
- 最小实现：私聊 `申请解禁 群号 说明` → 申请 ID → 转发固定管理员 → 编号同意/驳回 → 复用 `_unmute_member` → 私信通知。
- 完整实现：管理员群、引用/专用命令审批、状态持久化、过期、重复去重、多管理员并发幂等、权限校验。
- 审批不能仅靠"同意/驳回"关键词，应优先申请编号/引用/`/解禁审批 同意 <id>`，并校验 `sender.user_id`（非 `event.user_id`）。
- 私聊无 `group_id`：用户输入群号或复用最近禁言记录；校验用户是否在目标群、是否真被禁言。
- PR #116 风险叠加：新增 helper 必须纯 `async def`。

### 4.6 合入外部仓库（#122）

- 标题为"。"、正文仅 URL+命令形式时，从正文重建需求，不能依赖标题分类。
- 关注：许可证兼容、依赖与框架版本、代码风格统一、维护责任、schema 扩展、bot 权限、缓存策略、撤回时间窗、限流、部分失败处理；submodule/copy/vendor 选择、后续同步。

### 4.7 PR #123 多轮增量审查教训

- **增量审查结构性盲区**：只看 diff 易遗漏 `__init__` 初始化兼容、`after_message_sent` 钩子注册与签名兼容、读取端对新数据结构适配；必须做"对接面快速扫描"（被改动接口上下游）。
- **审查评分校准**：撤回/缓存核心回退路径 bug，影响面涉及"绝大多数未启用某配置的群组"时，评分上限不超过 5/10，决策 `request_changes`。
- **"quick" ≠ 零审查**：涉及权限/撤回/缓存的 PR，最低限度须覆盖安全检查、schema 一致性、命令签名、关键风险点。
- **commit 信息去重**：多个相同 `chore(sakura): add reflection for ...` 应标记为提交历史质量问题。
- **PR 描述数字与 diff 不一致**（如 +520/-103 vs +494/-52）：审查应主动核对，要求作者澄清。
- **重写型 PR 额外审视**：即使评分无变更也应作 red flag，审查 API 兼容性、回退路径、新旧接口映射。
- **`ast.parse` ≠ 真实加载**：应替换为 `python -m py_compile main.py`，最好有最小 AstrBot 启动验证。
- **撤回类 PR 强制 9 项检查**：时间窗（2 分钟）、限流、部分失败处理、自身消息排除、bot 消息处理（`after_message_sent` 不得被业务早退链吞噬）、撤回目标过滤、缓存数据结构（`maxlen ≥ 4 × N`）、OneBot 适配差异、配置 schema 一致性。
- **多编号参数与命令匹配器冲突**：`/撤回 1 3 5` 需确认 AstrBot 把整串当作 `arg_str` 还是按空格拆。

### 4.8 撤回命令族"五处同步"清单（#124/#126）

- `/撤回` 命令族每次新增/裁剪/语义变更都涉及 **5 处强制同步**：`main.py` + `_conf_schema.json`（字段语义缩窄）+ `README.md` + 帮助命令 + `CHANGELOG`（breaking change 必标）。
- **删除既有用法**（如 `/撤回 编号...`、`/撤回 @用户 编号...`）属典型 breaking change：必须显式列"删除路径 vs 保留路径对照表"，避免误删相邻用法（如 `@用户 N` 应保留）。
- `/消息列表` ↔ `/撤回 编号` 强耦合：被删功能的下游消费若消失，需评估是否同步简化或删除。
- 配置 schema 语义缩窄必须显式列为改动点，不能用"措辞微调"糊弄；必要时建议重命名。
- 工作量常被低估：看似 30-60 行代码，实际含代码 + 帮助 + README + CHANGELOG + 测试，区间 0.5-1 工作日。

## 5. Issue 分析与标签经验

- 标题为"。"、"，"或信息极少时，必须基于正文错误文本、复现命令和代码线索检索，不能依赖标题分类。
- **结构化输出校验失败 ≠ 信息不足**：应优先修复字段输出，不得把所有判断退化为"无法评估"——这是仓库反复出现的反模式（PR #123 incr5、Issue #125 两次即因此完全失败）。**Pre-check**：任何字段出现"无建议/无法评估/空"前，确认是否源于校验失败而非真正判断缺失。
- 不能因校验失败把明确的 `bug` / `enhancement` 降级为 `other`、标签留空、标题"无建议"、可行性"无法评估"。
- **撤回类标题必须覆盖普通与按用户两种形式**；维护者主动发起的"删除功能"类 enhancement 标题应明确列出"删除路径 vs 保留路径"。
- **撤回类标签三件套**：`recall` + `command` + `parser`；**头衔类标签**：`command` + `group-management` + `title`/`special-title` + `onebot`/`compatibility` + `needs-info`。高频模块标签：`recall`、`message-history`、`command`、`parser`、`onebot`、`group-management`、`title`/`special-title`、`compatibility`、`permission`、`configuration`、`breaking-change`、`needs-discussion`、`needs-info`。
- **`breaking-change` 应作独立标签**：删除既有命令语法、修改既有参数语义、修改返回值都属 breaking change。
- **`needs-discussion` 作主标签**（当分析已指出多个未决决策点时，如 #126 `/消息列表` 是否同步未决）。
- **`help wanted` 边界**：仅"需外部贡献者补完子任务、改法不明"时推荐；维护者本人提交 + 改法明确 → 不推 `help wanted`。
- **`question` 慎用**：用户反馈功能失效而非提问时，替换为 `needs-info` 或 `compatibility`。
- **行号定位必须标注证据来源**：精确行号若无"已读取 main.py 验证"说明会让读者怀疑是猜测。
- **重复检测措辞铁律**：无历史列表时**必须**写"暂未发现（建议检索关键词：...）"，禁用"未检测到重复"/"无重复"/"可能是 #X 的重复"。关键词：撤回（`/撤回`、`/撤回用户`、`@用户`、`get_group_msg_history`、`message_id`、`delete_msg`、`batch recall`、`批量撤回`、`按编号撤回`、`breaking-change`）；头衔（`取消头衔`、`special_title`、`空格头衔`、`set_group_special_title`、`群主头衔`）；解禁审批（`申请解禁`、`禁言申诉`、`私信`、`审批`、`appeal`、`unmute`）。
- **路由语义歧义类 Issue**：必须显式列出候选语义并请求维护者确认，标 `needs-discussion`。
- **"删除既有用法"类 enhancement**：优先级默认 `low`（owner-driven + 无横切关注点 + 纯减法），显式标 `breaking-change`，工作量预留 0.5-1 工作日而非 30-60 行。
- **"默认行为"类改动**：UX 增强常被低估工作量，预留 40-80 行而非 20-40。
- **标签 checklist 模板**：① 主分类（bug/enhancement/question）② 模块标签（command/parser/group-management/recall/title/...）③ 适配器标签（onebot/napcat/lagrange/...）④ 决策标签（needs-info/needs-discussion/help wanted/breaking-change/...）。

## 6. 开发约定与注意事项

- 逻辑集中在 `main.py`，修改时全局搜索相似命令模式，避免复制粘贴式遗漏。
- 管理员 QQ 号按字符串处理，群号统一 `str()` 归一化（缓存键、日志键、配置键一致）。
- 撤回相关改动必须做**对称性检查**：`recall_cmd`/`recall_user_cmd`/`/撤回自身 N` 在入口分流、缓存读写、用法提示必须对称；`message_history` 写入路径不得被业务早退链吞噬。
- 对群管理"成功提示"保持保守：设/取消头衔、设/取消管理、禁言、踢人、撤回、改群昵称等都应检查 API 返回与状态；"API 返回 ok ≠ 实际生效"是已知反模式，必要时回读。
- 对依赖 OneBot 能力的命令，应在 README/帮助中标注依赖与替代方案。
- 新增跨私聊/群聊工作流时，必须先设计状态机、申请 ID、权限边界、持久化/过期、并发幂等。
- 撤回类 PR 强制检查清单（9 项）：时间窗、限流、部分失败、自身消息排除、bot 消息处理、撤回目标过滤、缓存数据结构、OneBot 适配差异、配置 schema 一致性。
- 验证清单：`python -m py_compile main.py` ≥ `ast.parse`；本地缓存回退类改动应附最小单元测试；README/帮助/schema 必须在同一 PR 同步；提交信息避免批量重复 `chore` commit。

## 7. 协作与维护

README 维护功能表、安装方法、配置说明、权限说明和使用示例。Bug 与功能建议通过 GitHub Issue 管理；低到中等复杂度修复类 PR 优先合并；提交信息避免批量重复 `chore` commit 污染历史。项目仅供学习与交流使用，需遵守 QQ / QQ 群相关规范。