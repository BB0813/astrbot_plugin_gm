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
from datetime import datetime
from pathlib import Path
import re

@register(
    "group_admin",
    "YourName",
    "QQ群群管插件",
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
        self.config = self.load_config()

    def _get_default_config(self) -> dict:
        return {
            "show_recall_notice": True,
            "reject_re_add": False,
            "plugin_admins": [],
            "groups": {}
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
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")

    def is_plugin_admin(self, user_id: str) -> bool:
        return str(user_id) in [str(uid) for uid in self.config.get("plugin_admins", [])]

    def _is_group_owner(self, raw: dict) -> bool:
        role = raw.get("sender", {}).get("role", "")
        return role == "owner"

    def _is_group_admin(self, raw: dict) -> bool:
        role = raw.get("sender", {}).get("role", "")
        return role in {"admin", "owner"}

    def _get_raw_message(self, event: AstrMessageEvent):
        """Robustly extract the raw message dict from the event."""
        # Try event.message_obj.raw_message first (common pattern in plugins)
        try:
            return event.message_obj.raw_message
        except Exception:
            pass
        # Fallback to event.raw_message if present
        return getattr(event, "raw_message", None)

    def _parse_qq(self, text: str) -> str:
        match = re.search(r"(\d{5,12})", text)
        return match.group(1) if match else ""

    def _extract_at_qq(self, raw: dict) -> str:
        """Extract QQ number from At components in the raw message."""
        if not raw:
            return ""
        message_list = raw.get("message", [])
        for seg in message_list:
            if isinstance(seg, dict) and seg.get("type") == "at":
                qq = str(seg.get("data", {}).get("qq", ""))
                if qq:
                    return qq
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

    async def _recall_message(self, event: AstrMessageEvent, message_id: str):
        return await self._execute_action(event, "recall", message_id=message_id)

    async def _set_group_admin(self, event: AstrMessageEvent, group_id: str, qq: str, enable: bool):
        return await self._execute_action(event, "set_group_admin", group_id=group_id, user_id=qq, enable=enable)

    async def _set_group_title(self, event: AstrMessageEvent, group_id: str, qq: str, title: str):
        return await self._execute_action(event, "set_group_special_title", group_id=group_id, user_id=qq, special_title=title)

    async def _set_essence(self, event: AstrMessageEvent, message_id: str):
        return await self._execute_action(event, "set_essence", message_id=message_id)

    async def _mute_member(self, event: AstrMessageEvent, group_id: str, qq: str, duration: int):
        return await self._execute_action(event, "mute", group_id=group_id, user_id=qq, duration=duration)

    async def _unmute_member(self, event: AstrMessageEvent, group_id: str, qq: str):
        return await self._execute_action(event, "unmute", group_id=group_id, user_id=qq)

    async def _kick_member(self, event: AstrMessageEvent, group_id: str, qq: str):
        return await self._execute_action(event, "kick", group_id=group_id, user_id=qq)

    @filter.command("设管", "设置插件管理员")
    async def add_plugin_admin(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        # only plugin admin or group owner can set plugin admins
        if not self.is_plugin_admin(str(raw.get("user_id"))) and not self._is_group_owner(raw):
            yield event.plain_result("只有插件管理员或群主可执行此操作")
            return
        qq = self._parse_qq(target or str(raw.get("user_id")))
        if not qq:
            yield event.plain_result("请指定要设置为插件管理员的QQ号")
            return
        if qq in self.config.get("plugin_admins", []):
            yield event.plain_result(f"{qq} 已经是插件管理员")
            return
        self.config["plugin_admins"].append(qq)
        self.save_config()
        yield event.plain_result(f"已将 {qq} 设为插件管理员")

    @filter.command("取管", "移除插件管理员")
    async def remove_plugin_admin(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        if not self.is_plugin_admin(str(raw.get("user_id"))) and not self._is_group_owner(raw):
            yield event.plain_result("只有插件管理员或群主可执行此操作")
            return
        qq = self._parse_qq(target or str(raw.get("user_id")))
        if not qq:
            yield event.plain_result("请指定要移除的插件管理员QQ号")
            return
        if qq not in self.config.get("plugin_admins", []):
            yield event.plain_result(f"{qq} 不是插件管理员")
            return
        self.config["plugin_admins"].remove(qq)
        self.save_config()
        yield event.plain_result(f"已移除 {qq} 的插件管理员身份")

    @filter.command("设管理", "设置群管理员")
    async def set_group_admin_cmd(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        group_id = str(raw.get("group_id"))
        qq = self._parse_qq(target or str(raw.get("user_id")))
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
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        group_id = str(raw.get("group_id"))
        qq = self._parse_qq(target or str(raw.get("user_id")))
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
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        group_id = str(raw.get("group_id"))
        if not title:
            yield event.plain_result("请提供群头衔内容")
            return
        qq = self._parse_qq(qq or str(raw.get("user_id")))
        if not qq:
            yield event.plain_result("请指定要设置头衔的QQ号")
            return
        ok = await self._set_group_title(event, group_id, qq, title)
        yield event.plain_result("设置头衔成功" if ok else "设置头衔失败")

    @filter.command("取消头衔", "取消群头衔")
    async def unset_group_title_cmd(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        group_id = str(raw.get("group_id"))
        qq = self._parse_qq(target or str(raw.get("user_id")))
        if not qq:
            yield event.plain_result("请指定要取消头衔的QQ号")
            return
        ok = await self._set_group_title(event, group_id, qq, "")
        yield event.plain_result("取消头衔成功" if ok else "取消头衔失败")

    @filter.command("禁言", "禁言成员")
    async def mute_cmd(self, event: AstrMessageEvent, target: str = "", minutes: int = 10):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        if not self.is_plugin_admin(str(raw.get("user_id"))) and not self._is_group_admin(raw):
            yield event.plain_result("只有插件管理员或群管理员可执行此操作")
            return
        group_id = str(raw.get("group_id"))
        # Extract QQ from At components first, then fall back to target text
        qq = self._extract_at_qq(raw) or self._parse_qq(target)
        if not qq:
            yield event.plain_result("请指定要禁言的QQ号")
            return
        # Parse minutes from target text if it contains only digits
        target_stripped = target.strip()
        if target_stripped.isdigit():
            try:
                minutes = int(target_stripped)
            except ValueError:
                pass
        ok = await self._mute_member(event, group_id, qq, minutes)
        yield event.plain_result("禁言成功" if ok else "禁言失败")

    @filter.command("解禁", "解除禁言")
    async def unmute_cmd(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        if not self.is_plugin_admin(str(raw.get("user_id"))) and not self._is_group_admin(raw):
            yield event.plain_result("只有插件管理员或群管理员可执行此操作")
            return
        group_id = str(raw.get("group_id"))
        qq = self._parse_qq(target or str(raw.get("user_id")))
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
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        group_id = str(raw.get("group_id"))
        qq = self._parse_qq(target or str(raw.get("user_id")))
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

    @filter.command("status", "查看插件配置")
    async def status_cmd(self, event: AstrMessageEvent):
        plugin_admins = self.config.get("plugin_admins", [])
        lines = [
            f"show_recall_notice: {self.config.get('show_recall_notice', True)}",
            f"reject_re_add: {self.config.get('reject_re_add', False)}",
            f"plugin_admins: {', '.join(plugin_admins) if plugin_admins else '空'}"
        ]
        yield event.plain_result("插件配置：\n" + "\n".join(lines))

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_group_event(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not isinstance(raw, dict):
            return
        if raw.get("post_type") != "notice":
            return
        if raw.get("notice_type") == "group_increase":
            group_id = str(raw.get("group_id"))
            if self.config.get("groups", {}).get(group_id, {}).get("welcome_enabled", False):
                welcome = self.config["groups"][group_id].get("welcome_message", "欢迎 {at} 加入本群！")
                content = welcome.replace("{at}", f"@{raw.get('user_id')}")
                await self._send(event, self._build_text(content))
