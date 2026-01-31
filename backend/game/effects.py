"""装备特效计算模块 - 封装所有战斗特效的计算逻辑"""
import random
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

# 特效配置 - 可在此处调整各特效的基础参数
EFFECT_CONFIG = {
    "crush_multiplier": 1.5,      # 压碎伤害倍率
    "crit_multiplier": 1.5,       # 暴击伤害倍率
    "default_crit_rate": 0.05,    # 默认暴击率
    "default_hit_rate": 0.95,     # 默认命中率
    "default_dodge_rate": 0.05,   # 默认闪避率
    "max_damage_reduction": 0.3,  # 最大减伤比例（降低）
    "max_block_rate": 0.15,       # 最大格挡几率（降低）
    "max_lifesteal": 0.2,         # 最大吸血比例（降低）
    "max_block_amount": 0.3,      # 最大格挡伤害比例
}

# 特效中文名称映射
EFFECT_NAMES = {
    "double_attack": "双击",
    "hit_rate": "命中",
    "dodge_rate": "闪避",
    "crush_rate": "压碎",
    "lifesteal": "吸血",
    "reflect": "反弹",
    "hp_on_hit": "击回HP",
    "mp_on_hit": "击回MP",
    "block_rate": "格挡",
    "block_amount": "格挡量",
    "extra_phys": "附物伤",
    "extra_magic": "附魔伤",
    "damage_reduction": "减伤",
    "stun_rate": "眩晕",
    "splash_rate": "溅射",
    "poison_damage": "毒伤",
    "poison_rounds": "毒回合",
    "ignore_defense": "穿防",
    "ignore_magic_def": "穿魔防",
    "crit_rate": "暴击",
    "crit_damage": "暴伤",
}

@dataclass
class EffectResult:
    """特效计算结果"""
    damage: int = 0
    heal_hp: int = 0
    heal_mp: int = 0
    is_crit: bool = False
    is_crush: bool = False
    is_blocked: bool = False
    is_dodged: bool = False
    is_missed: bool = False
    is_stunned: bool = False
    reflect_damage: int = 0
    splash_damage: int = 0
    poison_damage: int = 0
    poison_rounds: int = 0
    extra_attacks: int = 0
    logs: List[str] = field(default_factory=list)

