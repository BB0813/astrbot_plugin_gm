# 项目概述：mjy1113451/astrbot_plugin_gm

> 累计反思 98 次

## 1. 项目简介
AstrBot QQ 群管插件，逻辑集中在 `main.py`，依赖 aiocqhttp/OneBot API。Python 3.10+、MIT 许可。命令：`/设管`、`/取管`、`/禁言`、`/解禁`、`/禁我`、`/踢`、`/头衔`、`/取消头衔`、`/设管理`、`/取消管理`、`/设精`、`/设群昵称`、`/改昵称`、`/撤回`、`/撤回用户`，外加群违规检测（图片/刷屏/骂人/广告/链接/群号推广）、按群覆盖配置、发言排名等。

## 2. 权限与配置模型
- **两层权限**：插件管理员（`plugin_admins` 或 `/设管`，群主天然具备）+ QQ 官方群管权限。
- **专项权限/按群覆盖**：`title_admins`/`group_admin_admins`/`kick_admins`/`group_overrides`/`get_group_setting`/`has_*_admin_rights`。
- **全局默认 + 群级覆盖**：`0` 可能是合法配置（关闭阈值），不能误当缺失回退。

## 3. 核心风险沉淀（按主题分组）

### 3.1 AstrBot 异步与命令签名
- `async def` 内 `yield` 即变 async generator，不能 `return True/False` 被 `await`（PR #116）。
- `count: int = 0/1` 注解会让 AstrBot 提前转换，函数体内 `try/except int()` 捕不到（#106）。
- 验证至少 `python -m py_compile main.py`（≥ `ast.parse`）。

### 3.2 `/撤回` 本地缓存回退骨架（PR #123）
- 按群隔离 `{str(group_id): deque[dict]}` + 仅存 `message_id`/`user_id` + `maxlen ≥ 4N`。
- 工厂函数 `{}` + `setdefault(k, factory())` 优于 `defaultdict(factory)`。
- **bot 消息写入必须独立于业务早退链**（PR #123 阻断性 bug 根因）。
- 写入失败 try/except + debug；排除命令自身 message_id；README 明示重启不可恢复。
- `recall_cmd`/`recall_user_cmd`/`/撤回自身 N` 必须对称；撤回类 PR 9 项检查清单（时间窗/限流/部分失败/自身排除/bot/目标过滤/缓存/适配差异/schema）。

### 3.3 "提示成功但实际未生效"通用模式（头衔/禁言/设精/改名）
- 区分 `""`/`" "`/`\t`/`None`/缺失；`strip()` 把单空格误判为空（反模式）。
- `duration=0` 是合法值但 `if not duration` 会误判（falsy 判空陷阱）。
- `set_group_special_title`/`set_group_ban` 在 NapCat/Lagrange/go-cqhttp 语义可能不同。
- `@昵称` 解析走 segment/`user_id`/`_extract_at_qq`，不按空格 split（昵称可含空格）。
- 装饰字符 QQ（花体字 𝓒𝓪𝓷𝓬𝓮𝓻 / 数学字母 𝐀𝕒）：NFKC 对 U+1D400-U+1D7FF **无效**，必须白名单 `\d{5,12}` 强校验 + 自定义映射表（#134/#136）。

### 3.4 权限模型重构（#130/#132/#139/#140/#142 沉淀）
- 必给标签：`enhancement` + `breaking-change` ≥0.90 + `deprecation` ≥0.75 + `permission-model` ≥0.80 + `bot-role`/`sender-role` ≥0.70 + `configuration`/`group-management` ≥0.85 + `onebot` ≥0.65 + `needs-discussion` ≥0.75。
- 移除 `question`（owner-driven 增强有明确诉求）。
- 同类配置项扫描：`title_admins`/`group_admin_admins`/`kick_admins` 是否同步迁移。
- **优先级决策 5 路径**：① 横切权限 + breaking-change → 最低 medium；② owner-driven + 已标准化模式 → 不升 high；③ 工作量可控 + 迁移路径明确 → 不升 high；④ 跨适配器风险已识别但有兜底 → 维持 medium；⑤ **默认值决策（默认 false → 维持；默认 true → silent behavior change → 升 high）**。
- `breaking-change` 4 档：新增+默认 false ≤0.30 / 新增+默认 true 0.55-0.65（silent） / 修改既有默认值 0.70-0.80 / 删除既有 0.90-0.95。

### 3.5 owner-driven Issue 标签权重校准（#131 沉淀）
- `needs-info` ≤0.2-0.30（owner-driven 缺决策非信息）；`needs-discussion` 0.75-0.85（保持高权重）；`good first issue` ≤0.15；`help wanted` ≤0.05-0.1。

