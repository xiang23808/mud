#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
装备生成脚本
根据改造文档生成所有散件和套装装备
"""

import json
import math
import random

# 装备槽位定义
SLOTS = {
    "weapon": "武器",
    "helmet": "头盔",
    "body": "胸甲",
    "belt": "腰带",
    "boots": "鞋子",
    "necklace": "项链",
    "ring": "戒指",
    "ring2": "戒指2",
    "bracelet": "手镯",
    "bracelet2": "手镯2"
}

# 散件槽位（前5个）
SCATTER_SLOTS = ["weapon", "helmet", "body", "belt", "boots"]

# 套装槽位（全部9个）
SET_SLOTS = list(SLOTS.keys())

# 职业定义
CLASSES = {
    "warrior": "战士",
    "mage": "法师"
}

# 散件名称模板（按档次）
SCATTER_NAMES = {
    1: {"warrior": ["木剑", "布帽", "布衣", "皮带", "皮靴"], "mage": ["木杖", "布帽", "布衣", "皮带", "皮靴"]},
    2: {"warrior": ["铁剑", "铁盔", "铁甲", "铁腰带", "铁靴"], "mage": ["法杖", "法师帽", "魔法袍", "铁腰带", "铁靴"]},
    3: {"warrior": ["钢剑", "钢盔", "钢甲", "钢腰带", "钢靴"], "mage": ["银杖", "银冠", "银袍", "银腰带", "银靴"]},
    4: {"warrior": ["青铜剑", "青铜盔", "青铜甲", "青铜腰带", "青铜靴"], "mage": ["秘银杖", "秘银冠", "秘银袍", "秘银腰带", "秘银靴"]},
    5: {"warrior": ["精钢剑", "精钢盔", "精钢甲", "精钢腰带", "精钢靴"], "mage": ["秘法杖", "秘法冠", "秘法袍", "秘法腰带", "秘法靴"]},
    6: {"warrior": ["勇士剑", "勇士盔", "勇士甲", "勇士腰带", "勇士靴"], "mage": ["法师杖", "法师冠", "法师袍", "法师腰带", "法师靴"]},
    7: {"warrior": ["骑士剑", "骑士盔", "骑士甲", "骑士腰带", "骑士靴"], "mage": ["术士杖", "术士冠", "术士袍", "术士腰带", "术士靴"]},
    8: {"warrior": ["百夫长剑", "百夫长盔", "百夫长甲", "百夫长腰带", "百夫长靴"], "mage": ["首席杖", "首席冠", "首席袍", "首席腰带", "首席靴"]},
    9: {"warrior": ["龙牙剑", "龙牙盔", "龙牙甲", "龙牙腰带", "龙牙靴"], "mage": ["凤羽杖", "凤羽冠", "凤羽袍", "凤羽腰带", "凤羽靴"]},
    10: {"warrior": ["雷神剑", "雷神盔", "雷神甲", "雷神腰带", "雷神靴"], "mage": ["星魔杖", "星魔冠", "星魔袍", "星魔腰带", "星魔靴"]},
    11: {"warrior": ["圣光剑", "圣光盔", "圣光甲", "圣光腰带", "圣光靴"], "mage": ["暗影杖", "暗影冠", "暗影袍", "暗影腰带", "暗影靴"]},
    12: {"warrior": ["冰霜剑", "冰霜盔", "冰霜甲", "冰霜腰带", "冰霜靴"], "mage": ["亡灵杖", "亡灵冠", "亡灵袍", "亡灵腰带", "亡灵靴"]},
    13: {"warrior": ["风暴剑", "风暴盔", "风暴甲", "风暴腰带", "风暴靴"], "mage": ["熔岩杖", "熔岩冠", "熔岩袍", "熔岩腰带", "熔岩靴"]},
    14: {"warrior": ["泰坦剑", "泰坦盔", "泰坦甲", "泰坦腰带", "泰坦靴"], "mage": ["虚空杖", "虚空冠", "虚空袍", "虚空腰带", "虚空靴"]},
    15: {"warrior": ["深渊剑", "深渊盔", "深渊甲", "深渊腰带", "深渊靴"], "mage": ["梦魇杖", "梦魇冠", "梦魇袍", "梦魇腰带", "梦魇靴"]},
    16: {"warrior": ["神域剑", "神域盔", "神域甲", "神域腰带", "神域靴"], "mage": ["天界杖", "天界冠", "天界袍", "天界腰带", "天界靴"]},
}

# 套装名称（按档次）
SET_NAMES = {
    2: {"warrior": "新手", "mage": "新手"},
    3: {"warrior": "丛林", "mage": "秘法"},
    4: {"warrior": "勇气", "mage": "光辉"},
    5: {"warrior": "守护", "mage": "奥秘"},
    6: {"warrior": "熔火", "mage": "奥术"},
    7: {"warrior": "烈焰", "mage": "寒冰"},
    8: {"warrior": "勇者", "mage": "魔能"},
    9: {"warrior": "龙鳞", "mage": "灵风"},
    10: {"warrior": "雷霆", "mage": "虚空"},
    11: {"warrior": "圣光", "mage": "暗影"},
    12: {"warrior": "冰冠", "mage": "巫妖"},
    13: {"warrior": "风暴", "mage": "熔岩"},
    14: {"warrior": "奥术战铠", "mage": "奥术秘法"},
    15: {"warrior": "深渊", "mage": "深渊魔纹"},
    16: {"warrior": "终极", "mage": "终极"},
}

# 套装部件名称后缀
SET_PART_NAMES = {
    "weapon": "之刃",
    "helmet": "之盔",
    "body": "之甲",
    "belt": "之带",
    "boots": "之靴",
    "necklace": "之链",
    "ring": "之戒",
    "ring2": "之戒",
    "bracelet": "之镯",
    "bracelet2": "之镯"
}

def calculate_attribute(tier, base_value, variance=0.2):
    """计算属性值（带随机波动）"""
    value = tier * base_value
    min_val = int(value * (1 - variance))
    max_val = int(value * (1 + variance))
    return min_val, max_val

def generate_scatter_equipment(tier, level_min, level_max):
    """生成散件装备"""
    equipment = {}
    
    for class_name, class_cn in CLASSES.items():
        names = SCATTER_NAMES[tier][class_name]
        
        for idx, slot in enumerate(SCATTER_SLOTS):
            item_name = names[idx]
            item_id = f"tier_{tier}_{class_name}_{slot}"
            
            item = {
                "id": item_id,
                "name": item_name,
                "type": "weapon" if slot == "weapon" else "armor",
                "slot": slot,
                "class": [class_name],
                "level_req": level_min,
                "tier": tier,
                "buy_price": 0,
                "recycle_yuanbao": tier * 5 if tier >= 7 else 0,
                "recycle_gold": tier * 50 if tier < 7 else 0,
                "drop_only": tier >= 7
            }
            
            # 根据职业和槽位添加属性
            if slot == "weapon":
                if class_name == "warrior":
                    min_atk, max_atk = calculate_attribute(tier, 8)
                    item["attack_min"] = min_atk
                    item["attack_max"] = max_atk
                else:  # mage
                    min_mag, max_mag = calculate_attribute(tier, 10)
                    item["magic_min"] = min_mag
                    item["magic_max"] = max_mag
                    item["mp_bonus"] = tier * 40
            else:  # armor
                if class_name == "warrior":
                    min_def, max_def = calculate_attribute(tier, 5)
                    item["defense_min"] = min_def
                    item["defense_max"] = max_def
                    item["hp_bonus"] = tier * 30
                else:  # mage
                    min_mdef, max_mdef = calculate_attribute(tier, 6)
                    item["magic_defense_min"] = min_mdef
                    item["magic_defense_max"] = max_mdef
                    item["mp_bonus"] = tier * 40
            
            # 添加特效（高级装备）
            if tier >= 7:
                effects = {}
                if class_name == "warrior":
                    if tier >= 7:
                        effects["crit_rate"] = round(0.01 * (tier - 6), 2)
                    if tier >= 9:
                        effects["crush_rate"] = round(0.01 * (tier - 8), 2)
                    if tier >= 10:
                        effects["extra_phys"] = (tier - 9) * 2
                else:  # mage
                    if tier >= 7:
                        effects["crit_rate"] = round(0.01 * (tier - 6), 2)
                    if tier >= 8:
                        effects["extra_magic"] = (tier - 7) * 3
                    if tier >= 10:
                        effects["ignore_magic_def"] = round(0.02 * (tier - 9), 2)
                
                if effects:
                    item["effects"] = effects
            
            equipment[item_id] = item
    
    return equipment

def generate_all_scatter_equipment():
    """生成所有散件装备"""
    all_equipment = {}
    
    tier_ranges = [
        (1, 1, 5), (2, 6, 10), (3, 11, 15), (4, 16, 20),
        (5, 21, 25), (6, 26, 30), (7, 31, 35), (8, 36, 40),
        (9, 41, 45), (10, 46, 50), (11, 51, 55), (12, 56, 60),
        (13, 61, 65), (14, 66, 70), (15, 71, 75), (16, 76, 80)
    ]
    
    for tier, level_min, level_max in tier_ranges:
        equipment = generate_scatter_equipment(tier, level_min, level_max)
        all_equipment.update(equipment)
    
    return all_equipment

def generate_set_equipment(tier, level_min, level_max):
    """生成套装装备"""
    equipment = {}
    
    for class_name, class_cn in CLASSES.items():
        set_name = SET_NAMES[tier][class_name]
        set_id = f"set_{tier}_{class_name}"
        
        for slot in SET_SLOTS:
            part_suffix = SET_PART_NAMES[slot]
            item_name = f"{set_name}{part_suffix}"
            item_id = f"{set_id}_{slot}"
            
            item = {
                "id": item_id,
                "name": item_name,
                "type": "weapon" if slot == "weapon" else "armor",
                "slot": slot,
                "class": [class_name],
                "level_req": level_min,
                "tier": tier,
                "set_id": set_id,
                "set_name": f"{set_name}套装",
                "buy_price": 0,
                "recycle_yuanbao": tier * 3 if tier >= 7 else 0,
                "recycle_gold": tier * 30 if tier < 7 else 0,
                "drop_only": tier >= 7
            }
            
            # 套装单件属性为散件的75%
            if slot == "weapon":
                if class_name == "warrior":
                    min_atk, max_atk = calculate_attribute(tier, 8)
                    item["attack_min"] = int(min_atk * 0.75)
                    item["attack_max"] = int(max_atk * 0.75)
                else:  # mage
                    min_mag, max_mag = calculate_attribute(tier, 10)
                    item["magic_min"] = int(min_mag * 0.75)
                    item["magic_max"] = int(max_mag * 0.75)
                    item["mp_bonus"] = int(tier * 40 * 0.75)
            else:  # armor
                if class_name == "warrior":
                    min_def, max_def = calculate_attribute(tier, 5)
                    item["defense_min"] = int(min_def * 0.75)
                    item["defense_max"] = int(max_def * 0.75)
                    item["hp_bonus"] = int(tier * 30 * 0.75)
                else:  # mage
                    min_mdef, max_mdef = calculate_attribute(tier, 6)
                    item["magic_defense_min"] = int(min_mdef * 0.75)
                    item["magic_defense_max"] = int(max_mdef * 0.75)
                    item["mp_bonus"] = int(tier * 40 * 0.75)
            
            equipment[item_id] = item
    
    return equipment

def generate_all_set_equipment():
    """生成所有套装装备"""
    all_equipment = {}
    
    # 套装从第2档开始（6-10级）
    tier_ranges = [
        (2, 6, 10), (3, 11, 15), (4, 16, 20),
        (5, 21, 25), (6, 26, 30), (7, 31, 35), (8, 36, 40),
        (9, 41, 45), (10, 46, 50), (11, 51, 55), (12, 56, 60),
        (13, 61, 65), (14, 66, 70), (15, 71, 75), (16, 76, 80)
    ]
    
    for tier, level_min, level_max in tier_ranges:
        equipment = generate_set_equipment(tier, level_min, level_max)
        all_equipment.update(equipment)
    
    return all_equipment

def generate_set_bonuses():
    """生成套装加成配置"""
    sets = {}
    
    # 套装从第2档开始
    tier_ranges = [
        (2, 6, 10), (3, 11, 15), (4, 16, 20),
        (5, 21, 25), (6, 26, 30), (7, 31, 35), (8, 36, 40),
        (9, 41, 45), (10, 46, 50), (11, 51, 55), (12, 56, 60),
        (13, 61, 65), (14, 66, 70), (15, 71, 75), (16, 76, 80)
    ]
    
    for tier, level_min, level_max in tier_ranges:
        for class_name, class_cn in CLASSES.items():
            set_name = SET_NAMES[tier][class_name]
            set_id = f"set_{tier}_{class_name}"
            
            # 计算基础属性值
            if class_name == "warrior":
                base_attack = tier * 8
                base_defense = tier * 5
                base_hp = tier * 30
            else:  # mage
                base_magic = tier * 10
                base_mdef = tier * 6
                base_mp = tier * 40
            
            set_config = {
                "id": set_id,
                "name": f"{set_name}套装",
                "class": [class_name],
                "tier": tier,
                "level_req": level_min,
                "bonuses": {}
            }
            
            # 2件套加成：+20%
            bonus_2 = {}
            if class_name == "warrior":
                bonus_2["attack"] = int(base_attack * 0.2)
                bonus_2["defense"] = int(base_defense * 0.2)
            else:
                bonus_2["magic"] = int(base_magic * 0.2)
                bonus_2["magic_defense"] = int(base_mdef * 0.2)
            set_config["bonuses"]["2"] = {"attributes": bonus_2}
            
            # 4件套加成：+50%
            bonus_4 = {}
            if class_name == "warrior":
                bonus_4["attack"] = int(base_attack * 0.5)
                bonus_4["defense"] = int(base_defense * 0.5)
                bonus_4["hp"] = int(base_hp * 0.5)
            else:
                bonus_4["magic"] = int(base_magic * 0.5)
                bonus_4["magic_defense"] = int(base_mdef * 0.5)
                bonus_4["mp"] = int(base_mp * 0.5)
            
            effects_4 = {}
            if tier >= 5:
                if class_name == "warrior":
                    effects_4["crit_rate"] = 0.02
                else:
                    effects_4["crit_rate"] = 0.02
            
            set_config["bonuses"]["4"] = {
                "attributes": bonus_4,
                "effects": effects_4 if effects_4 else {}
            }
            
            # 6件套加成：+100%
            bonus_6 = {}
            if class_name == "warrior":
                bonus_6["attack"] = int(base_attack * 1.0)
                bonus_6["defense"] = int(base_defense * 1.0)
                bonus_6["hp"] = int(base_hp * 1.0)
            else:
                bonus_6["magic"] = int(base_magic * 1.0)
                bonus_6["magic_defense"] = int(base_mdef * 1.0)
                bonus_6["mp"] = int(base_mp * 1.0)
            
            effects_6 = {}
            if tier >= 5:
                if class_name == "warrior":
                    effects_6["crit_rate"] = 0.05
                    effects_6["crush_rate"] = 0.03
                else:
                    effects_6["crit_rate"] = 0.05
                    effects_6["extra_magic"] = tier
            
            set_config["bonuses"]["6"] = {
                "attributes": bonus_6,
                "effects": effects_6 if effects_6 else {}
            }
            
            # 8件套加成：+150%
            bonus_8 = {}
            if class_name == "warrior":
                bonus_8["attack"] = int(base_attack * 1.5)
                bonus_8["defense"] = int(base_defense * 1.5)
                bonus_8["hp"] = int(base_hp * 1.5)
            else:
                bonus_8["magic"] = int(base_magic * 1.5)
                bonus_8["magic_defense"] = int(base_mdef * 1.5)
                bonus_8["mp"] = int(base_mp * 1.5)
            
            effects_8 = {}
            if tier >= 5:
                if class_name == "warrior":
                    effects_8["crit_rate"] = 0.08
                    effects_8["crush_rate"] = 0.05
                    effects_8["extra_phys"] = tier * 2
                else:
                    effects_8["crit_rate"] = 0.08
                    effects_8["extra_magic"] = tier * 2
                    effects_8["ignore_magic_def"] = 0.05
            
            set_config["bonuses"]["8"] = {
                "attributes": bonus_8,
                "effects": effects_8 if effects_8 else {}
            }
            
            # 9件套加成：+200%（终极加成）
            bonus_9 = {}
            if class_name == "warrior":
                bonus_9["attack"] = int(base_attack * 2.0)
                bonus_9["defense"] = int(base_defense * 2.0)
                bonus_9["hp"] = int(base_hp * 2.0)
            else:
                bonus_9["magic"] = int(base_magic * 2.0)
                bonus_9["magic_defense"] = int(base_mdef * 2.0)
                bonus_9["mp"] = int(base_mp * 2.0)
            
            effects_9 = {}
            if tier >= 5:
                if class_name == "warrior":
                    effects_9["crit_rate"] = 0.12
                    effects_9["crush_rate"] = 0.08
                    effects_9["extra_phys"] = tier * 3
                    effects_9["damage_reduction"] = 0.05
                else:
                    effects_9["crit_rate"] = 0.12
                    effects_9["extra_magic"] = tier * 3
                    effects_9["ignore_magic_def"] = 0.1
                    effects_9["mp_regen"] = tier * 2
            
            set_config["bonuses"]["9"] = {
                "attributes": bonus_9,
                "effects": effects_9 if effects_9 else {},
                "description": f"{set_name}套装终极加成"
            }
            
            sets[set_id] = set_config
    
    return sets

def main():
    """主函数"""
    print("=" * 60)
    print("装备生成脚本 - 根据改造文档生成所有装备")
    print("=" * 60)
    
    # 生成散件装备
    print("\n[1/3] 生成散件装备...")
    scatter_equipment = generate_all_scatter_equipment()
    print(f"[OK] 生成了 {len(scatter_equipment)} 件散件装备")
    
    # 分类保存散件
    scatter_weapons = {k: v for k, v in scatter_equipment.items() if v["type"] == "weapon"}
    scatter_armors = {k: v for k, v in scatter_equipment.items() if v["type"] == "armor"}
    
    # 生成套装装备
    print("\n[2/3] 生成套装装备...")
    set_equipment = generate_all_set_equipment()
    print(f"[OK] 生成了 {len(set_equipment)} 件套装装备")
    
    # 分类套装装备
    set_weapons = {k: v for k, v in set_equipment.items() if v["type"] == "weapon"}
    set_armors = {k: v for k, v in set_equipment.items() if v["type"] == "armor"}
    
    # 生成套装配置
    print("\n[3/3] 生成套装配置...")
    set_bonuses = generate_set_bonuses()
    print(f"[OK] 生成了 {len(set_bonuses)} 个套装配置")
    
    # 合并武器和防具
    all_weapons = {**scatter_weapons, **set_weapons}
    all_armors = {**scatter_armors, **set_armors}
    
    # 保存文件
    print("\n保存文件...")
    
    # 保存武器
    with open("data/items/weapons_new.json", "w", encoding="utf-8") as f:
        json.dump(all_weapons, f, ensure_ascii=False, indent=2)
    print(f"[OK] 武器数据已保存: weapons_new.json ({len(all_weapons)} 件)")
    
    # 保存防具
    with open("data/items/armors_new.json", "w", encoding="utf-8") as f:
        json.dump(all_armors, f, ensure_ascii=False, indent=2)
    print(f"[OK] 防具数据已保存: armors_new.json ({len(all_armors)} 件)")
    
    # 保存套装装备（单独文件）
    with open("data/items/set_items.json", "w", encoding="utf-8") as f:
        json.dump(set_equipment, f, ensure_ascii=False, indent=2)
    print(f"[OK] 套装装备已保存: set_items.json ({len(set_equipment)} 件)")
    
    # 保存套装配置
    with open("data/config/sets.json", "w", encoding="utf-8") as f:
        json.dump(set_bonuses, f, ensure_ascii=False, indent=2)
    print(f"[OK] 套装配置已保存: sets.json ({len(set_bonuses)} 个套装)")
    
    # 统计信息
    print("\n" + "=" * 60)
    print("生成完成！统计信息：")
    print("=" * 60)
    print(f"散件装备: {len(scatter_equipment)} 件")
    print(f"  - 武器: {len(scatter_weapons)} 件")
    print(f"  - 防具: {len(scatter_armors)} 件")
    print(f"\n套装装备: {len(set_equipment)} 件")
    print(f"  - 武器: {len(set_weapons)} 件")
    print(f"  - 防具: {len(set_armors)} 件")
    print(f"\n套装配置: {len(set_bonuses)} 个")
    print(f"\n总计装备: {len(scatter_equipment) + len(set_equipment)} 件")
    print("=" * 60)

if __name__ == "__main__":
    main()