class EffectCalculator:
    """特效计算器 - 处理所有装备特效"""
    
    @staticmethod
    def get_equipment_effects(equipment: List[dict]) -> dict:
        """从装备列表中汇总所有特效"""
        effects = {
            "double_attack": 0,      # 双次攻击几率
            "hit_rate": 0,           # 命中率加成
            "dodge_rate": 0,         # 闪避率加成
            "crush_rate": 0,         # 压碎几率
            "lifesteal": 0,          # 吸血比例
            "reflect": 0,            # 反弹比例
            "hp_on_hit": 0,          # 击中回复HP
            "mp_on_hit": 0,          # 击中回复MP
            "block_rate": 0,         # 格挡几率
            "block_amount": 0,       # 格挡伤害比例
            "extra_phys": 0,         # 附加物理伤害
            "extra_magic": 0,        # 附加魔法伤害
            "damage_reduction": 0,   # 减伤比例
            "stun_rate": 0,          # 眩晕几率
            "splash_rate": 0,        # 溅射比例
            "poison_damage": 0,      # 毒伤每回合
            "poison_rounds": 0,      # 毒伤持续回合
            "ignore_defense": 0,     # 忽略防御比例
            "ignore_magic_def": 0,   # 忽略魔御比例
            "crit_rate": 0,          # 暴击率加成
            "crit_damage": 0,        # 暴击伤害加成
        }
        
        for equip in equipment:
            if not equip:
                continue
            info = equip.get("info", equip)
            fx = info.get("effects", {})
            for key in effects:
                if key in fx:
                    effects[key] += fx[key]
        
        return effects
    
    @staticmethod
    def calculate_hit(attacker_effects: dict, defender_effects: dict) -> Tuple[bool, bool]:
        """计算命中和闪避，返回 (是否命中, 是否闪避)"""
        hit_rate = EFFECT_CONFIG["default_hit_rate"] + attacker_effects.get("hit_rate", 0)
        dodge_rate = EFFECT_CONFIG["default_dodge_rate"] + defender_effects.get("dodge_rate", 0)
        
        # 命中判定
        if random.random() > hit_rate:
            return False, False  # 未命中
        
        # 闪避判定
        if random.random() < dodge_rate:
            return True, True  # 命中但被闪避
        
        return True, False  # 命中且未闪避
    
    @staticmethod
    def calculate_crit(attacker_effects: dict) -> Tuple[bool, float]:
        """计算暴击，返回 (是否暴击, 暴击倍率)"""
        crit_rate = EFFECT_CONFIG["default_crit_rate"] + attacker_effects.get("crit_rate", 0)
        crit_mult = EFFECT_CONFIG["crit_multiplier"] + attacker_effects.get("crit_damage", 0)
        
        if random.random() < crit_rate:
            return True, crit_mult
        return False, 1.0
    
    @staticmethod
    def calculate_crush(attacker_effects: dict) -> Tuple[bool, float]:
        """计算压碎，返回 (是否压碎, 压碎倍率)"""
        crush_rate = attacker_effects.get("crush_rate", 0)
        if crush_rate > 0 and random.random() < crush_rate:
            return True, EFFECT_CONFIG["crush_multiplier"]
        return False, 1.0
    
    @staticmethod
    def calculate_block(defender_effects: dict, damage: int) -> Tuple[bool, int]:
        """计算格挡，返回 (是否格挡, 格挡后伤害)"""
        block_rate = min(defender_effects.get("block_rate", 0), EFFECT_CONFIG["max_block_rate"])
        block_amount = min(defender_effects.get("block_amount", 0.2), EFFECT_CONFIG["max_block_amount"])
        
        if block_rate > 0 and random.random() < block_rate:
            blocked_damage = int(damage * (1 - block_amount))
            return True, max(int(damage * 0.7), blocked_damage)  # 格挡最多减少30%伤害
        return False, damage
    
    @staticmethod
    def apply_damage_reduction(defender_effects: dict, damage: int) -> int:
        """应用减伤"""
        reduction = min(defender_effects.get("damage_reduction", 0), EFFECT_CONFIG["max_damage_reduction"])
        return max(int(damage * 0.7), int(damage * (1 - reduction)))  # 减伤最多减少30%伤害
    
    @staticmethod
    def calculate_lifesteal(attacker_effects: dict, damage: int) -> int:
        """计算吸血回复量"""
        lifesteal = min(attacker_effects.get("lifesteal", 0), EFFECT_CONFIG["max_lifesteal"])
        return int(damage * lifesteal * 0.5)  # 吸血效果减半
    
    @staticmethod
    def calculate_reflect(defender_effects: dict, damage: int) -> int:
        """计算反弹伤害"""
        reflect = defender_effects.get("reflect", 0)
        return int(damage * reflect)
    
    @staticmethod
    def calculate_on_hit(attacker_effects: dict) -> Tuple[int, int]:
        """计算击中回复，返回 (HP回复, MP回复)"""
        return attacker_effects.get("hp_on_hit", 0), attacker_effects.get("mp_on_hit", 0)
    
    @staticmethod
    def calculate_stun(attacker_effects: dict) -> bool:
        """计算是否眩晕"""
        stun_rate = attacker_effects.get("stun_rate", 0)
        return stun_rate > 0 and random.random() < stun_rate
    
    @staticmethod
    def calculate_splash(attacker_effects: dict, damage: int) -> int:
        """计算溅射伤害"""
        splash_rate = attacker_effects.get("splash_rate", 0)
        return int(damage * splash_rate)
    
    @staticmethod
    def get_poison(attacker_effects: dict) -> Tuple[int, int]:
        """获取毒伤数据，返回 (每回合伤害, 持续回合)"""
        return attacker_effects.get("poison_damage", 0), attacker_effects.get("poison_rounds", 0)
    
    @staticmethod
    def calculate_defense_penetration(attacker_effects: dict, defense: int, is_magic: bool = False) -> int:
        """计算忽略防御后的有效防御值"""
        if is_magic:
            ignore = attacker_effects.get("ignore_magic_def", 0)
        else:
            ignore = attacker_effects.get("ignore_defense", 0)
        return max(0, int(defense * (1 - ignore)))
    
    @staticmethod
    def get_extra_damage(attacker_effects: dict) -> Tuple[int, int]:
        """获取附加伤害，返回 (物理附伤, 魔法附伤)"""
        return attacker_effects.get("extra_phys", 0), attacker_effects.get("extra_magic", 0)
    
    @staticmethod
    def check_double_attack(attacker_effects: dict) -> int:
        """检查双次攻击，返回额外攻击次数"""
        double_rate = attacker_effects.get("double_attack", 0)
        if double_rate > 0 and random.random() < double_rate:
            return 1
        return 0
    
    @classmethod
    def process_attack(cls, attacker: dict, defender: dict, base_damage: int, 
                       attacker_equip: List[dict] = None, defender_equip: List[dict] = None,
                       is_magic: bool = False) -> EffectResult:
        """处理一次完整的攻击，应用所有特效"""
        result = EffectResult()
        atk_fx = cls.get_equipment_effects(attacker_equip or [])
        def_fx = cls.get_equipment_effects(defender_equip or [])
        
        # 1. 命中/闪避判定
        hit, dodged = cls.calculate_hit(atk_fx, def_fx)
        if not hit:
            result.is_missed = True
            result.logs.append("攻击未命中!")
            return result
        if dodged:
            result.is_dodged = True
            result.logs.append("攻击被闪避!")
            return result
        
        damage = base_damage
        
        # 2. 忽略防御计算（已在base_damage计算时考虑）
        
        # 3. 暴击判定
        is_crit, crit_mult = cls.calculate_crit(atk_fx)
        if is_crit:
            damage = int(damage * crit_mult)
            result.is_crit = True
            result.logs.append(f"暴击x{crit_mult:.1f}")
        
        # 4. 压碎判定
        is_crush, crush_mult = cls.calculate_crush(atk_fx)
        if is_crush:
            damage = int(damage * crush_mult)
            result.is_crush = True
            result.logs.append(f"压碎x{crush_mult:.1f}")
        
        # 5. 附加伤害
        extra_phys, extra_magic = cls.get_extra_damage(atk_fx)
        if extra_phys > 0:
            damage += int(extra_phys)
            result.logs.append(f"附伤+{int(extra_phys)}")
        if extra_magic > 0:
            damage += int(extra_magic)
            result.logs.append(f"魔伤+{int(extra_magic)}")
        
        # 6. 格挡判定
        blocked, damage = cls.calculate_block(def_fx, damage)
        if blocked:
            result.is_blocked = True
            result.logs.append("攻击被格挡!")
        
        # 7. 减伤
        damage = cls.apply_damage_reduction(def_fx, damage)
        
        result.damage = damage
        
        # 8. 吸血
        lifesteal_hp = cls.calculate_lifesteal(atk_fx, damage)
        if lifesteal_hp > 0:
            result.heal_hp += lifesteal_hp
            result.logs.append(f"吸血+{lifesteal_hp}HP")
        
        # 9. 击中回复
        hp_on_hit, mp_on_hit = cls.calculate_on_hit(atk_fx)
        hp_on_hit = int(hp_on_hit)
        mp_on_hit = int(mp_on_hit)
        if hp_on_hit > 0:
            result.heal_hp += hp_on_hit
            result.logs.append(f"击回+{hp_on_hit}HP")
        if mp_on_hit > 0:
            result.heal_mp += mp_on_hit
            result.logs.append(f"击回+{mp_on_hit}MP")
        
        # 10. 反弹伤害
        result.reflect_damage = cls.calculate_reflect(def_fx, damage)
        if result.reflect_damage > 0:
            result.logs.append(f"反弹{result.reflect_damage}")
        
        # 11. 眩晕判定
        result.is_stunned = cls.calculate_stun(atk_fx)
        if result.is_stunned:
            result.logs.append("眩晕")
        
        # 12. 溅射伤害
        result.splash_damage = cls.calculate_splash(atk_fx, damage)
        
        # 13. 毒伤 (1/10概率触发)
        poison_dmg, poison_rounds = cls.get_poison(atk_fx)
        if poison_dmg > 0 and poison_rounds > 0 and random.randint(1, 10) == 1:
            result.poison_damage = int(poison_dmg)
            result.poison_rounds = int(poison_rounds)
            result.logs.append(f"毒伤{int(poison_dmg)}x{int(poison_rounds)}回合")
        
        # 14. 双次攻击
        result.extra_attacks = cls.check_double_attack(atk_fx)
        if result.extra_attacks > 0:
            result.logs.append("双击")
        
        return result


