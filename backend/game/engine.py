from typing import Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models import Character, InventoryItem, Equipment, CharacterSkill, StorageType
from backend.game.map_manager import map_manager
from backend.game.combat import CombatEngine
from backend.game.data_loader import DataLoader

class GameEngine:
    """游戏引擎 - 处理所有游戏逻辑"""
    
    # 战斗锁 {char_id: True}
    combat_locks: Dict[int, bool] = {}
    
    @classmethod
    async def enter_game(cls, char_id: int, db: AsyncSession) -> dict:
        """角色进入游戏"""
        char = await db.get(Character, char_id)
        if not char:
            return {"error": "角色不存在"}
        
        # 进入地图
        result = map_manager.enter_map(char_id, char.map_id or "main_city")
        
        # 更新角色位置
        char.pos_x = result["position"][0]
        char.pos_y = result["position"][1]
        await db.commit()
        
        return {
            "character": cls._char_to_dict(char),
            "map": result["state"]
        }
    
    @classmethod
    async def move(cls, char_id: int, x: int, y: int, db: AsyncSession) -> dict:
        """移动角色"""
        if cls.combat_locks.get(char_id):
            return {"success": False, "error": "战斗中无法移动"}
        
        result = map_manager.move(char_id, (x, y))
        
        if result.get("success"):
            char = await db.get(Character, char_id)
            if char:
                char.pos_x = x
                char.pos_y = y
                await db.commit()
        
        return result
    
    @classmethod
    async def attack_monster(cls, char_id: int, monster_pos: Tuple[int, int], db: AsyncSession) -> dict:
        """攻击怪物"""
        if cls.combat_locks.get(char_id):
            return {"success": False, "error": "已在战斗中"}
        
        # 获取角色
        char = await db.get(Character, char_id)
        if not char:
            return {"success": False, "error": "角色不存在"}
        
        # 获取地图实例
        map_id = map_manager.player_map.get(char_id)
        if not map_id:
            return {"success": False, "error": "不在地图中"}
        
        instance = map_manager.instances.get(map_id)
        if not instance:
            return {"success": False, "error": "地图不存在"}
        
        # 获取怪物
        monster_data = instance.monsters.get(monster_pos)
        if not monster_data:
            return {"success": False, "error": "怪物不存在"}
        
        monster_info = DataLoader.get_monster(monster_data["type"])
        if not monster_info:
            return {"success": False, "error": "怪物数据不存在"}
        
        # 锁定战斗
        cls.combat_locks[char_id] = True
        
        try:
            # 获取角色已学习的主动技能
            skills_result = await db.execute(
                select(CharacterSkill).where(CharacterSkill.character_id == char_id)
            )
            learned_skills = skills_result.scalars().all()
            active_skills = []
            for skill in learned_skills:
                skill_info = DataLoader.get_skill(skill.skill_id, char.char_class.value)
                if skill_info and skill_info.get("type") == "active":
                    skill_data = {**skill_info, "level": skill.level, "skill_id": skill.skill_id}
                    active_skills.append(skill_data)
            
            # 计算战斗
            player_stats = await cls._get_combat_stats(char, db)
            drop_groups = monster_info.get("drop_groups", [])
            result = CombatEngine.pve_combat(player_stats, monster_info, active_skills, drop_groups, DataLoader)
            
            if result.victory:
                # 移除怪物并移动玩家到怪物位置
                instance.remove_monster(monster_pos)
                map_manager.move(char_id, monster_pos)
                char.pos_x = monster_pos[0]
                char.pos_y = monster_pos[1]
                
                # 增加经验和金币
                char.exp += result.exp_gained
                char.gold += result.gold_gained
                
                # 检查升级
                level_up = cls._check_level_up(char)
                
                # 添加掉落物品
                for drop in result.drops:
                    await cls._add_item(char_id, drop["item_id"], drop["quality"], db)
                
                # 增加使用技能的熟练度
                for skill_id in result.skills_used:
                    await cls._increase_skill_proficiency(char_id, skill_id, db)
                
                await db.commit()
                
                return {
                    "success": True,
                    "victory": True,
                    "logs": result.logs,
                    "exp_gained": result.exp_gained,
                    "gold_gained": result.gold_gained,
                    "drops": result.drops,
                    "level_up": level_up,
                    "character": cls._char_to_dict(char)
                }
            else:
                # 战斗失败，角色留在原地
                return {
                    "success": True,
                    "victory": False,
                    "logs": result.logs,
                    "player_died": result.player_died
                }
        finally:
            cls.combat_locks.pop(char_id, None)
    
    @classmethod
    async def use_entrance(cls, char_id: int, entrance_id: str, db: AsyncSession) -> dict:
        """使用入口传送"""
        result = map_manager.use_entrance(char_id, entrance_id)
        
        if result.get("map_id"):
            char = await db.get(Character, char_id)
            if char:
                char.map_id = result["map_id"]
                char.pos_x = result["position"][0]
                char.pos_y = result["position"][1]
                await db.commit()
        
        return result
    
    @classmethod
    async def use_exit(cls, char_id: int, exit_type: str, db: AsyncSession) -> dict:
        """使用出口"""
        result = map_manager.use_exit(char_id, exit_type)
        
        if result.get("map_id"):
            char = await db.get(Character, char_id)
            if char:
                char.map_id = result["map_id"]
                char.pos_x = result["position"][0]
                char.pos_y = result["position"][1]
                await db.commit()
        
        return result
    
    @classmethod
    async def return_to_city(cls, char_id: int, db: AsyncSession) -> dict:
        """回城"""
        result = map_manager.return_to_city(char_id)
        
        char = await db.get(Character, char_id)
        if char:
            char.map_id = "main_city"
            char.pos_x = result["position"][0]
            char.pos_y = result["position"][1]
            await db.commit()
        
        return result
    
    @classmethod
    async def get_inventory(cls, char_id: int, storage_type: str, db: AsyncSession) -> dict:
        """获取背包/仓库"""
        st = StorageType.WAREHOUSE if storage_type == "warehouse" else StorageType.INVENTORY
        result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.character_id == char_id,
                InventoryItem.storage_type == st
            )
        )
        items = result.scalars().all()
        
        return {
            "storage_type": storage_type,
            "items": [{
                "slot": item.slot,
                "item_id": item.item_id,
                "quality": item.quality,
                "quantity": item.quantity,
                "info": cls._apply_quality_bonus(DataLoader.get_item(item.item_id), item.quality)
            } for item in items]
        }
    
    @classmethod
    async def get_equipment(cls, char_id: int, db: AsyncSession) -> dict:
        """获取角色装备和综合属性"""
        char = await db.get(Character, char_id)
        if not char:
            return {"equipment": {}, "total_stats": {}}
        
        # 获取所有装备
        result = await db.execute(select(Equipment).where(Equipment.character_id == char_id))
        equipment_list = result.scalars().all()
        
        # 装备槽位
        slots = ["weapon", "helmet", "armor", "belt", "boots", "necklace", "ring_left", "ring_right", "bracelet_left", "bracelet_right"]
        equipment = {}
        
        for slot in slots:
            equip = next((e for e in equipment_list if e.slot == slot), None)
            if equip:
                item_info = cls._apply_quality_bonus(DataLoader.get_item(equip.item_id), equip.quality)
                equipment[slot] = {
                    "item_id": equip.item_id,
                    "quality": equip.quality,
                    "info": item_info
                }
            else:
                equipment[slot] = None
        
        # 计算综合属性
        total_stats = await cls._get_combat_stats(char, db)
        
        return {
            "equipment": equipment,
            "total_stats": {
                "level": total_stats["level"],
                "hp": f"{char.hp}/{total_stats['max_hp']}",
                "mp": f"{char.mp}/{total_stats['max_mp']}",
                "attack": f"{total_stats['attack_min']}-{total_stats['attack_max']}",
                "magic": f"{total_stats['magic_min']}-{total_stats['magic_max']}",
                "defense": f"{total_stats['defense_min']}-{total_stats['defense_max']}",
                "magic_defense": f"{total_stats['magic_defense_min']}-{total_stats['magic_defense_max']}",
                "luck": total_stats["luck"]
            }
        }
    
    # 槽位映射：物品slot -> 装备slot
    SLOT_MAP = {
        "body": "armor",
        "head": "helmet",
        "helmet": "helmet",
        "weapon": "weapon",
        "belt": "belt",
        "boots": "boots",
        "necklace": "necklace",
        "ring": "ring_left",  # 默认左边
        "bracelet": "bracelet_left",  # 默认左边
    }
    
    @classmethod
    async def equip_item(cls, char_id: int, inventory_slot: int, db: AsyncSession, target_slot: str = None) -> dict:
        """装备物品"""
        # 获取背包物品
        result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.character_id == char_id,
                InventoryItem.storage_type == StorageType.INVENTORY,
                InventoryItem.slot == inventory_slot
            )
        )
        inv_item = result.scalar_one_or_none()
        if not inv_item:
            return {"success": False, "error": "物品不存在"}
        
        item_info = DataLoader.get_item(inv_item.item_id)
        if not item_info or item_info.get("type") not in ["weapon", "armor", "accessory"]:
            return {"success": False, "error": "无法装备此物品"}
        
        # 获取物品槽位并映射到装备槽位
        item_slot = item_info.get("slot", "weapon")
        equip_slot = cls.SLOT_MAP.get(item_slot, item_slot)
        
        # 对于戒指和手镯，如果指定了目标槽位则使用，否则自动选择
        if item_slot in ["ring", "bracelet"]:
            left_slot = f"{item_slot}_left"
            right_slot = f"{item_slot}_right"
            if target_slot in [left_slot, right_slot]:
                equip_slot = target_slot
            else:
                # 自动选择：优先空槽位，否则左边
                result = await db.execute(
                    select(Equipment).where(
                        Equipment.character_id == char_id,
                        Equipment.slot == left_slot
                    )
                )
                if result.scalar_one_or_none():
                    equip_slot = right_slot
                else:
                    equip_slot = left_slot
        
        # 检查当前装备
        result = await db.execute(
            select(Equipment).where(
                Equipment.character_id == char_id,
                Equipment.slot == equip_slot
            )
        )
        current_equip = result.scalar_one_or_none()
        
        if current_equip:
            # 将当前装备放入背包
            await cls._add_item(char_id, current_equip.item_id, current_equip.quality, db)
            current_equip.item_id = inv_item.item_id
            current_equip.quality = inv_item.quality
        else:
            # 创建新装备
            new_equip = Equipment(
                character_id=char_id,
                slot=equip_slot,
                item_id=inv_item.item_id,
                quality=inv_item.quality
            )
            db.add(new_equip)
        
        # 移除背包物品
        await db.delete(inv_item)
        await db.commit()
        
        return {"success": True}
    
    @classmethod
    async def recycle_item(cls, char_id: int, inventory_slot: int, db: AsyncSession) -> dict:
        """回收物品"""
        result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.character_id == char_id,
                InventoryItem.storage_type == StorageType.INVENTORY,
                InventoryItem.slot == inventory_slot
            )
        )
        inv_item = result.scalar_one_or_none()
        if not inv_item:
            return {"success": False, "error": "物品不存在"}
        
        item_info = DataLoader.get_item(inv_item.item_id)
        quality_info = DataLoader.get_quality(inv_item.quality)
        
        char = await db.get(Character, char_id)
        
        gold = int(item_info.get("recycle_gold", 0) * quality_info.get("recycle_multiplier", 1))
        yuanbao = int(item_info.get("recycle_yuanbao", 0) * quality_info.get("recycle_multiplier", 1))
        
        if gold > 0:
            char.gold += gold * inv_item.quantity
        if yuanbao > 0:
            char.yuanbao += yuanbao * inv_item.quantity
        
        await db.delete(inv_item)
        await db.commit()
        
        return {"success": True, "gold": gold, "yuanbao": yuanbao}
    
    @classmethod
    async def recycle_all(cls, char_id: int, db: AsyncSession) -> dict:
        """回收背包中所有物品"""
        result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.character_id == char_id,
                InventoryItem.storage_type == StorageType.INVENTORY
            )
        )
        items = result.scalars().all()
        
        if not items:
            return {"success": False, "error": "背包为空"}
        
        char = await db.get(Character, char_id)
        total_gold = 0
        total_yuanbao = 0
        recycled_count = 0
        
        for inv_item in items:
            item_info = DataLoader.get_item(inv_item.item_id)
            quality_info = DataLoader.get_quality(inv_item.quality)
            
            gold = int(item_info.get("recycle_gold", 0) * quality_info.get("recycle_multiplier", 1))
            yuanbao = int(item_info.get("recycle_yuanbao", 0) * quality_info.get("recycle_multiplier", 1))
            
            if gold > 0:
                total_gold += gold * inv_item.quantity
            if yuanbao > 0:
                total_yuanbao += yuanbao * inv_item.quantity
            
            await db.delete(inv_item)
            recycled_count += 1
        
        char.gold += total_gold
        char.yuanbao += total_yuanbao
        await db.commit()
        
        return {"success": True, "gold": total_gold, "yuanbao": total_yuanbao, "count": recycled_count}
    
    @classmethod
    async def move_to_warehouse(cls, char_id: int, inventory_slot: int, db: AsyncSession) -> dict:
        """将背包物品移到仓库"""
        # 获取背包物品
        result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.character_id == char_id,
                InventoryItem.storage_type == StorageType.INVENTORY,
                InventoryItem.slot == inventory_slot
            )
        )
        inv_item = result.scalar_one_or_none()
        if not inv_item:
            return {"success": False, "error": "物品不存在"}
        
        # 找仓库空位
        result = await db.execute(
            select(InventoryItem.slot).where(
                InventoryItem.character_id == char_id,
                InventoryItem.storage_type == StorageType.WAREHOUSE
            )
        )
        used_slots = {row[0] for row in result.fetchall()}
        
        warehouse_slot = None
        for slot in range(1000):
            if slot not in used_slots:
                warehouse_slot = slot
                break
        
        if warehouse_slot is None:
            return {"success": False, "error": "仓库已满"}
        
        # 移动物品
        inv_item.storage_type = StorageType.WAREHOUSE
        inv_item.slot = warehouse_slot
        await db.commit()
        
        return {"success": True}
    
    @classmethod
    async def move_to_inventory(cls, char_id: int, warehouse_slot: int, db: AsyncSession) -> dict:
        """将仓库物品移到背包"""
        # 获取仓库物品
        result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.character_id == char_id,
                InventoryItem.storage_type == StorageType.WAREHOUSE,
                InventoryItem.slot == warehouse_slot
            )
        )
        wh_item = result.scalar_one_or_none()
        if not wh_item:
            return {"success": False, "error": "物品不存在"}
        
        # 找背包空位
        result = await db.execute(
            select(InventoryItem.slot).where(
                InventoryItem.character_id == char_id,
                InventoryItem.storage_type == StorageType.INVENTORY
            )
        )
        used_slots = {row[0] for row in result.fetchall()}
        
        inv_slot = None
        for slot in range(200):
            if slot not in used_slots:
                inv_slot = slot
                break
        
        if inv_slot is None:
            return {"success": False, "error": "背包已满"}
        
        # 移动物品
        wh_item.storage_type = StorageType.INVENTORY
        wh_item.slot = inv_slot
        await db.commit()
        
        return {"success": True}
    
    @classmethod
    async def buy_item(cls, char_id: int, item_id: str, quantity: int, db: AsyncSession) -> dict:
        """购买物品"""
        item_info = DataLoader.get_item(item_id)
        if not item_info or item_info.get("buy_price", 0) <= 0:
            return {"success": False, "error": "物品无法购买"}
        
        total_price = item_info["buy_price"] * quantity
        
        char = await db.get(Character, char_id)
        if char.gold < total_price:
            return {"success": False, "error": "金币不足"}
        
        char.gold -= total_price
        await cls._add_item(char_id, item_id, "white", db, quantity)
        await db.commit()
        
        return {"success": True}
    
    @classmethod
    async def learn_skill(cls, char_id: int, skill_id: str, db: AsyncSession) -> dict:
        """学习技能"""
        char = await db.get(Character, char_id)
        skill_info = DataLoader.get_skill(skill_id, char.char_class.value)
        
        if not skill_info:
            return {"success": False, "error": "技能不存在"}
        
        if skill_info.get("class") != char.char_class.value:
            return {"success": False, "error": "职业不符"}
        
        if char.level < skill_info.get("level_req", 1):
            return {"success": False, "error": "等级不足"}
        
        # 检查是否已学习
        result = await db.execute(
            select(CharacterSkill).where(
                CharacterSkill.character_id == char_id,
                CharacterSkill.skill_id == skill_id
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            return {"success": False, "error": "技能已学习"}
        
        # 学习新技能
        buy_price = skill_info.get("buy_price", 0)
        if buy_price > 0:
            if char.gold < buy_price:
                return {"success": False, "error": "金币不足"}
            char.gold -= buy_price
        
        new_skill = CharacterSkill(character_id=char_id, skill_id=skill_id, level=1, proficiency=0)
        db.add(new_skill)
        await db.commit()
        return {"success": True}
    
    @classmethod
    async def use_skillbook(cls, char_id: int, inventory_slot: int, db: AsyncSession) -> dict:
        """使用技能书学习技能"""
        # 获取背包物品
        result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.character_id == char_id,
                InventoryItem.storage_type == StorageType.INVENTORY,
                InventoryItem.slot == inventory_slot
            )
        )
        inv_item = result.scalar_one_or_none()
        if not inv_item:
            return {"success": False, "error": "物品不存在"}
        
        item_info = DataLoader.get_item(inv_item.item_id)
        if not item_info or item_info.get("type") != "skillbook":
            return {"success": False, "error": "这不是技能书"}
        
        skill_id = item_info.get("skill_id")
        char = await db.get(Character, char_id)
        
        # 检查职业
        if item_info.get("class") != char.char_class.value:
            return {"success": False, "error": "职业不符，无法学习此技能"}
        
        # 学习技能
        learn_result = await cls.learn_skill(char_id, skill_id, db)
        if not learn_result.get("success"):
            return learn_result
        
        # 消耗技能书
        await db.delete(inv_item)
        await db.commit()
        
        return {"success": True, "skill_id": skill_id, "message": f"成功学习技能: {item_info.get('name')}"}
    
    @classmethod
    async def get_character_skills(cls, char_id: int, db: AsyncSession) -> dict:
        """获取角色技能列表"""
        char = await db.get(Character, char_id)
        if not char:
            return {"learned": [], "available": []}
        
        # 获取已学习的技能
        result = await db.execute(
            select(CharacterSkill).where(CharacterSkill.character_id == char_id)
        )
        learned_skills = result.scalars().all()
        learned_dict = {
            skill.skill_id: {
                "skill_id": skill.skill_id,
                "level": skill.level,
                "proficiency": skill.proficiency,
                "info": DataLoader.get_skill(skill.skill_id, char.char_class.value)
            }
            for skill in learned_skills
        }
        
        # 获取所有可学习的技能
        all_skills = DataLoader.get_shop_items("skill")
        available_skills = []
        for skill_id, skill_info in all_skills.items():
            if skill_info.get("class") == char.char_class.value:
                is_learned = skill_id in learned_dict
                available_skills.append({
                    "skill_id": skill_id,
                    "info": skill_info,
                    "learned": is_learned,
                    "can_learn": not is_learned and char.level >= skill_info.get("level_req", 1)
                })
        
        return {"learned": list(learned_dict.values()), "available": available_skills}
    
    @classmethod
    async def use_skill(cls, char_id: int, skill_id: str, db: AsyncSession) -> dict:
        """使用技能(增加熟练度)"""
        result = await db.execute(
            select(CharacterSkill).where(
                CharacterSkill.character_id == char_id,
                CharacterSkill.skill_id == skill_id
            )
        )
        skill = result.scalar_one_or_none()
        
        if not skill:
            return {"success": False, "error": "未学习此技能"}
        
        # 增加熟练度
        skill.proficiency += 10
        
        # 检查升级 (每1000熟练度升1级)
        max_level = 3
        while skill.proficiency >= 1000 and skill.level < max_level:
            skill.proficiency -= 1000
            skill.level += 1
        
        await db.commit()
        return {"success": True, "level": skill.level, "proficiency": skill.proficiency}
    
    @classmethod
    async def _increase_skill_proficiency(cls, char_id: int, skill_id: str, db: AsyncSession):
        """增加技能熟练度（内部方法，不提交事务）"""
        result = await db.execute(
            select(CharacterSkill).where(
                CharacterSkill.character_id == char_id,
                CharacterSkill.skill_id == skill_id
            )
        )
        skill = result.scalar_one_or_none()
        
        if not skill:
            return
        
        # 增加熟练度
        skill.proficiency += 10
        
        # 检查升级 (每1000熟练度升1级)
        max_level = 3
        while skill.proficiency >= 1000 and skill.level < max_level:
            skill.proficiency -= 1000
            skill.level += 1
    
    @classmethod
    def _apply_quality_bonus(cls, item_info: dict, quality: str) -> dict:
        """应用品质加成到物品属性"""
        if not item_info:
            return item_info
        quality_info = DataLoader.get_quality(quality)
        bonus = quality_info.get("bonus", 1.0) if quality_info else 1.0
        if bonus == 1.0:
            return item_info
        
        result = item_info.copy()
        # 应用加成到所有数值属性
        for key in ["attack_min", "attack_max", "magic_min", "magic_max",
                    "defense_min", "defense_max", "magic_defense_min", "magic_defense_max",
                    "hp_bonus", "mp_bonus"]:
            if key in result:
                result[key] = int(result[key] * bonus)
        return result
    
    @classmethod
    async def _add_item(cls, char_id: int, item_id: str, quality: str, db: AsyncSession, quantity: int = 1):
        """添加物品到背包"""
        # 找空位
        result = await db.execute(
            select(InventoryItem.slot).where(
                InventoryItem.character_id == char_id,
                InventoryItem.storage_type == StorageType.INVENTORY
            )
        )
        used_slots = {row[0] for row in result.fetchall()}
        
        for slot in range(200):
            if slot not in used_slots:
                item = InventoryItem(
                    character_id=char_id,
                    storage_type=StorageType.INVENTORY,
                    item_id=item_id,
                    quality=quality,
                    slot=slot,
                    quantity=quantity
                )
                db.add(item)
                return True
        return False
    
    @classmethod
    async def _get_combat_stats(cls, char: Character, db: AsyncSession) -> dict:
        """获取战斗属性（支持攻击/魔法/防御/魔御的min-max范围）"""
        stats = {
            "id": char.id,
            "name": char.name,
            "level": char.level,
            "max_hp": char.max_hp,
            "max_mp": char.max_mp,
            "attack_min": char.attack,
            "attack_max": char.attack,
            "magic_min": 0,
            "magic_max": 0,
            "defense_min": char.defense,
            "defense_max": char.defense,
            "magic_defense_min": 0,
            "magic_defense_max": 0,
            "luck": char.luck
        }
        # 兼容旧代码
        stats["attack"] = char.attack
        stats["defense"] = char.defense
        
        # 加上装备属性
        result = await db.execute(select(Equipment).where(Equipment.character_id == char.id))
        for equip in result.scalars():
            item_info = DataLoader.get_item(equip.item_id)
            quality_info = DataLoader.get_quality(equip.quality)
            bonus = quality_info.get("bonus", 1.0)
            
            # 支持min/max格式，也兼容旧的单值格式
            atk = item_info.get("attack", 0)
            stats["attack_min"] += int(item_info.get("attack_min", atk) * bonus)
            stats["attack_max"] += int(item_info.get("attack_max", atk) * bonus)
            
            magic = item_info.get("magic", 0)
            stats["magic_min"] += int(item_info.get("magic_min", magic) * bonus)
            stats["magic_max"] += int(item_info.get("magic_max", magic) * bonus)
            
            defense = item_info.get("defense", 0)
            stats["defense_min"] += int(item_info.get("defense_min", defense) * bonus)
            stats["defense_max"] += int(item_info.get("defense_max", defense) * bonus)
            
            mac = item_info.get("magic_defense", 0)
            stats["magic_defense_min"] += int(item_info.get("magic_defense_min", mac) * bonus)
            stats["magic_defense_max"] += int(item_info.get("magic_defense_max", mac) * bonus)
            
            stats["max_hp"] += int(item_info.get("hp_bonus", 0) * bonus)
            stats["max_mp"] += int(item_info.get("mp_bonus", 0) * bonus)
        
        # 加上被动技能属性
        skills_result = await db.execute(select(CharacterSkill).where(CharacterSkill.character_id == char.id))
        for skill in skills_result.scalars():
            skill_info = DataLoader.get_skill(skill.skill_id, char.char_class.value)
            if skill_info and skill_info.get("type") == "passive":
                effect = skill_info.get("effect", {})
                level_bonus = skill.level
                stats["attack_min"] += int(effect.get("attack_bonus", 0) * level_bonus)
                stats["attack_max"] += int(effect.get("attack_bonus", 0) * level_bonus)
                stats["defense_min"] += int(effect.get("defense_bonus", 0) * level_bonus)
                stats["defense_max"] += int(effect.get("defense_bonus", 0) * level_bonus)
                stats["max_hp"] += int(effect.get("hp_bonus", 0) * level_bonus)
                stats["max_mp"] += int(effect.get("mp_bonus", 0) * level_bonus)
        
        # 兼容旧代码：取平均值
        stats["attack"] = (stats["attack_min"] + stats["attack_max"]) // 2
        stats["defense"] = (stats["defense_min"] + stats["defense_max"]) // 2
        
        return stats
    
    @classmethod
    def _check_level_up(cls, char: Character) -> dict:
        """检查升级，返回升级信息"""
        level_up_data = {"leveled_up": False, "new_level": char.level, "stats_gained": {}}
        
        # 计算升级所需经验（指数增长）
        exp_needed = int(char.level * 100 * (1.1 ** (char.level - 1)))
        
        if char.exp >= exp_needed:
            char.exp -= exp_needed
            char.level += 1
            
            # 根据职业获得不同的属性加成
            if char.char_class.value == "warrior":
                hp_gain = 25
                mp_gain = 5
                attack_gain = 4
                magic_gain = 0
                defense_gain = 3
                magic_defense_gain = 1
            elif char.char_class.value == "mage":
                hp_gain = 10
                mp_gain = 20
                attack_gain = 1
                magic_gain = 5
                defense_gain = 1
                magic_defense_gain = 2
            else:  # taoist
                hp_gain = 15
                mp_gain = 15
                attack_gain = 2
                magic_gain = 3
                defense_gain = 2
                magic_defense_gain = 1
            
            char.max_hp += hp_gain
            char.max_mp += mp_gain
            char.attack += attack_gain
            char.magic += magic_gain
            char.defense += defense_gain
            char.magic_defense += magic_defense_gain
            
            # 每10级额外增加幸运值
            luck_gain = 0
            if char.level % 10 == 0:
                char.luck += 1
                luck_gain = 1
            
            # 恢复满状态
            char.hp = char.max_hp
            char.mp = char.max_mp
            
            level_up_data = {
                "leveled_up": True,
                "new_level": char.level,
                "stats_gained": {
                    "hp": hp_gain,
                    "mp": mp_gain,
                    "attack": attack_gain,
                    "magic": magic_gain,
                    "defense": defense_gain,
                    "magic_defense": magic_defense_gain,
                    "luck": luck_gain
                }
            }
        
        return level_up_data
    
    @classmethod
    def _char_to_dict(cls, char: Character) -> dict:
        return {
            "id": char.id,
            "name": char.name,
            "char_class": char.char_class.value,
            "level": char.level,
            "exp": char.exp,
            "gold": char.gold,
            "yuanbao": char.yuanbao,
            "hp": char.hp,
            "max_hp": char.max_hp,
            "mp": char.mp,
            "max_mp": char.max_mp,
            "attack": char.attack,
            "magic": getattr(char, 'magic', 0),
            "defense": char.defense,
            "magic_defense": getattr(char, 'magic_defense', 0),
            "luck": char.luck,
            "map_id": char.map_id,
            "pos_x": char.pos_x,
            "pos_y": char.pos_y
        }