from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models import Character, InventoryItem, StorageType
from backend.game.combat import CombatEngine
from backend.game.data_loader import DataLoader
import random

class PVPSystem:
    """PVP系统"""
    
    # PK值衰减：每小时减少10点
    PK_DECAY_PER_HOUR = 10
    
    # 红名阈值
    RED_NAME_THRESHOLD = 100
    
    @classmethod
    async def attack_player(cls, attacker_id: int, defender_id: int, db: AsyncSession) -> dict:
        """玩家攻击玩家"""
        attacker = await db.get(Character, attacker_id)
        defender = await db.get(Character, defender_id)
        
        if not attacker or not defender:
            return {"success": False, "error": "玩家不存在"}
        
        # 检查是否在安全区
        if attacker.map_id == "main_city":
            return {"success": False, "error": "安全区内禁止PK"}
        
        # 获取战斗属性
        attacker_stats = await cls._get_stats(attacker, db)
        defender_stats = await cls._get_stats(defender, db)
        
        # 战斗
        result = CombatEngine.pvp_combat(attacker_stats, defender_stats)
        
        # 处理结果
        winner_id = result["winner_id"]
        loser_id = result["loser_id"]
        
        winner = attacker if winner_id == attacker_id else defender
        loser = attacker if loser_id == attacker_id else defender
        
        # 增加PK值
        if winner_id == attacker_id:
            attacker.pk_value += 50
        
        # 掉落物品
        drops = await cls._handle_death_drops(loser, db)
        
        await db.commit()
        
        return {
            "success": True,
            "winner_id": winner_id,
            "loser_id": loser_id,
            "logs": result["logs"],
            "drops": drops,
            "pk_value": attacker.pk_value
        }
    
    @classmethod
    async def _get_stats(cls, char: Character, db: AsyncSession) -> dict:
        """获取战斗属性"""
        from backend.game.engine import GameEngine
        return await GameEngine._get_combat_stats(char, db)
    
    @classmethod
    async def _handle_death_drops(cls, loser: Character, db: AsyncSession) -> List[dict]:
        """处理死亡掉落"""
        drops = []
        
        # 红名掉落更多
        drop_rate = 0.3 if loser.pk_value >= cls.RED_NAME_THRESHOLD else 0.1
        
        # 获取背包物品
        from sqlalchemy import select
        result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.character_id == loser.id,
                InventoryItem.storage_type == StorageType.INVENTORY
            )
        )
        items = result.scalars().all()
        
        for item in items:
            if random.random() < drop_rate:
                drops.append({
                    "item_id": item.item_id,
                    "quality": item.quality,
                    "quantity": item.quantity
                })
                await db.delete(item)
        
        return drops
    
    @classmethod
    def is_red_name(cls, pk_value: int) -> bool:
        """是否红名"""
        return pk_value >= cls.RED_NAME_THRESHOLD
    
    @classmethod
    def get_name_color(cls, pk_value: int) -> str:
        """获取名字颜色"""
        if pk_value >= 200:
            return "#ff0000"  # 深红
        elif pk_value >= cls.RED_NAME_THRESHOLD:
            return "#ff6666"  # 浅红
        elif pk_value >= 50:
            return "#ffff00"  # 黄名
        else:
            return "#ffffff"  # 白名