# 品质加成配置
QUALITY_CONFIG = {
    "white": {"name": "普通", "bonus": 1.0, "effect_bonus": 0, "drop_weight": 50},
    "green": {"name": "优秀", "bonus": 1.1, "effect_bonus": 0.1, "drop_weight": 30},
    "blue": {"name": "精良", "bonus": 1.25, "effect_bonus": 0.2, "drop_weight": 15},
    "purple": {"name": "史诗", "bonus": 1.5, "effect_bonus": 0.35, "drop_weight": 4},
    "red": {"name": "传说", "bonus": 2.0, "effect_bonus": 0.5, "drop_weight": 1},
}

def apply_quality_bonus(item: dict, quality: str) -> dict:
    """应用品质加成到物品属性"""
    config = QUALITY_CONFIG.get(quality, QUALITY_CONFIG["white"])
    bonus = config["bonus"]
    effect_bonus = config["effect_bonus"]
    
    result = item.copy()
    
    # 数值属性加成
    numeric_attrs = ["attack_min", "attack_max", "magic_min", "magic_max", 
                     "defense_min", "defense_max", "magic_defense_min", "magic_defense_max",
                     "hp_bonus", "mp_bonus"]
    for attr in numeric_attrs:
        if attr in result:
            result[attr] = int(result[attr] * bonus)
    
    # 特效加成
    if "effects" in result:
        effects = result["effects"].copy()
        # 整数类型特效
        int_effects = {"poison_damage", "poison_rounds", "extra_phys", "extra_magic", "hp_on_hit", "mp_on_hit"}
        for key, value in effects.items():
            if isinstance(value, (int, float)) and value > 0:
                new_val = value * (1 + effect_bonus)
                effects[key] = int(new_val) if key in int_effects else round(new_val, 3)
        result["effects"] = effects
    
    return result

