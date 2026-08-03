import asyncio
from astrbot.api import star, logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.message_components import At, Plain, Reply
from typing import Optional, Union, List, Dict, Any

class GroupAdminPlugin(star.Star):
    """AstrBot 群管插件 - 提供完整的群组管理功能"""
    
    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        self.context = context
        
    @filter.command("禁言")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def mute_command(self, event: AstrMessageEvent, args: List[str]):
        """禁言指定群成员
        
        用法: /禁言 @某人 分钟数
        示例: /禁言 @张三 1440 (代表禁言1天)
        """
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return
            
        # 解析@的目标
        at_segment = None
        for segment in event.message_obj.message:
            if isinstance(segment, At):
                at_segment = segment
                break
                
        if not at_segment:
            yield event.plain_result("请使用 @ 提及要禁言的成员")
            return
            
        target_qq = at_segment.qq
        
        # 解析时长（统一按分钟）
        duration_minutes = 10  # 默认10分钟
        if args:
            try:
                duration_minutes = int(args[0])
            except ValueError:
                yield event.plain_result("时长格式错误: 请输入纯数字的分钟数\n例如: 1440 (代表1天)")
                return
            
        duration_seconds = duration_minutes * 60
            
        # 执行禁言
        try:
            await self._mute_user(event.message_obj.group_id, target_qq, duration_seconds)
            yield event.plain_result(f"已禁言 @ qq={target_qq} {duration_minutes} 分钟")
        except Exception as e:
            yield event.plain_result(f"禁言失败: {str(e)}")
    
    @filter.command("解禁")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def unmute_command(self, event: AstrMessageEvent, args: List[str]):
        """解除禁言
        
        用法: /解禁 @某人
        """
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return
            
        at_segment = None
        for segment in event.message_obj.message:
            if isinstance(segment, At):
                at_segment = segment
                break
                
        if not at_segment:
            yield event.plain_result("请使用 @ 提及要解禁的成员")
            return
            
        target_qq = at_segment.qq
        
        try:
            await self._unmute_user(event.message_obj.group_id, target_qq)
            yield event.plain_result(f"已解禁 @ qq={target_qq}")
        except Exception as e:
            yield event.plain_result(f"解禁失败: {str(e)}")
    
    @filter.command("踢")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def kick_command(self, event: AstrMessageEvent, args: List[str]):
        """踢出群成员
        
        用法: /踢 @某人
        """
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return
            
        at_segment = None
        for segment in event.message_obj.message:
            if isinstance(segment, At):
                at_segment = segment
                break
                
        if not at_segment:
            yield event.plain_result("请使用 @ 提及要踢出的成员")
            return
            
        target_qq = at_segment.qq
        
        try:
            await self._kick_user(event.message_obj.group_id, target_qq)
            yield event.plain_result(f"已踢出 @ qq={target_qq}")
        except Exception as e:
            yield event.plain_result(f"踢出失败: {str(e)}")
    
    @filter.command("头衔")
@filter.permission_type(filter.PermissionType.ADMIN)
    async def set_title_command(self, event: AstrMessageEvent, args: List[str]):
        """设置群成员专属头衔
        
        用法: /头衔 @某人 头衔名称
        示例: /头衔 @张三 管理员
        """
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return
            
        if len(args) < 1:
            yield event.plain_result("用法: /头衔 @某人 头衔名称")
            return
            
        at_segment = None
        for segment in event.message_obj.message:
            if isinstance(segment, At):
                at_segment = segment
                break
                
        if not at_segment:
            yield event.plain_result("请使用 @ 提及要设置头衔的成员")
            return
            
        target_qq = at_segment.qq
        title = args[0]  # 假设头衔是第一个纯文本参数
        
        try:
            await self._set_special_title(event.message_obj.group_id, target_qq, title)
            yield event.plain_result(f"已设置 @ qq={target_qq} 的头衔为: {title}")
        except Exception as e:
            yield event.plain_result(f"设置头衔失败: {str(e)}")
    
    @filter.command("设精华")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def set_essence_command(self, event: AstrMessageEvent, args: List[str]):
        """将消息设为精华消息
        
        用法: /设精华 (需引用消息)
        """
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return
            
        reply_segment = None
        for segment in event.message_obj.message:
            if isinstance(segment, Reply):
                reply_segment = segment
                break
                
        if not reply_segment:
            yield event.plain_result("请引用一条消息来设为精华")
            return
            
        message_id = reply_segment.id
        
        try:
            await self._set_essence_message(event.message_obj.group_id, message_id)
            yield event.plain_result(f"已将消息设为精华")
        except Exception as e:
            yield event.plain_result(f"设为精华失败: {str(e)}")
    
    @filter.command("设群昵称")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def set_group_card_command(self, event: AstrMessageEvent, args: List[str]):
        """设置群成员的群昵称
        
        用法: /设群昵称 @某人 新昵称
        """
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return
            
        if len(args) < 1:
            yield event.plain_result("用法: /设群昵称 @某人 新昵称")
            return
            
        at_segment = None
        for segment in event.message_obj.message:
            if isinstance(segment, At):
                at_segment = segment
                break
                
        if not at_segment:
            yield event.plain_result("请使用 @ 提及要设置群昵称的成员")
            return
            
        target_qq = at_segment.qq
        new_card = args[0]
        
        try:
            await self._set_group_card(event.message_obj.group_id, target_qq, new_card)
            yield event.plain_result(f"已设置 @ qq={target_qq} 的群昵称为: {new_card}")
        except Exception as e:
            yield event.plain_result(f"设置群昵称失败: {str(e)}")
    
    @filter.command("改昵称")
    async def set_my_group_card_command(self, event: AstrMessageEvent, args: List[str]):
        """设置自己的群昵称
        
        用法: /改昵称 新昵称
        """
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return
            
        if len(args) < 1:
            yield event.plain_result("用法: /改昵称 新昵称")
            return
            
        new_card = args[0]
        sender_qq = event.message_obj.sender.user_id
        
        try:
            await self._set_group_card(event.message_obj.group_id, sender_qq, new_card)
            yield event.plain_result(f"已设置你的群昵称为: {new_card}")
        except Exception as e:
            yield event.plain_result(f"设置群昵称失败: {str(e)}")
    
    @filter.command("撤回")
