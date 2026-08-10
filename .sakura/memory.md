# AstrBot GM 插件代码审查经验记忆

> 累计反思 120 次（2026-08-10 更新）

---

## 一、审查策略触发规则

### 1.1 策略升级阈值
| 条件 | 策略 |
|------|------|
| 破坏性配置变更（删除默认项） | **必须 full** |
| 新增配置项 ≥ 5 个 | 建议 standard |
| 代码变更 ≥ 200 行 | 建议 standard |
| 增量包含合并提交 | 建议 standard |

### 1.2 快速失败规则
```
审查工具验证失败时 → 自动标记 "manual review required"
禁止产生 None/10 评分（应触发告警）
```

---

## 二、审查工具鲁棒性要求

- 审查输出必须有评分（None/10 → 拒绝提交）
- `file findings` 必须同时提供 `line values`
- 验证失败时降级为 manual review，不产生无效输出

---

## 三、分类型必检清单

### 3.1 命令移除（AstrBot 插件）
```
□ main.py handler 已删除
□ _GM_COMMAND_NAMES 元组已同步
□ README/文档中无残留引用（grep 验证）
□ CHANGELOG 已记录
□ metadata.yaml 已更新
□ i18n 文件无残留
□ 七处同步完整性确认
```

### 3.2 配置项变更
```
新增项：
□ 默认值是否安全（false 优于 true）
□ 枚举值边界校验
□ 数值范围在 schema 中限定

删除项：
□ breaking-change 评分（0.90-0.95）
□ 旧配置迁移路径说明
□ CHANGELOG "[BREAKING]" 标注
```

### 3.3 权限模型变更
```
□ 替代方案是否完备
□ 旧配置迁移路径
□ 破坏性影响 PR 描述说明
□ 是否需要 changelog/升级指引

| 收紧权限 | 低风险 | 重点：向后兼容 |
| 放宽权限 | 高风险 | 重点：滥用风险 |
| 简化模型 | 中风险 | 重点：功能完整性 |
```

### 3.4 文档同步（quick 模式强制项）
```
□ README 中是否提及被移除的命令/配置
□ _GM_COMMAND_NAMES 与实际命令同步
□ 权限变更时帮助文本/错误提示同步
```

---

## 四、Issue 分析规范

### 4.1 命令名验证
```
引用任何命令名之前 → 必须用 grep 验证
禁止：未经代码验证直接引用命令名
```

### 4.2 标签置信度
```
owner-driven enhancement → 降低 needs-discussion 置信度
命令合并 → 考虑添加 cleanup/deprecation 标签
breaking-change → 必须提供具体处置建议
```

### 4.3 重复检测
```
命令合并类 → 检查底层实现是否相同（grep _recall_user_recent_msgs 等）
主动优化建议类 → 无需深度冲突检测
```

---

## 五、项目 Pattern 总结

### 5.1 AstrBot 命令注册七处同步
```
1. main.py handler
2. _GM_COMMAND_NAMES 元组
3. README/帮助文本
4. CHANGELOG
5. metadata.yaml
6. i18n 文件
7. 错误提示文本
```

### 5.2 权限检查架构
```
_is_authorized() → _is_group_admin_or_owner()
                     ↓
         has_*_admin_rights() × 3
```
分散 `is_plugin_admin` → 统一 `_is_authorized()` 是该仓库标准化路径。

### 5.3 配置分离模式
```
_conf_schema.json (schema 定义)
config.json (用户配置)
分离校验 + 默认值管理
```

---

## 六、通用经验

1. **quick 不代表浅层** — 文档同步检查是 quick 模式默认必检项
2. **命令移除仅删 handler 不够** — 必须显式验证 `_GM_COMMAND_NAMES`
3. **硬编码替代可配置项** — 显式评估 breaking-change，不默认无影响
4. **增量审查** — 合并提交前验证原 PR 是否已审查
5. **Issue 分析命令名** — 必须先 grep 验证再引用
6. **breaking-change 评分** — 必须附带具体处置建议，不止于评分

---

*下次审查时优先查阅此文件对应章节*