def roll_quality(base_rate: float = 1.0) -> str:
    """根据掉率随机品质 - 掉率越低品质越高概率"""
    weights = []
    qualities = []
    
    # 基础掉率越低，高品质权重越高
    rarity_boost = min(0.5, (1 - base_rate) * 0.8)
    
    for q, cfg in QUALITY_CONFIG.items():
        qualities.append(q)
        weight = cfg["drop_weight"]
        if q in ["purple", "red"]:
            weight *= (1 + rarity_boost * 3)
        elif q == "blue":
            weight *= (1 + rarity_boost * 2)
        weights.append(weight)
    
    total = sum(weights)
    roll = random.random() * total
    cumulative = 0
    
    for q, w in zip(qualities, weights):
        cumulative += w
        if roll < cumulative:
            return q
    
    return "white"


def calculate_set_bonuses(equipment: list, sets_config: dict, include_full_config: bool = False) -> dict:
    """计算套装加成
    Args:
        equipment: 装备列表，每个装备需要有info.set_id
        sets_config: 套装配置数据
        include_full_config: 是否返回完整套装配置（用于前端显示）
    Returns:
        {
            "active_sets": [{"set_id": str, "name": str, "count": int, "bonuses": dict, "full_bonuses": dict}],
            "total_stats": {"hp_bonus": int, "defense": int, ...},
            "total_effects": {"crit_rate": float, ...}
        }
    """
    # 统计每个套装的件数
    set_counts = {}
    for equip in equipment:
        if not equip:
            continue
        info = equip.get("info", equip)
        set_id = info.get("set_id")
        if set_id:
            set_counts[set_id] = set_counts.get(set_id, 0) + 1
    
    active_sets = []
    total_stats = {}
    total_effects = {}
    
    for set_id, count in set_counts.items():
        set_cfg = sets_config.get(set_id)
        if not set_cfg:
            continue
        
        set_info = {"set_id": set_id, "name": set_cfg.get("name", set_id), "count": count, "bonuses": {}}
        
        # 返回完整套装配置（包含所有阶段）
        if include_full_config:
            set_info["full_bonuses"] = set_cfg.get("bonuses", {})
        
        # 检查各阶段加成（支持2/4/6/8/9件）
        for threshold in ["2", "4", "6", "8", "9"]:
            if count >= int(threshold) and threshold in set_cfg.get("bonuses", {}):
                bonus = set_cfg["bonuses"][threshold]
                set_info["bonuses"][threshold] = bonus

                # 累加属性
                for key, val in bonus.items():
                    if key == "effects":
                        for ek, ev in val.items():
                            total_effects[ek] = total_effects.get(ek, 0) + ev
                    else:
                        total_stats[key] = total_stats.get(key, 0) + val
        
        if count >= 1:  # 只要有1件就显示套装信息
            active_sets.append(set_info)
    
    return {"active_sets": active_sets, "total_stats": total_stats, "total_effects": total_effects}