@filter.permission_type(filter.PermissionType.ADMIN)
    async def recall_command(self, event: AstrMessageEvent, args: List[str]):
        """撤回引用的消息
        
        用法: /撤回 (需引用消息)
        """
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return
            
        reply_segment = None
        for segment in event.message_obj.message:
            if isinstance(segment, Reply):
                reply_segment = segment
                break
                
        if not reply_segment:
            yield event.plain_result("请引用一条要撤回的消息")
            return
            
        message_id = reply_segment.id
        
        try:
            await self._recall_message(event.message_obj.group_id, message_id)
            yield event.plain_result(f"已撤回该消息")
        except Exception as e:
            yield event.plain_result(f"撤回失败: {str(e)}")
    
    @filter.command("禁我")
    async def mute_myself_command(self, event: AstrMessageEvent, args: List[str]):
        """禁言自己
        
        用法: /禁我 分钟数
        示例: /禁我 1440 (代表禁言自己1天)
        """
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return
            
        duration_minutes = 10  # 默认10分钟
        if args:
            try:
                duration_minutes = int(args[0])
            except ValueError:
                yield event.plain_result("时长格式错误: 请输入纯数字的分钟数\n例如: 1440 (代表1天)")
                return
            
        duration_seconds = duration_minutes * 60
        sender_qq = event.message_obj.sender.user_id
        
        try:
            await self._mute_user(event.message_obj.group_id, sender_qq, duration_seconds)
            yield event.plain_result(f"已禁言自己 {duration_minutes} 分钟")
        except Exception as e:
            yield event.plain_result(f"禁言失败: {str(e)}")
    
    # 以下是内部方法，实现具体的群管操作
    async def _mute_user(self, group_id: str, user_id: str, duration: int):
        """禁言用户"""
        params = {
            "group_id": group_id,
            "user_id": user_id,
            "duration": duration
        }
        await self.context.platform.call_api(
            platform="qq",
            api="set_group_ban",
            **params
        )
    
    async def _unmute_user(self, group_id: str, user_id: str):
        """解除禁言"""
        await self._mute_user(group_id, user_id, 0)
    
    async def _kick_user(self, group_id: str, user_id: str):
        """踢出群成员"""
        params = {
            "group_id": group_id,
            "user_id": user_id,
            "reject_add_request": False
        }
        await self.context.platform.call_api(
            platform="qq",
            api="set_group_kick",
            **params
        )
    
    async def _set_special_title(self, group_id: str, user_id: str, title: str):
        """设置专属头衔"""
        params = {
            "group_id": group_id,
            "user_id": user_id,
            "special_title": title,
            "duration": -1
        }
        await self.context.platform.call_api(
            platform="qq",
            api="set_group_special_title",
            **params
        )
    
    async def _set_essence_message(self, group_id: str, message_id: str):
        """设为精华消息"""
        params = {
            "group_id": group_id,
            "message_id": message_id
        }
        await self.context.platform.call_api(
            platform="qq",
            api="set_essence_message",
            **params
        )
    
    async def _set_group_card(self, group_id: str, user_id: str, card: str):
        """设置群昵称"""
        params = {
            "group_id": group_id,
            "user_id": user_id,
            "card": card
        }
        await self.context.platform.call_api(
            platform="qq",
            api="set_group_card",
            **params
        )
    
    async def _recall_message(self, group_id: str, message_id: str):
        """撤回消息"""
params = {
            "message_id": message_id
        }
        await self.context.platform.call_api(
            platform="qq",
            api="delete_msg",
            **params
        )

