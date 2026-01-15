import random
from typing import Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models import Character, InventoryItem, Equipment, CharacterSkill, StorageType
from backend.game.map_manager import map_manager
from backend.game.combat import CombatEngine
from backend.game.data_loader import DataLoader
from backend.game.effects import EffectCalculator, calculate_set_bonuses

class GameEngine:
    """游戏引擎 - 处理所有游戏逻辑"""
    
    # 战斗锁 {char_id: True}
    combat_locks: Dict[int, bool] = {}
    # 召唤物状态 {char_id: summon_dict}
    summons: Dict[int, dict] = {}
    # 禁用技能 {char_id: [skill_id, ...]}
    disabled_skills: Dict[int, list] = {}
    
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
    
    # 地图区域对应的Boss映射
    MAP_BOSS_MAPPING = {
        # 沃玛区域
        "woma_forest": "woma_leader", "woma_temple_1": "woma_leader", "woma_temple_2": "woma_leader", "woma_temple_3": "woma_leader",
        # 僵尸洞区域
        "zombie_cave_1": "corpse_king", "zombie_cave_2": "corpse_king", "zombie_cave_3": "corpse_king",
        # 猪洞区域
        "pig_cave_1": "pig_king", "pig_cave_2": "pig_king", "pig_cave_3": "pig_king",
        # 祖玛区域
        "zuma_temple_1": "zuma_leader", "zuma_temple_2": "zuma_leader", "zuma_temple_3": "zuma_leader", "zuma_temple_4": "zuma_leader", "zuma_temple_5": "zuma_leader",
        # 封魔谷区域
        "sealed_valley_1": "demon_lord", "sealed_valley_2": "demon_lord", "sealed_valley_3": "demon_lord",
        # 赤月区域
        "red_moon_canyon": "red_moon_demon", "red_moon_cave": "red_moon_demon", "red_moon_temple": "red_moon_demon",
        # 暗黑区域
        "dark_forest": "blood_raven", "cold_plains": "blood_raven", "blood_moor": "blood_raven",
        # 崔斯特瑞姆区域
        "tristram_ruins": "butcher", "cathedral_1": "butcher", "cathedral_2": "butcher", "cathedral_3": "butcher",
        # 卡拉赞区域
        "deadwind_pass": "prince_malchezaar", "karazhan_1": "prince_malchezaar", "karazhan_2": "prince_malchezaar", "karazhan_3": "prince_malchezaar",
        # 熔火之心区域
        "molten_core_entrance": "ragnaros", "molten_core_1": "ragnaros", "molten_core_2": "ragnaros",
        # 蜈蚣洞区域
        "centipede_cave_1": "skeleton_king", "centipede_cave_2": "skeleton_king", "centipede_cave_3": "skeleton_king",
        # 黑石区域
        "blackrock_depths": "nefarian", "blackrock_spire": "nefarian",
    }
    
    @classmethod
    async def attack_monster(cls, char_id: int, monster_pos: Tuple[int, int], db: AsyncSession) -> dict:
        """攻击怪物 - 支持多怪物战斗和哥布林遭遇"""
        if cls.combat_locks.get(char_id):
            return {"success": False, "error": "已在战斗中"}
        
        char = await db.get(Character, char_id)
        if not char:
            return {"success": False, "error": "角色不存在"}
        
        map_id = map_manager.player_map.get(char_id)
        if not map_id:
            return {"success": False, "error": "不在地图中"}
        
        instance = map_manager.instances.get(map_id)
        if not instance:
            return {"success": False, "error": "地图不存在"}
        
        monster_data = instance.monsters.get(monster_pos)
        if not monster_data:
            return {"success": False, "error": "怪物不存在"}
        
        monster_info = DataLoader.get_monster(monster_data["type"])
        if not monster_info:
            return {"success": False, "error": "怪物数据不存在"}
        
        # 检查是否遇到哥布林 (1/10概率)
        goblin_encounter = False
        goblin_monster = None
        if random.randint(1, 5) == 1 and map_id in cls.MAP_BOSS_MAPPING:
            boss_type = cls.MAP_BOSS_MAPPING[map_id]
            boss_info = DataLoader.get_monster(boss_type)
            if boss_info:
                goblin_encounter = True
                goblin_monster = boss_info.copy()
                goblin_monster["name"] = "哥布林"
                goblin_monster["is_goblin"] = True
                # 掉落率提升10倍
                enhanced_drops = []
                for drop in goblin_monster.get("drops", []):
                    new_drop = drop.copy()
                    rate_str = str(drop.get("rate", "1/100"))
                    if "/" in rate_str:
                        parts = rate_str.split("/")
                        new_rate = f"{int(parts[0]) * 10}/{parts[1]}"
                        new_drop["rate"] = new_rate
                    enhanced_drops.append(new_drop)
                goblin_monster["drops"] = enhanced_drops
        
        cls.combat_locks[char_id] = True
        
        try:
            # 获取角色所有技能（包括被动）
            skills_result = await db.execute(
                select(CharacterSkill).where(CharacterSkill.character_id == char_id)
            )
            learned_skills = skills_result.scalars().all()
            all_skills = []
            for skill in learned_skills:
                skill_info = DataLoader.get_skill(skill.skill_id, char.char_class.value)
                if skill_info:
                    skill_data = {**skill_info, "level": skill.level, "skill_id": skill.skill_id}
                    all_skills.append(skill_data)
            
            # 获取背包中的恢复物品（使用行锁避免并发冲突）
            inv_result = await db.execute(
                select(InventoryItem).where(
                    InventoryItem.character_id == char_id,
                    InventoryItem.storage_type == StorageType.INVENTORY
                ).with_for_update()
            )
            inventory = []
            for item in inv_result.scalars():
                item_info = DataLoader.get_item(item.item_id)
                if item_info and item_info.get("type") == "consumable":
                    inventory.append({"slot": item.slot, "info": item_info, "db_item": item})
            
            # 生成多怪物（1-6个，根据地图难度）
            # 如果遇到哥布林，替换第一个怪物
            if goblin_encounter and goblin_monster:
                monsters = [goblin_monster]
                monsters[0]["quality"] = "white"  # 哥布林使用普通品质
            else:
                monsters = [monster_info.copy()]
                monsters[0]["quality"] = monster_data.get("quality", "white")
            
            # 随机添加额外怪物（最多5个额外）- Boss战斗时额外怪物为同地图普通怪
            extra_count = random.randint(0, min(5, char.level // 10))
            if extra_count > 0:
                map_config = map_manager.map_configs.get(map_id, {})
                normal_monster_types = map_config.get("monsters", [])
                for _ in range(extra_count):
                    # Boss战斗时，额外怪物从地图普通怪物中选择
                    if monster_data.get("is_boss") and normal_monster_types:
                        extra_type = random.choice(normal_monster_types)
                        extra_info = DataLoader.get_monster(extra_type)
                        if extra_info:
                            extra_monster = extra_info.copy()
                        else:
                            continue
                    else:
                        extra_monster = monster_info.copy()
                    extra_monster["quality"] = random.choices(
                        ["white", "green", "blue", "purple", "orange"],
                        weights=[50, 30, 15, 4, 1]
                    )[0]
                    monsters.append(extra_monster)
            
            player_stats = await cls._get_combat_stats(char, db)
            player_stats["char_class"] = char.char_class.value
            
            # 获取装备列表用于特效计算
            equip_result = await db.execute(select(Equipment).where(Equipment.character_id == char_id))
            equipment_list = []
            for equip in equip_result.scalars():
                item_info = cls._apply_quality_bonus(DataLoader.get_item(equip.item_id), equip.quality)
                if item_info:
                    equipment_list.append({"info": item_info})
            
            # 获取召唤物和禁用技能
            summon = cls.summons.get(char_id)
            disabled = cls.disabled_skills.get(char_id, [])
            
            result = CombatEngine.pve_combat(player_stats, monsters, all_skills, [], DataLoader, inventory, summon, disabled, equipment_list)
            
            # 更新召唤物状态
            if result.summon_died:
                cls.summons.pop(char_id, None)
            
            # 消耗使用的药水（统计每个db_item使用次数）
            used_counts = {}
            for item in inventory:
                if item.get("used_count", 0) > 0:
                    db_item = item.get("db_item")
                    if db_item:
                        used_counts[db_item] = used_counts.get(db_item, 0) + item["used_count"]
            for db_item, count in used_counts.items():
                if db_item.quantity > count:
                    db_item.quantity -= count
                else:
                    await db.delete(db_item)
            
            # 先提交药水消耗，避免锁等待
            await db.flush()
            
            if result.victory:
                instance.remove_monster(monster_pos)
                map_manager.move(char_id, monster_pos)
                char.pos_x = monster_pos[0]
                char.pos_y = monster_pos[1]
                
                char.exp += result.exp_gained
                char.gold += result.gold_gained
                
                level_up = cls._check_level_up(char)
                
                for drop in result.drops:
                    await cls._add_item(char_id, drop["item_id"], drop["quality"], db)
                
                # 增加主动技能熟练度
                for skill_id in result.skills_used:
                    await cls._increase_skill_proficiency(char_id, skill_id, db)
                
                # 增加被动技能熟练度（每次战斗+5）
                for skill_id in result.passive_skills:
                    await cls._increase_skill_proficiency(char_id, skill_id, db, amount=5)
                
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
        """获取背包/仓库（仓库按user_id共享）"""
        from sqlalchemy import or_
        st = StorageType.WAREHOUSE if storage_type == "warehouse" else StorageType.INVENTORY
        
        if st == StorageType.WAREHOUSE:
            char = await db.get(Character, char_id)
            result = await db.execute(
                select(InventoryItem).where(
                    InventoryItem.storage_type == st,
                    or_(
                        InventoryItem.user_id == char.user_id,
                        InventoryItem.character_id == char_id
                    )
                )
            )
        else:
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
    async def organize_inventory(cls, char_id: int, storage_type: str, db: AsyncSession) -> dict:
        """整理背包/仓库 - 合并可叠加物品（仓库按user_id共享）"""
        from sqlalchemy import or_
        st = StorageType.WAREHOUSE if storage_type == "warehouse" else StorageType.INVENTORY
        
        if st == StorageType.WAREHOUSE:
            char = await db.get(Character, char_id)
            result = await db.execute(
                select(InventoryItem).where(
                    InventoryItem.storage_type == st,
                    or_(
                        InventoryItem.user_id == char.user_id,
                        InventoryItem.character_id == char_id
                    )
                )
            )
        else:
            result = await db.execute(
                select(InventoryItem).where(
                    InventoryItem.character_id == char_id,
                    InventoryItem.storage_type == st
                )
            )
        items = list(result.scalars().all())
        
        # 按(item_id, quality)分组
        groups = {}
        for item in items:
            item_info = DataLoader.get_item(item.item_id)
            item_type = item_info.get("type") if item_info else None
            is_stackable = item_type in ["consumable", "material", "skillbook", "boss_summon"]
            if is_stackable:
                key = (item.item_id, item.quality)
                if key not in groups:
                    groups[key] = []
                groups[key].append(item)
        
        # 合并同类物品
        merged = 0
        for key, group in groups.items():
            if len(group) > 1:
                # 保留第一个，合并其他
                first = group[0]
                for other in group[1:]:
                    first.quantity += other.quantity
                    await db.delete(other)
                    merged += 1
        
        await db.commit()
        return {"success": True, "merged": merged}
    
    @classmethod
    async def get_equipment(cls, char_id: int, db: AsyncSession) -> dict:
        """获取角色装备和综合属性"""
        char = await db.get(Character, char_id)
        if not char:
            return {"equipment": {}, "total_stats": {}, "total_effects": {}, "set_bonuses": []}
        
        # 获取所有装备
        result = await db.execute(select(Equipment).where(Equipment.character_id == char_id))
        equipment_list = result.scalars().all()
        
        # 装备槽位
        slots = ["weapon", "helmet", "armor", "belt", "boots", "necklace", "ring_left", "ring_right", "bracelet_left", "bracelet_right"]
        equipment = {}
        equip_list_for_effects = []
        
        for slot in slots:
            equip = next((e for e in equipment_list if e.slot == slot), None)
            if equip:
                item_info = cls._apply_quality_bonus(DataLoader.get_item(equip.item_id), equip.quality)
                equipment[slot] = {
                    "item_id": equip.item_id,
                    "quality": equip.quality,
                    "info": item_info
                }
                equip_list_for_effects.append({"info": item_info})
            else:
                equipment[slot] = None
        
        # 计算综合属性
        total_stats = await cls._get_combat_stats(char, db)
        
        # 计算综合特效
        total_effects = EffectCalculator.get_equipment_effects(equip_list_for_effects)
        
        # 计算套装加成，并返回完整套装配置
        sets_config = DataLoader.get_sets()
        set_result = calculate_set_bonuses(equip_list_for_effects, sets_config, include_full_config=True)
        
        # 合并套装特效
        for k, v in set_result["total_effects"].items():
            total_effects[k] = total_effects.get(k, 0) + v
        
        # 合并套装属性到total_stats
        for k, v in set_result["total_stats"].items():
            if k in total_stats:
                total_stats[k] += v
            elif k == "hp_bonus":
                total_stats["max_hp"] += v
            elif k == "mp_bonus":
                total_stats["max_mp"] += v
            elif k == "defense":
                total_stats["defense_min"] += v
                total_stats["defense_max"] += v
            elif k == "magic_defense":
                total_stats["magic_defense_min"] += v
                total_stats["magic_defense_max"] += v
            elif k == "attack_bonus":
                total_stats["attack_min"] += v
                total_stats["attack_max"] += v
            elif k == "magic_bonus":
                total_stats["magic_min"] += v
                total_stats["magic_max"] += v
        
        # 过滤掉值为0的特效
        total_effects = {k: v for k, v in total_effects.items() if v > 0}
        
        return {
            "equipment": equipment,
            "total_stats": {
                "level": total_stats["level"],
                "hp": total_stats["max_hp"],
                "mp": total_stats["max_mp"],
                "attack": f"{total_stats['attack_min']}-{total_stats['attack_max']}",
                "magic": f"{total_stats['magic_min']}-{total_stats['magic_max']}",
                "defense": f"{total_stats['defense_min']}-{total_stats['defense_max']}",
                "magic_defense": f"{total_stats['magic_defense_min']}-{total_stats['magic_defense_max']}",
                "luck": total_stats["luck"]
            },
            "total_effects": total_effects,
            "set_bonuses": set_result["active_sets"]
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
            ).limit(1)
        )
        inv_item = result.scalar()
        if not inv_item:
            return {"success": False, "error": "物品不存在"}
        
        item_info = DataLoader.get_item(inv_item.item_id)
        if not item_info or item_info.get("type") not in ["weapon", "armor", "accessory"]:
            return {"success": False, "error": "无法装备此物品"}
        
        # 检查等级要求
        char = await db.get(Character, char_id)
        level_req = item_info.get("level_req", 1)
        if char.level < level_req:
            return {"success": False, "error": f"等级不足，需要{level_req}级"}
        
        # 检查职业限制
        allowed_classes = item_info.get("class")
        if allowed_classes:
            if isinstance(allowed_classes, str):
                allowed_classes = [allowed_classes]
            if char.char_class.value not in allowed_classes:
                return {"success": False, "error": f"职业不符，该装备限{'/'.join(allowed_classes)}"}
        
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
        """将背包物品移到仓库（仓库按user_id共享）"""
        from sqlalchemy import or_
        char = await db.get(Character, char_id)
        
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
        
        # 找仓库空位（按user_id共享）
        result = await db.execute(
            select(InventoryItem.slot).where(
                InventoryItem.storage_type == StorageType.WAREHOUSE,
                or_(
                    InventoryItem.user_id == char.user_id,
                    InventoryItem.character_id == char_id
                )
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
        
        # 移动物品到共享仓库
        inv_item.storage_type = StorageType.WAREHOUSE
        inv_item.slot = warehouse_slot
        inv_item.user_id = char.user_id
        await db.commit()
        
        return {"success": True}
    
    @classmethod
    async def move_to_inventory(cls, char_id: int, warehouse_slot: int, db: AsyncSession) -> dict:
        """将仓库物品移到背包（仓库按user_id共享）"""
        from sqlalchemy import or_
        char = await db.get(Character, char_id)
        
        # 获取仓库物品（按user_id共享）
        result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.storage_type == StorageType.WAREHOUSE,
                InventoryItem.slot == warehouse_slot,
                or_(
                    InventoryItem.user_id == char.user_id,
                    InventoryItem.character_id == char_id
                )
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
        
        # 移动物品到角色背包
        wh_item.storage_type = StorageType.INVENTORY
        wh_item.slot = inv_slot
        wh_item.character_id = char_id
        wh_item.user_id = char.user_id
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
    
    # 商城物品价格配置
    SHOP_PRICES = {
        # 药品
        'hp_potion_small': {'gold': 20}, 'hp_potion_medium': {'gold': 60}, 'hp_potion_large': {'gold': 200},
        'mp_potion_small': {'gold': 15}, 'mp_potion_medium': {'gold': 50}, 'mp_potion_large': {'gold': 150},
        'return_scroll': {'gold': 50},
        # 装备
        'wooden_sword': {'gold': 100}, 'wooden_staff': {'gold': 100}, 'wooden_wand': {'gold': 100},
        'cloth_armor': {'gold': 80}, 'leather_boots': {'gold': 200}, 'leather_belt': {'gold': 150},
        # 特殊物品
        'blessing_oil': {'yuanbao': 100}, 'woma_horn': {'yuanbao': 50}, 'zuma_piece': {'yuanbao': 80},
        'demon_heart': {'yuanbao': 120}
    }
    
    @classmethod
    async def shop_buy(cls, char_id: int, item_id: str, quantity: int, currency: str, db: AsyncSession) -> dict:
        """商城购买物品"""
        price_info = cls.SHOP_PRICES.get(item_id)
        if not price_info:
            return {"success": False, "error": "商品不存在"}
        
        price = price_info.get(currency, 0)
        if price <= 0:
            return {"success": False, "error": "无法使用该货币购买"}
        
        total = price * quantity
        char = await db.get(Character, char_id)
        if not char:
            return {"success": False, "error": "角色不存在"}
        
        if currency == 'yuanbao':
            if char.yuanbao < total:
                return {"success": False, "error": "元宝不足"}
            char.yuanbao -= total
        else:
            if char.gold < total:
                return {"success": False, "error": "金币不足"}
            char.gold -= total
        
        success = await cls._add_item(char_id, item_id, "white", db, quantity)
        if not success:
            return {"success": False, "error": "背包已满"}
        
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
    async def use_boss_item(cls, char_id: int, inventory_slot: int, db: AsyncSession) -> dict:
        """使用专属物品召唤Boss战斗"""
        if cls.combat_locks.get(char_id):
            return {"success": False, "error": "已在战斗中"}
        
        # 获取背包物品
        result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.character_id == char_id,
                InventoryItem.storage_type == StorageType.INVENTORY,
                InventoryItem.slot == inventory_slot
            ).limit(1)
        )
        inv_item = result.scalar()
        if not inv_item:
            return {"success": False, "error": "物品不存在"}
        
        item_info = DataLoader.get_item(inv_item.item_id)
        if not item_info or item_info.get("type") != "boss_summon":
            return {"success": False, "error": "这不是Boss召唤物品"}
        
        # 获取Boss类型
        summon_boss = item_info.get("summon_boss")
        if isinstance(summon_boss, list):
            boss_type = random.choice(summon_boss)
        else:
            boss_type = summon_boss
        
        monster_info = DataLoader.get_monster(boss_type)
        if not monster_info:
            return {"success": False, "error": "Boss数据不存在"}
        
        char = await db.get(Character, char_id)
        cls.combat_locks[char_id] = True
        
        try:
            # 获取角色技能
            skills_result = await db.execute(
                select(CharacterSkill).where(CharacterSkill.character_id == char_id)
            )
            all_skills = []
            for skill in skills_result.scalars():
                skill_info = DataLoader.get_skill(skill.skill_id, char.char_class.value)
                if skill_info:
                    all_skills.append({**skill_info, "level": skill.level, "skill_id": skill.skill_id})
            
            # 获取背包药水
            inv_result = await db.execute(
                select(InventoryItem).where(
                    InventoryItem.character_id == char_id,
                    InventoryItem.storage_type == StorageType.INVENTORY
                ).with_for_update()
            )
            inventory = []
            for item in inv_result.scalars():
                info = DataLoader.get_item(item.item_id)
                if info and info.get("type") == "consumable":
                    for _ in range(item.quantity):
                        inventory.append({"slot": item.slot, "info": info, "db_item": item})
            
            # Boss战斗
            boss = monster_info.copy()
            boss["quality"] = "orange"  # Boss固定橙色品质
            
            player_stats = await cls._get_combat_stats(char, db)
            player_stats["char_class"] = char.char_class.value
            
            # 获取装备列表用于特效计算
            equip_result = await db.execute(select(Equipment).where(Equipment.character_id == char_id))
            equipment_list = []
            for equip in equip_result.scalars():
                item_info = cls._apply_quality_bonus(DataLoader.get_item(equip.item_id), equip.quality)
                if item_info:
                    equipment_list.append({"info": item_info})
            
            summon = cls.summons.get(char_id)
            disabled = cls.disabled_skills.get(char_id, [])
            
            combat_result = CombatEngine.pve_combat(player_stats, [boss], all_skills, [], DataLoader, inventory, summon, disabled, equipment_list)
            
            # 更新召唤物状态
            if combat_result.summon_died:
                cls.summons.pop(char_id, None)
            
            # 消耗使用的药水
            used_counts = {}
            for item in inventory:
                if item.get("used_count", 0) > 0:
                    db_item = item.get("db_item")
                    if db_item:
                        used_counts[db_item] = used_counts.get(db_item, 0) + item["used_count"]
            for db_item, count in used_counts.items():
                if db_item.quantity > count:
                    db_item.quantity -= count
                else:
                    await db.delete(db_item)
            
            # 消耗召唤物品
            if inv_item.quantity > 1:
                inv_item.quantity -= 1
            else:
                await db.delete(inv_item)
            
            await db.flush()
            
            if combat_result.victory:
                char.exp += combat_result.exp_gained
                char.gold += combat_result.gold_gained
                
                level_up = cls._check_level_up(char)
                
                for drop in combat_result.drops:
                    await cls._add_item(char_id, drop["item_id"], drop["quality"], db)
                
                for skill_id in combat_result.skills_used:
                    await cls._increase_skill_proficiency(char_id, skill_id, db)
                
                await db.commit()
                
                return {
                    "success": True,
                    "victory": True,
                    "logs": combat_result.logs,
                    "exp_gained": combat_result.exp_gained,
                    "gold_gained": combat_result.gold_gained,
                    "drops": combat_result.drops,
                    "level_up": level_up,
                    "character": cls._char_to_dict(char)
                }
            else:
                await db.commit()
                return {
                    "success": True,
                    "victory": False,
                    "logs": combat_result.logs,
                    "player_died": combat_result.player_died
                }
        finally:
            cls.combat_locks.pop(char_id, None)
    
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
    async def _increase_skill_proficiency(cls, char_id: int, skill_id: str, db: AsyncSession, amount: int = 10):
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
        
        max_level = 3
        # 顶级技能不再增加熟练度
        if skill.level >= max_level:
            skill.proficiency = 0
            return
        
        skill.proficiency += amount
        
        while skill.proficiency >= 1000 and skill.level < max_level:
            skill.proficiency -= 1000
            skill.level += 1
            if skill.level >= max_level:
                skill.proficiency = 0
    
    @classmethod
    def _apply_quality_bonus(cls, item_info: dict, quality: str) -> dict:
        """应用品质加成到物品属性和特效"""
        if not item_info:
            return item_info
        quality_info = DataLoader.get_quality(quality)
        bonus = quality_info.get("bonus", 1.0) if quality_info else 1.0
        effect_bonus = quality_info.get("effect_bonus", 0) if quality_info else 0
        
        if bonus == 1.0 and effect_bonus == 0:
            return item_info
        
        result = item_info.copy()
        # 应用加成到所有数值属性
        for key in ["attack_min", "attack_max", "magic_min", "magic_max",
                    "defense_min", "defense_max", "magic_defense_min", "magic_defense_max",
                    "hp_bonus", "mp_bonus"]:
            if key in result:
                result[key] = int(result[key] * bonus)
        
        # 应用特效加成
        if "effects" in result and effect_bonus > 0:
            effects = result["effects"].copy()
            # 整数类型特效
            int_effects = {"poison_damage", "poison_rounds", "extra_phys", "extra_magic", "hp_on_hit", "mp_on_hit"}
            for key, value in effects.items():
                if isinstance(value, (int, float)) and value > 0:
                    new_val = value * (1 + effect_bonus)
                    # 整数特效取整，百分比特效保留3位小数
                    effects[key] = int(new_val) if key in int_effects else round(new_val, 3)
            result["effects"] = effects
        
        return result
    
    @classmethod
    async def _add_item(cls, char_id: int, item_id: str, quality: str, db: AsyncSession, quantity: int = 1):
        """添加物品到背包（消耗品可堆叠）"""
        # 获取角色的user_id用于仓库共享
        char = await db.get(Character, char_id)
        user_id = char.user_id if char else None
        
        item_info = DataLoader.get_item(item_id)
        item_type = item_info.get("type") if item_info else None
        is_stackable = item_type in ["consumable", "material", "skillbook", "boss_summon"]
        # 非装备类型物品品质统一为普通
        if item_type not in ["weapon", "armor", "accessory"]:
            quality = "white"
        
        # 如果是可堆叠物品，先查找已有的同类物品
        if is_stackable:
            result = await db.execute(
                select(InventoryItem).where(
                    InventoryItem.character_id == char_id,
                    InventoryItem.storage_type == StorageType.INVENTORY,
                    InventoryItem.item_id == item_id,
                    InventoryItem.quality == quality
                ).limit(1)
            )
            existing = result.scalar()
            if existing:
                existing.quantity += quantity
                return True
        
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
                    user_id=user_id,
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
        
        # 加上被动技能属性（按基础属性百分比增加）
        skills_result = await db.execute(select(CharacterSkill).where(CharacterSkill.character_id == char.id))
        for skill in skills_result.scalars():
            skill_info = DataLoader.get_skill(skill.skill_id, char.char_class.value)
            if skill_info and skill_info.get("type") == "passive":
                effect = skill_info.get("effect", {})
                level_bonus = skill.level
                # 阶梯增长：1级5%，2级12%，3级20%
                percent_bonus = [0.05, 0.12, 0.20][min(level_bonus, 3) - 1] if level_bonus > 0 else 0
                
                # 攻击加成（按百分比）
                if effect.get("attack_bonus"):
                    bonus = int(char.attack * percent_bonus)
                    stats["attack_min"] += bonus
                    stats["attack_max"] += bonus
                # 防御加成（按百分比）
                if effect.get("defense_bonus"):
                    bonus = int(char.defense * percent_bonus)
                    stats["defense_min"] += bonus
                    stats["defense_max"] += bonus
                # 魔御加成（按百分比）
                if effect.get("magic_defense_bonus"):
                    bonus = int(char.magic_defense * percent_bonus)
                    stats["magic_defense_min"] += bonus
                    stats["magic_defense_max"] += bonus
                # HP加成（按百分比）
                if effect.get("hp_bonus"):
                    stats["max_hp"] += int(char.max_hp * percent_bonus)
                # MP加成（按百分比）
                if effect.get("mp_bonus"):
                    stats["max_mp"] += int(char.max_mp * percent_bonus)
        
        # 兼容旧代码：取平均值
        stats["attack"] = (stats["attack_min"] + stats["attack_max"]) // 2
        stats["defense"] = (stats["defense_min"] + stats["defense_max"]) // 2
        
        return stats
    
    @classmethod
    def _check_level_up(cls, char: Character) -> dict:
        """检查升级，返回升级信息"""
        level_up_data = {"leveled_up": False, "new_level": char.level, "stats_gained": {}}
        
        # 计算升级所需经验（更陡峭的指数增长）
        exp_needed = int(char.level * 150 * (1.15 ** (char.level - 1)))
        
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