### 3.6 事件驱动型 + 动作联动型工作流（#142/#143 沉淀，仓库第 5 种角色模式）
- 触发：A（kick/ban/mute/recall）成功后自动或手动触发 B（清除记录/撤回/通知）。
- 10 项必查：① AstrBot kick/leave 事件 hook vs OneBot `notice` 订阅；② `notice` 跨适配器字段差异（`sub_type`/`event`/`notice_type`）；③ `message_history` deque maxlen 现状；④ 撤回 2 分钟硬约束降级（warning vs 报错）；⑤ 批撤回限速 20-30 msg/s；⑥ bot 自身消息排除；⑦ **撤回 ≠ 清除**（群员仍可见撤回提示）；⑧ 配置 schema `clear_history_on_kick`/`auto_recall_on_kick_enabled`；⑨ 区分命令触发 vs 任意踢出事件；⑩ 撤回失败统计回执。
- A/B/C/D 四档可行性：80-150 行 1.5-2 天 / 200-350 行 3-5 天 / 350-500 行 5-7 天 / 分阶段累计 4-6 天。
- 必给标签：`enhancement`+`command`+`recall`+`configuration`+`group-management`(≥0.85)+`permission`+`message-history`+`onebot`+`onebot-extension`+`compatibility`+`throttling`+`pagination`+`partial-failure`+`privacy`+`external-reference`+`event-driven`+`needs-discussion`+`needs-info`(≤0.30)。
- 与 PR #123 `message_history` 强相关必须 `Refs #123`；外部仓库参考标签区分：`external-reference`+`reference`（参考）vs `merge-request`+`license-check`（合入）。

### 3.7 引用消息触发型命令（#131 群待办沉淀）
- OneBot v11 标准**未定义** `set_group_todo`/`send_group_todo`（非标准扩展，NapCat/Lagrange 实现有，go-cqhttp 无）。
- QQ 群只有**群主**能设群待办（部分客户端允许管理员），复用 `_is_group_owner`。
- API 返回 ok ≠ UI 生效（客户端异步刷新 1-2 秒），提示"约 1-2 秒后生效"。
- 新增命令七处同步：main.py + README + 帮助命令 + `_conf_schema.json` + CHANGELOG + `_GM_COMMAND_NAMES` 元组注册 + 跨适配器兼容性文档。

### 3.8 删除既有命令用法（#126/#138/#139 沉淀）
- 9 项反向清单：精确删除路径 + 保留路径边界 + 调用点清空 + README 帮助文案 + yield 帮助文本 + 配置 schema 语义缩窄 + bot 回复模板 + CHANGELOG breaking-change + 替代方案提示。
- 与并行 Issue 方向冲突（如 #124 增强 vs #126 删除）单独实施会制造新不兼容，必须 `needs-discussion` 高权重。
- 主动 grep `_GM_COMMAND_NAMES` + `@filter.command(...)` 建立"命令名 → handler"映射。

### 3.9 多模态违规检测（#127/#128 语音 STT 沉淀）
- 消息类型 → 转写/标准化 → 关键词匹配 → 标准处置。`_moderation_dispatch` 建标准流水线。
- Whisper large-v3 ≈3GB 部署障碍，建议云端 API 或 small/base。
- 11 项检查：触发 segment / STT 调用 / 语音文件获取（silk/opus/amr 解码）/ 关键词匹配 / 2 分钟撤回时限 / 禁言权限 / 降级策略 / 限流 / 隐私边界 / 配置 schema（默认禁用）/ 文档同步。

### 3.10 校验失败短路器（P0 级硬约束，累计触发 ≥11 次）
- 字段校验失败 ≠ 信息不足，应**仅修复字段输出格式**，不得连带退化实质性判断为 `other`/`无法评估`/空/`无建议`/`未检测到重复`。
- 落笔前 Pre-check 6 项：① 校验失败扫描 ② 空标签扫描 ③ 标题扫描 ④ 重复检测措辞扫描 ⑤ 可行性 A/B/C 分支扫描 ⑥ 优先级 4-5 决策路径扫描。
- 重复检测禁用措辞（累计 ≥11 次触犯）："未检测到重复"/"无重复"/"可能是 #X 的重复"/"无建议"/"无法评估"。**结果行第一句话必须为"暂未发现"**。
- 同根因不同症状 issue 重复置信度上限 0.75-0.85；方向相反但同主题归 `related`。

## 4. 开发约定
- 逻辑集中在 `main.py`，相似模式全局搜索遗漏；群号统一 `str()` 归一化。
- 撤回类改动对称性 + 9 项检查清单；新命令七处同步。
- 行号引用必须标注"已读取 main.py 验证"或"约 Lxxxx"模糊表述。
- 提交避免批量重复 `chore` commit 污染历史（PR #123 第五轮教训）。
- 引入外部代码前评估许可证/依赖/风格/维护责任/schema 兼容性。

## 5. 协作与维护
README 维护功能表、安装、配置、权限说明。Bug 与功能建议通过 GitHub Issue；低到中等复杂度修复类 PR 优先合并。仅供学习交流。