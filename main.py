from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain, At

try:
    from astrbot.api.message import MessageChain
except ImportError:
    try:
        from astrbot.api.message_components import MessageChain
    except ImportError:
        MessageChain = None

import json
import os
from pathlib import Path
import re
import time


def _parse_qq_list(text: str) -> list:
    """从文本中提取所有合法的QQ号（5-12位数字）。"""
    return list({m.group(1) for m in re.finditer(r"(\d{5,12})", text or "")})


@register(
    "group_admin",
    "YourName",
    "QQ群群管插件 - 禁言/踢人/头衔/精华/撤回/群公告/关键词撤回/违规检测/排名",
    "2.4.0",
    "https://github.com/mjy1113451/astrbot_plugin_gm"
)
class GroupAdminPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        try:
            from astrbot.api.star import StarTools
            self.data_dir = StarTools.get_data_dir() / "group_admin"
        except ImportError:
            self.data_dir = Path(os.getcwd()) / "data" / "group_admin"

        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)

        self.config_path = self.data_dir / "config.json"
        self.stats_path = self.data_dir / "stats.json"
        self.reports_path = self.data_dir / "reports.json"
        self.config = self.load_config()
        self.stats = self.load_json(self.stats_path, {"groups": {}})
        self.reports = self.load_json(self.reports_path, {"pending": []})

    # ===================== 通用 IO =====================

    def load_json(self, path: Path, default):
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载 {path.name} 失败: {e}")
        return default

    def save_json(self, path: Path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存 {path.name} 失败: {e}")

    def _get_default_config(self) -> dict:
        return {
            "show_recall_notice": True,
            "reject_re_add": False,
            "plugin_admins": [],
            "groups": {},
            # 按操作类型分别配置管理员（#34 权限系统重构）
            "title_admins": [],
            "group_admin_admins": [],
            "kick_admins": [],
            # 全局默认 #26 按群独立管理员
            "group_admins": {},
            # 关键词自动撤回（#46）
            "auto_recall_keywords": [],
            "auto_recall_enabled_groups": [],
            # 违规检测（#19）
            "violation_keywords": [],
            "violation_action": "none",
            "violation_mute_minutes": 10,
            "violation_enabled_groups": [],
            # 举报（#21）
            "report_notify_admins": [],
            # 群公告与排名（#16, #29）
            "rank_top_n": 10,
            # 加群请求关键词同意（#27 增强）
            "join_approve_keywords": [],
            "join_notify_admins": [],
            # 加群申请群内提醒（#57）
            "join_request_notify_in_group": False,
            "pending_join_requests": {},
        }

    def load_config(self) -> dict:
        default_config = self._get_default_config()
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    for key, value in default_config.items():
                        if key not in saved:
                            saved[key] = value
                    if "groups" not in saved:
                        saved["groups"] = {}
                    return saved
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
                return default_config
        return default_config

    def save_config(self):
        self.save_json(self.config_path, self.config)

    def save_stats(self):
        self.save_json(self.stats_path, self.stats)

    def save_reports(self):
        self.save_json(self.reports_path, self.reports)

    # ===================== 工具方法 =====================

    def is_plugin_admin(self, user_id: str) -> bool:
        return str(user_id) in [str(uid) for uid in self.config.get("plugin_admins", [])]

    def _is_group_owner(self, raw: dict) -> bool:
        role = raw.get("sender", {}).get("role", "")
        return role == "owner"

    def _is_group_admin(self, raw: dict) -> bool:
        role = raw.get("sender", {}).get("role", "")
        return role in {"admin", "owner"}

    def _is_group_admin_or_owner(self, raw: dict) -> bool:
        return self._is_group_admin(raw) or self._is_group_owner(raw)

    def has_title_admin_rights(self, user_id: str, group_id: str, raw: dict) -> bool:
        uid = str(user_id)
        if self.is_plugin_admin(uid):
            return True
        title_admins = [str(x) for x in self.config.get("title_admins", [])]
        if uid in title_admins:
            return True
        if self._is_group_admin_or_owner(raw):
            return True
        return False

    def has_kick_admin_rights(self, user_id: str, group_id: str, raw: dict) -> bool:
        uid = str(user_id)
        if self.is_plugin_admin(uid):
            return True
        kick_admins = [str(x) for x in self.config.get("kick_admins", [])]
        if uid in kick_admins:
            return True
        if self._is_group_admin_or_owner(raw):
            return True
        return False

    def has_group_admin_rights(self, user_id: str, group_id: str, raw: dict) -> bool:
        uid = str(user_id)
        if self.is_plugin_admin(uid):
            return True
        ga_admins = [str(x) for x in self.config.get("group_admin_admins", [])]
        if uid in ga_admins:
            return True
        if self._is_group_admin_or_owner(raw):
            return True
        return False

    def _get_raw_message(self, event: AstrMessageEvent):
        """Robustly extract the raw message dict from the event."""
        try:
            return event.message_obj.raw_message
        except Exception:
            pass
        return getattr(event, "raw_message", None)

    def _parse_qq(self, text: str) -> str:
        nums = _parse_qq_list(text)
        return nums[0] if nums else ""

    def _extract_at_qq(self, raw: dict) -> str:
        """Extract QQ number from At components in the raw message."""
        if not raw:
            return ""
        for seg in raw.get("message", []):
            if isinstance(seg, dict) and seg.get("type") == "at":
                qq = str(seg.get("data", {}).get("qq", ""))
                if qq:
                    return qq
        return ""

    def _extract_image_url(self, event: AstrMessageEvent) -> str:
        """从 event 的消息链中提取第一张图片的 URL。"""
        try:
            chain = getattr(event.message_obj, "message", None) or getattr(event, "message", None)
            if chain is None:
                return ""
            # AstrBot 的 message chain 可能是 MessageChain 或 list
            if hasattr(chain, "chain"):
                segs = chain.chain
            elif isinstance(chain, (list, tuple)):
                segs = chain
            else:
                segs = []
            for seg in segs:
                # 兼容不同的 Image 表示
                if isinstance(seg, dict):
                    if seg.get("type") == "image":
                        return seg.get("data", {}).get("url") or seg.get("data", {}).get("file", "")
                    continue
                if getattr(seg, "type", None) == "image":
                    return getattr(seg, "url", "") or getattr(seg, "file", "")
        except Exception as e:
            logger.error(f"提取图片URL失败: {e}")
        return ""

    def _build_text(self, text: str, at: str = None):
        if at:
            return [Plain(text), At(qq=at)] if text else [At(qq=at)]
        return [Plain(text)]

    async def _send(self, event: AstrMessageEvent, message_list):
        try:
            if hasattr(event, "send"):
                if MessageChain is not None:
                    await event.send(MessageChain(message_list))
                else:
                    await event.send(message_list)
                return True
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
        return False

    async def _execute_action(self, event: AstrMessageEvent, action: str, **params):
        handler = getattr(self.context, action, None)
        if callable(handler):
            try:
                return await handler(**params)
            except Exception as e:
                logger.error(f"调用 {action} 失败: {e}")
        if hasattr(event, action):
            handler = getattr(event, action)
            if callable(handler):
                try:
                    return await handler(**params)
                except Exception as e:
                    logger.error(f"调用 event.{action} 失败: {e}")
        return False

    def _get_reply_id(self, event: AstrMessageEvent):
        return getattr(event.message_obj, "reply_id", None) or getattr(event.message_obj, "quote_id", None)

    # ===================== OneBot API 封装 =====================

    async def _recall_message(self, event: AstrMessageEvent, message_id: str):
        return await self._execute_action(event, "recall", message_id=message_id)

    async def _set_group_admin(self, event: AstrMessageEvent, group_id: str, qq: str, enable: bool):
        return await self._execute_action(event, "set_group_admin", group_id=group_id, user_id=qq, enable=enable)

    async def _set_group_title(self, event: AstrMessageEvent, group_id: str, qq: str, title: str):
        return await self._execute_action(event, "set_group_special_title",
                                          group_id=group_id, user_id=qq, special_title=title)

    async def _set_group_card(self, event: AstrMessageEvent, group_id: str, qq: str, card: str):
        return await self._execute_action(event, "set_group_card",
                                          group_id=group_id, user_id=qq, card=card)

    async def _set_essence(self, event: AstrMessageEvent, message_id: str):
        return await self._execute_action(event, "set_essence", message_id=message_id)

    async def _mute_member(self, event: AstrMessageEvent, group_id: str, qq: str, duration_seconds: int):
        return await self._execute_action(event, "set_group_ban",
                                          group_id=group_id, user_id=qq, duration=duration_seconds)

    async def _unmute_member(self, event: AstrMessageEvent, group_id: str, qq: str):
        return await self._execute_action(event, "set_group_ban",
                                          group_id=group_id, user_id=qq, duration=0)

    async def _kick_member(self, event: AstrMessageEvent, group_id: str, qq: str):
        return await self._execute_action(event, "kick", group_id=group_id, user_id=qq)

    async def _set_group_avatar(self, event: AstrMessageEvent, group_id: str, file: str):
        """修改群头像，file 可以是 URL 或本地路径或 base64。"""
        return await self._execute_action(event, "set_group_portrait",
                                          group_id=group_id, file=file)

    async def _handle_group_request(self, event: AstrMessageEvent, flag: str, approve: bool, reason: str = ""):
        return await self._execute_action(event, "handle_group_request",
                                          flag=flag, approve=approve, reason=reason)

    # ===================== 消息收发辅助 =====================

    async def _send_private_msg(self, user_id: str, content: str):
        """向指定QQ号发送私聊消息（通过 context）。"""
        if hasattr(self.context, "send_private_msg"):
            try:
                return await self.context.send_private_msg(user_id=user_id, message=content)
            except Exception as e:
                logger.error(f"发送私聊失败: {e}")
        return False

    async def _send_group_text(self, event: AstrMessageEvent, group_id: str, text: str):
        """向指定群发送纯文本消息，返回 message_id（用于后续引用回复关联）。"""
        try:
            if hasattr(self.context, "send_group_msg"):
                # AstrBot 标准方法：send_group_msg(group_id=, message=)
                result = await self.context.send_group_msg(group_id=int(group_id), message=text)
                # 返回值可能直接是 message_id，也可能是含 message_id 的 dict
                if isinstance(result, dict):
                    return str(result.get("message_id") or result.get("data", {}).get("message_id", ""))
                return str(result) if result else ""
            # 回退：使用 _send 但拿不到 message_id
            await self._send(event, [Plain(text)])
        except Exception as e:
            logger.error(f"发送群消息失败: {e}")
        return ""

    async def _get_user_nickname(self, event: AstrMessageEvent, user_id: str) -> str:
        """获取用户昵称（通过 OneBot get_stranger_info API）。"""
        try:
            handler = getattr(self.context, "get_stranger_info", None)
            if callable(handler):
                info = await handler(user_id=int(user_id))
                if isinstance(info, dict):
                    return info.get("nickname") or info.get("data", {}).get("nickname", user_id)
                if hasattr(info, "nickname"):
                    return info.nickname
        except Exception as e:
            logger.error(f"获取昵称失败: {e}")
        return user_id

    async def _notify_admins(self, text: str):
        """向 join_notify_admins 配置的管理员发送私聊通知。"""
        for admin_id in self.config.get("join_notify_admins", []) or []:
            await self._send_private_msg(str(admin_id), text)

    # ===================== 计数统计（#29） =====================

    def _increment_message_count(self, group_id: str, user_id: str):
        groups = self.stats.setdefault("groups", {})
        g = groups.setdefault(str(group_id), {"messages": {}})
        msgs = g.setdefault("messages", {})
        msgs[str(user_id)] = msgs.get(str(user_id), 0) + 1

    def get_rank(self, group_id: str, top_n: int) -> list:
        groups = self.stats.get("groups", {})
        msgs = groups.get(str(group_id), {}).get("messages", {})
        ranked = sorted(msgs.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:top_n]

    def reset_group_stats(self, group_id: str):
        self.stats.setdefault("groups", {})[str(group_id)] = {"messages": {}}
        self.save_stats()

    # ===================== 群管指令 =====================

    @filter.command("设管", "添加插件管理员（支持批量）")
    async def add_plugin_admin(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        qq_list = _parse_qq_list(target)
        # 也可从At组件提取
        at_qq = self._extract_at_qq(raw)
        if at_qq:
            qq_list.append(at_qq)
        qq_list = list({str(x) for x in qq_list if x})
        if not qq_list:
            yield event.plain_result("请提供QQ号，例如 /设管 123456 234567")
            return
        added = []
        for qq in qq_list:
            if qq not in [str(x) for x in self.config.get("plugin_admins", [])]:
                self.config.setdefault("plugin_admins", []).append(qq)
                added.append(qq)
        self.save_config()
        if added:
            yield event.plain_result(f"已添加插件管理员: {', '.join(added)}")
        else:
            yield event.plain_result("所列QQ号均已是插件管理员")

    @filter.command("取管", "移除插件管理员（支持批量）")
    async def remove_plugin_admin(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        qq_list = _parse_qq_list(target)
        qq_list = list({str(x) for x in qq_list if x})
        if not qq_list:
            yield event.plain_result("请提供QQ号，例如 /取管 123456")
            return
        removed = []
        for qq in qq_list:
            if qq in [str(x) for x in self.config.get("plugin_admins", [])]:
                self.config["plugin_admins"].remove(qq)
                removed.append(qq)
        self.save_config()
        if removed:
            yield event.plain_result(f"已移除插件管理员: {', '.join(removed)}")
        else:
            yield event.plain_result("所列QQ号均非插件管理员")

    @filter.command("添加插件管理", "按群独立添加插件管理员（批量）")
    async def add_group_admin(self, event: AstrMessageEvent, target: str = ""):
        """按群独立添加插件管理员（#26）。
        用法：/添加插件管理 123456 234567
        """
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        group_id = str(raw.get("group_id"))
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        qq_list = _parse_qq_list(target)
        qq_list = list({str(x) for x in qq_list if x})
        if not qq_list:
            yield event.plain_result("请提供QQ号，例如 /添加插件管理 123456 234567")
            return
        admins = self.config.setdefault("group_admins", {}).setdefault(group_id, [])
        added = []
        for qq in qq_list:
            if qq not in [str(x) for x in admins]:
                admins.append(qq)
                added.append(qq)
        self.save_config()
        if added:
            yield event.plain_result(f"已在群 {group_id} 添加管理员: {', '.join(added)}")
        else:
            yield event.plain_result("所列QQ号均已是本群管理员")

    @filter.command("删除插件管理", "按群独立移除插件管理员（批量）")
    async def remove_group_admin(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        group_id = str(raw.get("group_id"))
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        qq_list = _parse_qq_list(target)
        qq_list = list({str(x) for x in qq_list if x})
        if not qq_list:
            yield event.plain_result("请提供QQ号，例如 /删除插件管理 123456")
            return
        admins = self.config.get("group_admins", {}).get(group_id, [])
        removed = []
        for qq in qq_list:
            if qq in [str(x) for x in admins]:
                admins.remove(qq)
                removed.append(qq)
        self.save_config()
        if removed:
            yield event.plain_result(f"已在群 {group_id} 移除管理员: {', '.join(removed)}")
        else:
            yield event.plain_result("所列QQ号均非本群管理员")

    @filter.command("设管理", "设置群管理员")
    async def set_group_admin_cmd(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        group_id = str(raw.get("group_id"))
        if not self.has_group_admin_rights(str(raw.get("user_id")), group_id, raw):
            yield event.plain_result("只有插件管理员或群管理员可执行此操作")
            return
        qq = self._extract_at_qq(raw) or self._parse_qq(target)
        if not qq:
            yield event.plain_result("请指定要设置为群管理员的QQ号")
            return
        ok = await self._set_group_admin(event, group_id, qq, True)
        yield event.plain_result("设置群管理成功" if ok else "设置群管理失败")

    @filter.command("取消管理", "取消群管理员")
    async def unset_group_admin_cmd(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        group_id = str(raw.get("group_id"))
        if not self.has_group_admin_rights(str(raw.get("user_id")), group_id, raw):
            yield event.plain_result("只有插件管理员或群管理员可执行此操作")
            return
        qq = self._extract_at_qq(raw) or self._parse_qq(target)
        if not qq:
            yield event.plain_result("请指定要取消群管理员的QQ号")
            return
        ok = await self._set_group_admin(event, group_id, qq, False)
        yield event.plain_result("取消成功" if ok else "取消失败")

    @filter.command("头衔", "设置群头衔")
    async def set_group_title_cmd(self, event: AstrMessageEvent, qq: str = "", title: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self.has_title_admin_rights(sender_id, group_id, raw):
            yield event.plain_result("只有插件管理员、头衔管理员或群管理员可执行此操作")
            return
        if not title:
            yield event.plain_result("请提供群头衔内容")
            return
        target_qq = self._extract_at_qq(raw) or self._parse_qq(qq)
        if not target_qq:
            # 操作对象为空时，对发送者自身设置（允许群管理员自设头衔）
            target_qq = sender_id
        ok = await self._set_group_title(event, group_id, target_qq, title)
        yield event.plain_result("设置头衔成功" if ok else "设置头衔失败")

    @filter.command("取消头衔", "取消群头衔")
    async def unset_group_title_cmd(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self.has_title_admin_rights(sender_id, group_id, raw):
            yield event.plain_result("只有插件管理员、头衔管理员或群管理员可执行此操作")
            return
        target_qq = self._extract_at_qq(raw) or self._parse_qq(target) or sender_id
        ok = await self._set_group_title(event, group_id, target_qq, "")
        if not ok:
            # 部分 OneBot 实现不接受空字符串，回退使用空格占位符
            ok = await self._set_group_title(event, group_id, target_qq, " ")
        yield event.plain_result("取消头衔成功" if ok else "取消头衔失败")

    # #18: 别人昵称 - 设置他人的群昵称
    @filter.command("别人昵称", "设置他人群昵称（需要引用消息）")
    async def set_other_card_cmd(self, event: AstrMessageEvent, card: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self.has_group_admin_rights(sender_id, group_id, raw):
            yield event.plain_result("只有插件管理员或群管理员可执行此操作")
            return
        reply_id = self._get_reply_id(event)
        target_qq = self._extract_at_qq(raw)
        if not target_qq:
            yield event.plain_result("请通过 @某人 或引用该用户的消息来指定对象")
            return
        if not card:
            yield event.plain_result("请提供新昵称内容")
            return
        ok = await self._set_group_card(event, group_id, target_qq, card)
        yield event.plain_result(f"已将 {target_qq} 的群昵称设为 {card}" if ok else "设置群昵称失败")

    # #18: 改群昵称 - 设置自己的群昵称
    @filter.command("改群昵称", "设置自己的群昵称")
    async def set_self_card_cmd(self, event: AstrMessageEvent, card: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not card:
            yield event.plain_result("请提供新昵称内容")
            return
        ok = await self._set_group_card(event, group_id, sender_id, card)
        yield event.plain_result(f"已将你的群昵称设为 {card}" if ok else "设置群昵称失败")

    @filter.command("禁言", "禁言成员")
    async def mute_cmd(self, event: AstrMessageEvent, target: str = "", minutes: int = 10):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self.is_plugin_admin(sender_id) and not self._is_group_admin(raw):
            yield event.plain_result("只有插件管理员或群管理员可执行此操作")
            return
        qq = self._extract_at_qq(raw) or self._parse_qq(target)
        if not qq:
            yield event.plain_result("请指定要禁言的QQ号")
            return
        target_stripped = (target or "").strip()
        if target_stripped.isdigit():
            try:
                minutes = int(target_stripped)
            except ValueError:
                pass
        ok = await self._mute_member(event, group_id, qq, minutes * 60)
        yield event.plain_result(f"禁言成功（{minutes}分钟）" if ok else "禁言失败")

    @filter.command("解禁", "解除禁言")
    async def unmute_cmd(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        if not self.is_plugin_admin(sender_id) and not self._is_group_admin(raw):
            yield event.plain_result("只有插件管理员或群管理员可执行此操作")
            return
        group_id = str(raw.get("group_id"))
        qq = self._extract_at_qq(raw) or self._parse_qq(target)
        if not qq:
            yield event.plain_result("请指定要解禁的QQ号")
            return
        ok = await self._unmute_member(event, group_id, qq)
        yield event.plain_result("解禁成功" if ok else "解禁失败")

    @filter.command("踢", "踢出群成员")
    async def kick_cmd(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self.has_kick_admin_rights(sender_id, group_id, raw):
            yield event.plain_result("只有插件管理员、踢人管理员或群管理员可执行此操作")
            return
        qq = self._extract_at_qq(raw) or self._parse_qq(target)
        if not qq:
            yield event.plain_result("请指定要踢出的QQ号")
            return
        ok = await self._kick_member(event, group_id, qq)
        if ok and self.config.get("reject_re_add", False):
            await self._execute_action(event, "reject_add", group_id=group_id, user_id=qq)
        yield event.plain_result("踢出成功" if ok else "踢出失败")

    @filter.command("撤回", "引用消息撤回")
    async def recall_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        if not self._is_group_admin(raw) and not self._is_group_owner(raw):
            yield event.plain_result("只有群管理员或群主可执行此操作")
            return
        reply_id = self._get_reply_id(event)
        if not reply_id:
            yield event.plain_result("请引用一条消息后使用该指令")
            return
        ok = await self._recall_message(event, reply_id)
        if ok and self.config.get("show_recall_notice", True):
            await self._send(event, self._build_text("已撤回该消息"))
        yield event.plain_result("撤回成功" if ok else "撤回失败")

    @filter.command("设精", "设置精华消息")
    async def essence_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        if not self._is_group_admin(raw) and not self._is_group_owner(raw):
            yield event.plain_result("只有群管理员或群主可执行此操作")
            return
        reply_id = self._get_reply_id(event)
        if not reply_id:
            yield event.plain_result("请引用一条消息后使用该指令")
            return
        ok = await self._set_essence(event, reply_id)
        yield event.plain_result("设精成功" if ok else "设精失败")

    # #24: 改群头像
    @filter.command("改群头像", "引用图片回复即可修改群头像")
    async def set_group_avatar_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self._is_group_admin_or_owner(raw) and not self.is_plugin_admin(sender_id):
            yield event.plain_result("只有群管理员或插件管理员可执行此操作")
            return
        image_url = self._extract_image_url(event)
        if not image_url:
            yield event.plain_result("请引用一条图片消息，或在消息中附带图片")
            return
        ok = await self._set_group_avatar(event, group_id, image_url)
        yield event.plain_result("群头像已更新" if ok else "修改群头像失败")

    # #16: 群公告
    @filter.command("发群公告", "发送群公告")
    async def send_group_notice_cmd(self, event: AstrMessageEvent, content: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self._is_group_admin_or_owner(raw) and not self.is_plugin_admin(sender_id):
            yield event.plain_result("只有群管理员或插件管理员可执行此操作")
            return
        if not content:
            yield event.plain_result("请提供公告内容")
            return
        # 尝试通过 send_group_notice / _send_group_notice API
        ok = await self._execute_action(event, "_send_group_notice",
                                        group_id=group_id, content=content)
        if not ok:
            ok = await self._execute_action(event, "send_group_notice",
                                            group_id=group_id, content=content)
        if ok:
            yield event.plain_result("群公告已发布")
        else:
            # 退化为普通消息提示
            await self._send(event, [Plain(f"[群公告] {content}")])
            yield event.plain_result("当前框架不支持发群公告，已以普通消息发送")

    @filter.command("删群公告", "删除群公告")
    async def delete_group_notice_cmd(self, event: AstrMessageEvent, notice_id: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self._is_group_admin_or_owner(raw) and not self.is_plugin_admin(sender_id):
            yield event.plain_result("只有群管理员或插件管理员可执行此操作")
            return
        if not notice_id:
            yield event.plain_result("请提供要删除的公告ID，例如 /删群公告 12345")
            return
        ok = await self._execute_action(event, "_delete_group_notice",
                                        group_id=group_id, notice_id=notice_id)
        if not ok:
            ok = await self._execute_action(event, "delete_group_notice",
                                            group_id=group_id, notice_id=notice_id)
        yield event.plain_result("群公告已删除" if ok else "删除群公告失败")

    # #29: 鞭尸禁言 + 发言排名
    @filter.command("鞭尸", "长期禁言被@的人（29天23小时59分）")
    async def whip_corpse_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self._is_group_admin_or_owner(raw) and not self.is_plugin_admin(sender_id):
            yield event.plain_result("只有群管理员或插件管理员可执行此操作")
            return
        qq = self._extract_at_qq(raw)
        if not qq:
            yield event.plain_result("请 @要鞭尸的成员")
            return
        # 29天23小时59分 = 29*86400 + 23*3600 + 59*60 = 2591640 秒
        duration = 29 * 86400 + 23 * 3600 + 59 * 60
        ok = await self._mute_member(event, group_id, qq, duration)
        yield event.plain_result("已鞭尸" if ok else "鞭尸失败")

    @filter.command("排名", "查看本群发言排名")
    async def rank_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        group_id = str(raw.get("group_id"))
        top_n = int(self.config.get("rank_top_n", 10))
        ranked = self.get_rank(group_id, top_n)
        if not ranked:
            yield event.plain_result("暂无发言数据")
            return
        lines = [f"{i+1}. {qq} - {cnt}条" for i, (qq, cnt) in enumerate(ranked)]
        yield event.plain_result(f"本群发言排名（Top {len(ranked)}）：\n" + "\n".join(lines))

    @filter.command("清除数据", "清除本群发言计数")
    async def clear_rank_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self._is_group_admin_or_owner(raw) and not self.is_plugin_admin(sender_id):
            yield event.plain_result("只有群管理员或插件管理员可执行此操作")
            return
        self.reset_group_stats(group_id)
        yield event.plain_result("已清除本群发言数据，重新开始计数")

    # #21: 举报违规
    @filter.command("举报", "举报群成员违规行为（需要引用消息）")
    async def report_cmd(self, event: AstrMessageEvent, reason: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        group_id = str(raw.get("group_id"))
        reporter_id = str(raw.get("user_id"))
        target_qq = self._extract_at_qq(raw)
        if not target_qq:
            yield event.plain_result("请 @要举报的成员")
            return
        reply_id = self._get_reply_id(event)
        record = {
            "group_id": group_id,
            "reporter_id": reporter_id,
            "target_qq": target_qq,
            "reason": reason or "（未提供原因）",
            "message_id": reply_id,
            "time": int(time.time()),
        }
        self.reports.setdefault("pending", []).append(record)
        self.save_reports()
        # 通知管理员
        notify_admins = self.config.get("report_notify_admins", [])
        if notify_admins:
            text = (f"[举报] 群 {group_id}\n"
                    f"举报人: {reporter_id}\n"
                    f"被举报: {target_qq}\n"
                    f"原因: {record['reason']}")
            for admin_id in notify_admins:
                await self._send_private_msg(str(admin_id), text)
        yield event.plain_result("已提交举报，管理员会尽快处理")

    # ===================== 状态查看 =====================

    @filter.command("status", "查看插件配置")
    async def status_cmd(self, event: AstrMessageEvent):
        c = self.config
        lines = [
            f"show_recall_notice: {c.get('show_recall_notice', True)}",
            f"reject_re_add: {c.get('reject_re_add', False)}",
            f"plugin_admins: {', '.join(map(str, c.get('plugin_admins', []))) or '空'}",
            f"title_admins: {', '.join(map(str, c.get('title_admins', []))) or '空'}",
            f"group_admin_admins: {', '.join(map(str, c.get('group_admin_admins', []))) or '空'}",
            f"kick_admins: {', '.join(map(str, c.get('kick_admins', []))) or '空'}",
            f"auto_recall_keywords: {c.get('auto_recall_keywords', [])}",
            f"violation_keywords: {len(c.get('violation_keywords', []))} 个",
            f"rank_top_n: {c.get('rank_top_n', 10)}",
        ]
        yield event.plain_result("插件配置：\n" + "\n".join(lines))

    # ===================== 全消息监听 =====================

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """监听群消息：发言计数 + 违规检测。"""
        raw = self._get_raw_message(event)
        if not raw or not isinstance(raw, dict):
            return
        if raw.get("post_type") != "message":
            return
        group_id = str(raw.get("group_id"))
        user_id = str(raw.get("user_id"))
        # 跳过 bot 自身
        if str(raw.get("self_id", "")) == user_id:
            return

        # 发言计数（#29）
        self._increment_message_count(group_id, user_id)

        # 违规检测（#19）
        enabled_groups = self.config.get("violation_enabled_groups", [])
        if enabled_groups and group_id in [str(x) for x in enabled_groups]:
            keywords = self.config.get("violation_keywords", [])
            if keywords:
                msg_text = self._extract_text(raw)
                if msg_text and any(kw in msg_text for kw in keywords):
                    action = self.config.get("violation_action", "none")
                    if action == "mute":
                        minutes = int(self.config.get("violation_mute_minutes", 10))
                        await self._mute_member(event, group_id, user_id, minutes * 60)
                        yield event.plain_result(f"检测到违规内容，已禁言 {minutes} 分钟")
                    elif action == "recall":
                        msg_id = raw.get("message_id")
                        if msg_id:
                            await self._recall_message(event, str(msg_id))
                            yield event.plain_result("检测到违规内容，已撤回")

        # 加群申请引用回复处理（#57）
        reply_id = self._get_reply_id(event)
        if reply_id and self._is_group_admin_or_owner(raw) or (self.is_plugin_admin(user_id)):
            pending = self.config.get("pending_join_requests", {})
            info = pending.get(str(reply_id))
            if info:
                msg_text = self._extract_text(raw)
                if msg_text:
                    approve = "同意" in msg_text
                    deny = "拒绝" in msg_text
                    if approve or deny:
                        await self._handle_group_request(event, info["flag"], approve, "管理员审核")
                        result = "同意" if approve else "拒绝"
                        # 清理已处理的记录
                        del pending[str(reply_id)]
                        self.save_config()
                        yield event.plain_result(f"已{result} {info['user_id']} 的加群申请")
                        return

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_group_event(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not isinstance(raw, dict):
            return

        # 入群欢迎
        if raw.get("post_type") == "notice" and raw.get("notice_type") == "group_increase":
            group_id = str(raw.get("group_id"))
            if self.config.get("groups", {}).get(group_id, {}).get("welcome_enabled", False):
                welcome = self.config["groups"][group_id].get("welcome_message", "欢迎 {at} 加入本群！")
                content = welcome.replace("{at}", f"@{raw.get('user_id')}")
                await self._send(event, self._build_text(content))
            return

        # 加群请求处理（#27 合并 group_manager）
        if raw.get("post_type") == "request" and raw.get("request_type") == "group":
            group_id = str(raw.get("group_id"))
            user_id = str(raw.get("user_id"))
            flag = raw.get("flag", "")
            comment = raw.get("comment", "")
            enabled_groups = self.config.get("violation_enabled_groups", [])
            violation_keywords = self.config.get("violation_keywords", [])
            join_approve_keywords = self.config.get("join_approve_keywords", [])
            enabled = enabled_groups and group_id in [str(x) for x in enabled_groups]

            # 命中违禁词：拒绝 + 通知管理员
            if enabled and violation_keywords and any(kw in comment for kw in violation_keywords):
                await self._handle_group_request(event, flag, False, "触发违禁词")
                yield event.plain_result(f"已拒绝 {user_id} 的加群申请（含违禁词）")
                await self._notify_admins(
                    f"[加群请求] 已拒绝 {user_id}（群 {group_id}）\n"
                    f"验证消息: {comment}\n"
                    f"原因: 命中违禁词"
                )
                return

            # 命中关键词：同意 + 通知管理员
            if enabled and join_approve_keywords and any(kw in comment for kw in join_approve_keywords):
                await self._handle_group_request(event, flag, True, "命中关键词自动同意")
                yield event.plain_result(f"已同意 {user_id} 的加群申请（命中关键词）")
                await self._notify_admins(
                    f"[加群请求] 已同意 {user_id}（群 {group_id}）\n"
                    f"验证消息: {comment}\n"
                    f"原因: 命中关键词"
                )
                return

            # 群内提醒（#57）：发送申请消息到对应群聊，等待管理员引用回复同意/拒绝
            if self.config.get("join_request_notify_in_group", False):
                nickname = await self._get_user_nickname(event, user_id)
                notify_text = (
                    f"【有新人加群申请】\n"
                    f"qq昵称：{nickname}\n"
                    f"新人qq号：{user_id}\n"
                    f"加群验证消息：{comment or '（无）'}\n"
                    f"注：引用消息回复同意或拒绝"
                )
                # 暂存 flag 等待引用回复
                sent_id = await self._send_group_text(event, group_id, notify_text)
                if sent_id:
                    pending = self.config.setdefault("pending_join_requests", {})
                    pending[str(sent_id)] = {"flag": flag, "group_id": group_id, "user_id": user_id}
                    self.save_config()
                    await self._notify_admins(
                        f"[加群请求] {user_id} 申请加入群 {group_id}\n"
                        f"已在群内发送提醒，请管理员引用回复同意/拒绝"
                    )

    @filter.after_message_sent()
    async def after_message_sent(self, event: AstrMessageEvent):
        """Bot 自身发言后：若命中关键词配置则自动撤回（#46）。"""
        raw = self._get_raw_message(event)
        if not raw:
            return
        group_id = str(raw.get("group_id", ""))
        if not group_id:
            return
        enabled = self.config.get("auto_recall_enabled_groups", [])
        if not enabled:
            return
        if group_id not in [str(x) for x in enabled]:
            return
        keywords = self.config.get("auto_recall_keywords", [])
        if not keywords:
            return
        msg_text = self._extract_text(raw)
        if not msg_text:
            return
        if any(kw in msg_text for kw in keywords):
            msg_id = raw.get("message_id")
            if msg_id:
                await self._recall_message(event, str(msg_id))

    def _extract_text(self, raw: dict) -> str:
        parts = []
        for seg in raw.get("message", []) or []:
            if isinstance(seg, dict) and seg.get("type") == "text":
                parts.append(seg.get("data", {}).get("text", ""))
        return "".join(parts)