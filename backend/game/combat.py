
import random
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from fractions import Fraction
from .effects import EffectCalculator, roll_quality, apply_quality_bonus, roll_item_attributes, EFFECT_CONFIG, EFFECT_NAMES
from backend.config import game_config

@dataclass
class CombatResult:
    victory: bool
    logs: List[str]
    exp_gained: int
    gold_gained: int
    drops: List[dict]
    player_died: bool
    skills_used: List[str]
    passive_skills: List[str] = field(default_factory=list)
    summon_died: bool = False

@dataclass
class PoisonState:
    """毒伤状态"""
    damage: int
    rounds: int

class CombatEngine:
    """战斗引擎 - 支持装备特效系统"""
    
    QUALITY_DROP_BONUS = {"white": 1.0, "green": 1.5, "blue": 2.0, "purple": 3.0, "orange": 5.0}
    
    @staticmethod
    def calculate_damage(attacker: dict, defender: dict, is_magic: bool = False, 
                        attacker_effects: dict = None, defender_effects: dict = None) -> int:
        """计算伤害（支持特效系统）"""
        attacker_effects = attacker_effects or {}
        defender_effects = defender_effects or {}
        
        # 获取攻击值
        if is_magic:
            atk_min = attacker.get("magic_min", attacker.get("magic", attacker.get("attack", 10)))
            atk_max = attacker.get("magic_max", attacker.get("magic", attacker.get("attack", 10)))
            def_min = defender.get("magic_defense_min", defender.get("magic_defense", 0))
            def_max = defender.get("magic_defense_max", defender.get("magic_defense", 0))
        else:
            atk_min = attacker.get("attack_min", attacker.get("attack", 10))
            atk_max = attacker.get("attack_max", attacker.get("attack", 10))
            def_min = defender.get("defense_min", defender.get("defense", 0))
            def_max = defender.get("defense_max", defender.get("defense", 0))
        
        attack = random.randint(int(atk_min), max(int(atk_min), int(atk_max)))
        defense = random.randint(int(def_min), max(int(def_min), int(def_max)))
        
        # 应用忽略防御
        defense = EffectCalculator.calculate_defense_penetration(attacker_effects, defense, is_magic)
        
        # 减伤公式
        reduction = min(0.8, defense / (defense + 100))
        base_damage = int(attack * (1 - reduction))
        base_damage = max(1, base_damage)
        
        # 随机浮动 ±10%
        variance = random.uniform(0.9, 1.1)
        return max(1, int(base_damage * variance))
    
    @staticmethod
    def calculate_skill_power(player: dict, skill: dict) -> int:
        """根据职业计算技能威力"""
        char_class = player.get("char_class", "warrior")
        skill_level = skill.get("level", 1)
        level_mult = 1 + (skill_level - 1) * 0.5
        
        if char_class == "warrior":
            base = (player.get("attack_min", 10) + player.get("attack_max", 10)) // 2
        else:
            base = (player.get("magic_min", 10) + player.get("magic_max", 10)) // 2
        
        return int(base * level_mult)
    
    @staticmethod
    def calculate_heal_amount(player: dict, skill: dict) -> int:
        """计算治愈量"""
        skill_level = skill.get("level", 1)
        magic = (player.get("magic_min", 0) + player.get("magic_max", 0)) // 2
        base_heal = skill.get("effect", {}).get("heal_hp", 50)
        return int((base_heal + magic * 0.5) * (1 + (skill_level - 1) * 0.3))
    
    @staticmethod
    def calculate_poison_damage(player: dict, skill: dict) -> tuple:
        """计算施毒术伤害 - 与技能等级和魔法值相关"""
        skill_level = skill.get("level", 1)
        magic = (player.get("magic_min", 0) + player.get("magic_max", 0)) // 2
        base_damage = skill.get("effect", {}).get("poison_damage", 10)
        duration = skill.get("effect", {}).get("duration", 5)
        # 毒伤 = (基础伤害 + 魔法值*0.3) * (1 + (技能等级-1)*0.5)
        damage = int((base_damage + magic * 0.3) * (1 + (skill_level - 1) * 0.5))
        # 持续回合随等级增加
        rounds = duration + (skill_level - 1)
        return damage, rounds
    
    @staticmethod
    def create_summon(player: dict, skill: dict) -> dict:
        """创建召唤物 - 属性跟随玩家属性计算"""
        skill_level = skill.get("level", 1)
        summon_type = skill.get("effect", {}).get("summon", "skeleton")

        # 获取玩家基础属性
        player_hp = player.get("max_hp", 100)
        player_mp = player.get("max_mp", 50)
        player_atk = (player.get("attack_min", 0) + player.get("attack_max", 0)) // 2
        player_def = player.get("defense", 0)
        player_magic = (player.get("magic_min", 0) + player.get("magic_max", 0)) // 2
        player_magic_def = player.get("magic_defense", 0)
        player_level = player.get("level", 1)

        # 技能等级加成 (每级+15%)
        level_bonus = 1 + (skill_level - 1) * 0.15

        # 根据召唤类型设置属性比例
        if summon_type == "skeleton":
            # 骷髅战士 - 入门召唤物
            hp_ratio = 0.2
            atk_ratio = 0.25
            def_ratio = 0.3
            magdef_ratio = 0.2
            summon_name = "骷髅战士"
        elif summon_type == "holy_dog":
            # 神兽 - 高血量坦克型
            hp_ratio = 0.6
            atk_ratio = 0.4
            def_ratio = 0.5
            magdef_ratio = 0.4
            summon_name = "神兽"
        elif summon_type == "kylin":
            # 麒麟 - 完美型召唤物
            hp_ratio = 0.8
            atk_ratio = 0.6
            def_ratio = 0.7
            magdef_ratio = 0.7
            summon_name = "麒麟"
        else:
            # 默认/未知类型
            hp_ratio = 0.3
            atk_ratio = 0.3
            def_ratio = 0.3
            magdef_ratio = 0.3
            summon_name = "召唤物"

        # 计算召唤物属性 (基于玩家属性 + 技能等级加成)
        # 高级玩家额外加成: 每10级额外5%
        level_extra_bonus = 1 + (player_level // 10) * 0.05

        summon_hp = int(player_hp * hp_ratio * level_bonus * level_bonus)
        summon_atk = int(max(player_atk, player_magic) * atk_ratio * level_bonus * level_bonus)
        summon_def = int(player_def * def_ratio * level_bonus * level_bonus)
        summon_magdef = int(player_magic_def * magdef_ratio * level_bonus * level_bonus)

        # 确保最低属性
        summon_hp = max(summon_hp, 50 + player_level * 10)
        summon_atk = max(summon_atk, 5 + player_level * 2)
        summon_def = max(summon_def, 2 + player_level)
        summon_magdef = max(summon_magdef, 2 + player_level)

        return {
            "name": summon_name,
            "type": summon_type,
            "hp": summon_hp,
            "max_hp": summon_hp,
            "attack": summon_atk,
            "defense": summon_def,
            "magic_defense": summon_magdef,
            "alive": True
        }
    
    @staticmethod
    def pve_combat(player: dict, monsters: list, skills: List[dict] = None, 
                   drop_groups: List[str] = None, data_loader=None, 
                   inventory: List[dict] = None, summon: dict = None, 
                   disabled_skills: List[str] = None, equipment: List[dict] = None) -> CombatResult:
        """PVE战斗 - 支持装备特效"""
        if isinstance(monsters, dict):
            monsters = [monsters]
        
        logs = []
        player_hp = player.get("max_hp", 100)
        player_mp = player.get("max_mp", 50)
        player_max_hp = player.get("max_hp", 100)
        player_max_mp = player.get("max_mp", 50)
        player_name = player.get("name", "玩家")
        char_class = player.get("char_class", "warrior")
        disabled_skills = disabled_skills or []
        equipment = equipment or []
        
        # 获取玩家装备特效
        player_effects = EffectCalculator.get_equipment_effects(equipment)
        
        # 显示玩家装备特效（如果有）
        active_effects = {k: v for k, v in player_effects.items() if v > 0}
        if active_effects:
            effect_strs = []
            for k, v in active_effects.items():
                name = EFFECT_NAMES.get(k, k)
                if k in ["hp_on_hit", "mp_on_hit", "extra_phys", "extra_magic", "poison_damage", "poison_rounds"]:
                    effect_strs.append(f"{name}+{int(v)}")
                else:
                    effect_strs.append(f"{name}:{int(v*100)}%")
            logs.append(f"⚔️ 装备特效: {', '.join(effect_strs)}")
        
        # 初始化怪物状态
        monster_states = []
        for m in monsters:
            quality = m.get("quality", "white")
            quality_bonus = {"white": 1.0, "green": 1.2, "blue": 1.5, "purple": 2.0, "orange": 3.0}.get(quality, 1.0)
            damage_type = m.get("damage_type", "physical")
            monster_states.append({
                "name": m.get("name", "怪物"),
                "hp": int(m.get("hp", 50) * quality_bonus),
                "max_hp": int(m.get("hp", 50) * quality_bonus),
                "attack": int(m.get("attack", 10) * quality_bonus),
                "defense": int(m.get("defense", 0) * quality_bonus),
                "magic_defense": int(m.get("magic_defense", m.get("defense", 0) * 0.5) * quality_bonus),
                "exp": int(m.get("exp", 10) * quality_bonus),
                "gold": int(m.get("gold", 5) * quality_bonus),
                "drops": m.get("drops", []),
                "quality": quality,
                "is_boss": m.get("is_boss", False),
                "damage_type": damage_type,
                "poison": None,  # 毒伤状态
                "burn": None,  # 灼烧状态
                "stunned": False  # 眩晕状态
            })
        
        for idx, m in enumerate(monster_states):
            m['idx'] = idx
        
        monster_names = ", ".join([f"{m['name']}[{m['quality']}]" for m in monster_states])
        logs.append(f"⚔️ 战斗开始: {player_name} vs {monster_names}")
        monster_hp_list = "|".join([f"#{m['idx']}{m['name']}[{m['quality']}]:{m['hp']}/{m['max_hp']}" for m in monster_states])
        logs.append(f"COMBAT_INIT|{player_hp}/{player_max_hp}|{player_mp}/{player_max_mp}|{monster_hp_list}")
        
        round_num = 0
        max_rounds = 100
        skills_used = []
        passive_skills = []
        player_poison = None  # 玩家毒伤状态
        player_stunned = False
        player_invisible = 0  # 隐身剩余回合数
        magic_shield_rounds = 0  # 魔法盾剩余回合数
        magic_shield_reduction = 0.0  # 魔法盾减伤比例
        
        # 分离技能
        active_skills = []
        for skill in (skills or []):
            skill_id = skill.get("skill_id", skill.get("id", ""))
            if skill_id in disabled_skills:
                continue
            if skill.get("type") == "passive":
                if skill_id:
                    passive_skills.append(skill_id)
            else:
                active_skills.append(skill)
        
        available_skills = sorted(active_skills, key=lambda s: s.get("level_req", 1), reverse=True)
        skill_cooldowns = {}
        
        # 召唤物状态
        summon_state = None
        summon_died = False
        if summon and summon.get("alive"):
            summon_state = summon.copy()
            logs.append(f"🐾 {summon_state['name']} 参战 (HP:{summon_state['hp']})")
        
        # 药水
        hp_potions = []
        mp_potions = []
        if inventory:
            for item in inventory:
                info = item.get("info", {})
                if info.get("type") == "consumable":
                    if info.get("effect", {}).get("heal_hp"):
                        hp_potions.append(item)
                    if info.get("effect", {}).get("heal_mp"):
                        mp_potions.append(item)
            hp_potions.sort(key=lambda x: x.get("info", {}).get("effect", {}).get("heal_hp", 0))
            mp_potions.sort(key=lambda x: x.get("info", {}).get("effect", {}).get("heal_mp", 0))
        
        while player_hp > 0 and any(m["hp"] > 0 for m in monster_states) and round_num < max_rounds:
            round_num += 1
            logs.append(f"--- 第{round_num}回合 ---")
            
            # 处理玩家毒伤
            if player_poison and player_poison.rounds > 0:
                player_hp -= player_poison.damage
                player_poison.rounds -= 1
                logs.append(f"🧪 中毒! 受到 {player_poison.damage} 点毒伤")
                if player_poison.rounds <= 0:
                    player_poison = None
            
            # 处理怪物毒伤
            for m in monster_states:
                if m["hp"] > 0 and m.get("poison") and m["poison"].rounds > 0:
                    m["hp"] -= m["poison"].damage
                    m["poison"].rounds -= 1
                    logs.append(f"🧪 {m['name']} 中毒! 受到 {m['poison'].damage} 点毒伤")
                    if m["hp"] <= 0:
                        logs.append(f"💀 {m['name']} 被毒死!")
                    if m["poison"].rounds <= 0:
                        m["poison"] = None
            
            # 处理怪物灼烧
            for m in monster_states:
                if m["hp"] > 0 and m.get("burn") and m["burn"].rounds > 0:
                    m["hp"] -= m["burn"].damage
                    m["burn"].rounds -= 1
                    logs.append(f"🔥 {m['name']} 灼烧! 受到 {m['burn'].damage} 点火焰伤害")
                    if m["hp"] <= 0:
                        logs.append(f"💀 {m['name']} 被烧死!")
                    if m["burn"].rounds <= 0:
                        m["burn"] = None
            
            # 圣言术判定（法师被动技能）
            if char_class == "mage" and "holy_word" in passive_skills:
                alive_targets = [m for m in monster_states if m["hp"] > 0]
                if alive_targets:
                    # 获取圣言术技能等级
                    holy_word_skill = next((s for s in (skills or []) if s.get("skill_id") == "holy_word"), None)
                    if holy_word_skill:
                        skill_level = holy_word_skill.get("level", 1)
                        # 根据等级计算触发率：1级1%，2级2%，3级3%
                        trigger_rate = skill_level * 0.01
                        if random.random() < trigger_rate:
                            target = random.choice(alive_targets)
                            target["hp"] = 0
                            logs.append(f"✨ 圣言术发动! {target['name']} 被神圣之力瞬间消灭!")
            
            # 检查玩家眩晕
            if player_stunned:
                logs.append("😵 你被眩晕，无法行动!")
                player_stunned = False
            else:
                # 自动使用药水（HP一半以下使用，可重复使用）
                if player_hp < player_max_hp * 0.3 and hp_potions:
                    potion = hp_potions[0]
                    heal = potion.get("info", {}).get("effect", {}).get("heal_hp", 0)
                    player_hp = min(player_max_hp, player_hp + heal)
                    potion["used_count"] = potion.get("used_count", 0) + 1
                    logs.append(f"🧪 自动使用 {potion.get('info', {}).get('name', '药水')} 恢复 {heal} HP")
                    # 检查是否用完
                    db_item = potion.get("db_item")
                    if db_item and potion["used_count"] >= db_item.quantity:
                        hp_potions.pop(0)
                
                if player_mp < player_max_mp * 0.3 and mp_potions:
                    potion = mp_potions[0]
                    heal = potion.get("info", {}).get("effect", {}).get("heal_mp", 0)
                    player_mp = min(player_max_mp, player_mp + heal)
                    potion["used_count"] = potion.get("used_count", 0) + 1
                    logs.append(f"🧪 自动使用 {potion.get('info', {}).get('name', '药水')} 恢复 {heal} MP")
                    # 检查是否用完
                    db_item = potion.get("db_item")
                    if db_item and potion["used_count"] >= db_item.quantity:
                        mp_potions.pop(0)
                
                # 减少技能CD
                for skill_name in list(skill_cooldowns.keys()):
                    skill_cooldowns[skill_name] -= 1
                    if skill_cooldowns[skill_name] <= 0:
                        del skill_cooldowns[skill_name]
                
                alive_targets = [m for m in monster_states if m["hp"] > 0]
                if not alive_targets:
                    break
                
                used_skill = False
                extra_damage = 0
                skill_name = ""
                is_aoe = False
                
                # 技能使用 - 法师90%、道士80%、战士50%
                skill_chance = {"mage": 0.9, "taoist": 0.8, "warrior": 0.5}.get(char_class, 0.5)
                if available_skills and player_mp > 0 and random.random() < skill_chance:
                    for skill in available_skills:
                        s_name = skill.get("name", "技能")
                        if skill.get("mp_cost", 0) <= player_mp and s_name not in skill_cooldowns:
                            mp_cost = skill.get("mp_cost", 0)
                            effect = skill.get("effect", {})
                            skill_level = skill.get("level", 1)
                            
                            # 治愈术只在HP低于70%时使用
                            if effect.get("heal_hp") and not effect.get("aoe"):
                                if player_hp >= player_max_hp * 0.7:
                                    continue
                            
                            if effect.get("summon"):
                                if summon_state and summon_state.get("alive"):
                                    continue
                                player_mp -= mp_cost
                                summon_state = CombatEngine.create_summon(player, skill)
                                skill_cooldowns[s_name] = skill.get("cooldown", 1)
                                logs.append(f"召唤: {summon_state['name']} (HP:{summon_state['hp']} ATK:{summon_state['attack']})")
                                skill_id = skill.get("skill_id", skill.get("id", ""))
                                if skill_id and skill_id not in skills_used:
                                    skills_used.append(skill_id)
                                used_skill = True
                                break
                            
                            player_mp -= mp_cost
                            used_skill = True
                            skill_name = s_name
                            cooldown = skill.get("cooldown", 1)
                            is_aoe = effect.get("aoe", False)
                            
                            skill_cooldowns[skill_name] = cooldown
                            
                            skill_id = skill.get("skill_id", skill.get("id", ""))
                            if skill_id and skill_id not in skills_used:
                                skills_used.append(skill_id)
                            
                            logs.append(f"使用技能: {skill_name} Lv.{skill_level} (消耗{mp_cost}MP)")
                            
                            skill_power = CombatEngine.calculate_skill_power(player, skill)
                            
                            if effect.get("magic_damage"):
                                extra_damage = int(effect["magic_damage"] * (1 + skill_power * 0.02))
                            elif effect.get("damage_multiplier"):
                                is_magic = char_class != "warrior"
                                base = CombatEngine.calculate_damage(player, alive_targets[0], is_magic, player_effects)
                                extra_damage = int(base * (effect["damage_multiplier"] - 1) * (1 + skill_level * 0.3))
                            
                            if effect.get("ignore_defense"):
                                extra_damage += int(alive_targets[0].get("defense", 0) * effect["ignore_defense"] * (1 + skill_level * 0.2))
                            
                            if effect.get("fire_damage"):
                                extra_damage += int(effect["fire_damage"] * (1 + skill_power * 0.02))
                            
                            # 施毒术 - 对目标施加持续毒伤
                            if effect.get("poison_damage") and effect.get("duration"):
                                poison_dmg, poison_rounds = CombatEngine.calculate_poison_damage(player, skill)
                                target = alive_targets[0]
                                target["poison"] = PoisonState(poison_dmg, poison_rounds)
                                logs.append(f"🧪 对{target['name']}施加毒素! 每回合{poison_dmg}点毒伤，持续{poison_rounds}回合")
                            
                            # 流星火雨 - 对目标施加持续灼烧
                            if effect.get("burn_damage") and effect.get("burn_rounds"):
                                burn_dmg = int(effect["burn_damage"] * (1 + skill_power * 0.02))
                                burn_rounds = effect["burn_rounds"]
                                if is_aoe:
                                    # AOE技能对所有目标施加灼烧
                                    for t in alive_targets[:3]:
                                        t["burn"] = PoisonState(burn_dmg, burn_rounds)
                                    logs.append(f"🔥 对所有目标施加灼烧! 每回合{burn_dmg}点火焰伤害，持续{burn_rounds}回合")
                                else:
                                    target = alive_targets[0]
                                    target["burn"] = PoisonState(burn_dmg, burn_rounds)
                                    logs.append(f"🔥 对{target['name']}施加灼烧! 每回合{burn_dmg}点火焰伤害，持续{burn_rounds}回合")
                            
                            if effect.get("heal_hp"):
                                heal = CombatEngine.calculate_heal_amount(player, skill)
                                player_hp = min(player_max_hp, player_hp + heal)
                                logs.append(f"恢复 {heal} 点生命值")
                            
                            # 隐身术
                            if effect.get("invisible"):
                                duration_min = effect.get("duration_min", 1)
                                duration_max = effect.get("duration_max", 5)
                                weight = effect.get("duration_weight_per_level", 10) * skill_level
                                # 技能等级越高，持续时间越长的概率越大
                                duration = random.choices(
                                    range(duration_min, duration_max + 1),
                                    weights=[1 + weight * (i - duration_min) for i in range(duration_min, duration_max + 1)]
                                )[0]
                                player_invisible = duration
                                logs.append(f"👻 进入隐身状态，持续{duration}回合")
                            
                            # 魔法盾
                            if effect.get("damage_reduction") and effect.get("duration_rounds"):
                                # 根据技能等级计算持续回合和减伤比例
                                # 1级：2回合15%，2级：4回合30%，3级：6回合45%
                                magic_shield_rounds = effect["duration_rounds"] * skill_level
                                magic_shield_reduction = effect["damage_reduction"] * skill_level
                                logs.append(f"🛡️ 魔法盾激活! 持续{magic_shield_rounds}回合，减伤{int(magic_shield_reduction*100)}%")
                            
                            break
                
                # 召唤物攻击
                if summon_state and summon_state.get("alive") and alive_targets:
                    target = alive_targets[0]
                    s_damage = CombatEngine.calculate_damage(summon_state, target)
                    target["hp"] -= s_damage
                    logs.append(f"{summon_state['name']}对{target['name']}造成 {s_damage} 点伤害")
                    if target["hp"] <= 0:
                        logs.append(f"💀 {target['name']} 被击败!")
                
                # 玩家攻击 - 战士和道士使用物理攻击，法师使用魔法攻击
                is_magic = char_class == "mage"
                
                # 检查双次攻击
                attack_count = 1 + EffectCalculator.check_double_attack(player_effects)
                
                for attack_num in range(attack_count):
                    alive_targets = [m for m in monster_states if m["hp"] > 0]
                    if not alive_targets:
                        break
                    
                    if attack_num > 0:
                        logs.append("⚡ 触发双次攻击!")
                    
                    if is_aoe:
                        targets = alive_targets[:3]
                        for t in targets:
                            base_damage = CombatEngine.calculate_damage(player, t, is_magic, player_effects) + extra_damage
                            result = EffectCalculator.process_attack(player, t, base_damage, equipment, [], is_magic)
                            
                            if result.is_missed:
                                logs.append(f"对{t['name']}的攻击未命中!")
                                continue
                            if result.is_dodged:
                                logs.append(f"🌀 {t['name']}闪避了攻击!")
                                continue
                            
                            t["hp"] -= result.damage
                            # 收集所有特效标签
                            effect_tags = [log for log in result.logs if not any(x in log for x in ["攻击未命中", "攻击被闪避"])]
                            log_msg = f"你对{t['name']}造成 {result.damage} 点技能伤害"
                            if effect_tags:
                                log_msg += f" [{'/'.join(effect_tags)}]"
                            logs.append(log_msg)
                            
                            if result.heal_hp > 0:
                                player_hp = min(player_max_hp, player_hp + result.heal_hp)
                            if result.heal_mp > 0:
                                player_mp = min(player_max_mp, player_mp + result.heal_mp)
                            if result.is_stunned:
                                t["stunned"] = True
                            if result.poison_damage > 0:
                                t["poison"] = PoisonState(result.poison_damage, result.poison_rounds)
                            
                            if t["hp"] <= 0:
                                logs.append(f"💀 {t['name']} 被击败!")
                        
                        # 溅射伤害
                        splash = EffectCalculator.calculate_splash(player_effects, base_damage)
                        if splash > 0:
                            for other in [m for m in monster_states if m["hp"] > 0 and m not in targets]:
                                other["hp"] -= splash
                                logs.append(f"💥 溅射对{other['name']}造成 {splash} 点伤害")
                    else:
                        target = alive_targets[0]
                        base_damage = CombatEngine.calculate_damage(player, target, is_magic, player_effects) + extra_damage
                        result = EffectCalculator.process_attack(player, target, base_damage, equipment, [], is_magic)
                        
                        if result.is_missed:
                            logs.append("攻击未命中!")
                            continue
                        if result.is_dodged:
                            logs.append(f"🌀 {target['name']}闪避了攻击!")
                            continue
                        
                        target["hp"] -= result.damage
                        if used_skill:
                            log_msg = f"你对{target['name']}造成 {result.damage} 点技能伤害"
                        else:
                            log_msg = f"你对{target['name']}造成 {result.damage} 点伤害"
                        # 收集所有特效标签
                        effect_tags = [log for log in result.logs if not any(x in log for x in ["攻击未命中", "攻击被闪避"])]
                        if effect_tags:
                            log_msg += f" [{'/'.join(effect_tags)}]"
                        logs.append(log_msg)
                        
                        if result.heal_hp > 0:
                            player_hp = min(player_max_hp, player_hp + result.heal_hp)
                        if result.heal_mp > 0:
                            player_mp = min(player_max_mp, player_mp + result.heal_mp)
                        if result.is_stunned:
                            target["stunned"] = True
                        if result.poison_damage > 0:
                            target["poison"] = PoisonState(result.poison_damage, result.poison_rounds)
                        
                        if target["hp"] <= 0:
                            logs.append(f"💀 {target['name']} 被击败!")
                        
                        # 溅射伤害
                        splash = EffectCalculator.calculate_splash(player_effects, result.damage)
                        if splash > 0:
                            for other in [m for m in monster_states if m["hp"] > 0 and m != target]:
                                other["hp"] -= splash
                                logs.append(f"💥 溅射对{other['name']}造成 {splash} 点伤害")
            
            # 怪物攻击
            for m in monster_states:
                if m["hp"] > 0:
                    # 检查怪物眩晕
                    if m.get("stunned"):
                        logs.append(f"😵 {m['name']} 被眩晕，无法行动!")
                        m["stunned"] = False
                        continue
                    
                    # 玩家隐身时怪物无法攻击玩家
                    if player_invisible > 0:
                        # 但可以攻击召唤物
                        if summon_state and summon_state.get("alive"):
                            is_magic_attack = m.get("damage_type") == "magic"
                            damage = CombatEngine.calculate_damage(m, summon_state, is_magic_attack)
                            summon_state["hp"] -= damage
                            logs.append(f"{m['name']}对{summon_state['name']}造成 {damage} 点伤害")
                            if summon_state["hp"] <= 0:
                                summon_state["alive"] = False
                                summon_died = True
                                logs.append(f"💀 {summon_state['name']} 死亡!")
                        else:
                            logs.append(f"👻 {m['name']}无法发现隐身的你!")
                        continue
                    
                    is_magic_attack = m.get("damage_type") == "magic"
                    
                    # 50%几率攻击召唤物
                    if summon_state and summon_state.get("alive") and random.random() < 0.5:
                        damage = CombatEngine.calculate_damage(m, summon_state, is_magic_attack)
                        summon_state["hp"] -= damage
                        logs.append(f"{m['name']}对{summon_state['name']}造成 {damage} 点伤害")
                        if summon_state["hp"] <= 0:
                            summon_state["alive"] = False
                            summon_died = True
                            logs.append(f"💀 {summon_state['name']} 死亡!")
                    else:
                        base_damage = CombatEngine.calculate_damage(m, player, is_magic_attack)
                        
                        # 应用玩家防御特效（格挡和减伤只取其一，不叠加）
                        defense_effects = []
                        blocked, blocked_damage = EffectCalculator.calculate_block(player_effects, base_damage)
                        reduced_damage = EffectCalculator.apply_damage_reduction(player_effects, base_damage)
                        
                        if blocked:
                            damage = blocked_damage
                            defense_effects.append("格挡")
                        elif player_effects.get("damage_reduction", 0) > 0:
                            damage = reduced_damage
                            defense_effects.append(f"减伤{int(player_effects['damage_reduction']*100)}%")
                        else:
                            damage = base_damage
                        
                        # 应用魔法盾减伤
                        if magic_shield_rounds > 0:
                            shield_reduced = int(damage * magic_shield_reduction)
                            damage = damage - shield_reduced
                            defense_effects.append(f"魔法盾减伤{int(magic_shield_reduction*100)}%")
                        
                        # 确保最低伤害为基础伤害的50%
                        damage = max(int(base_damage * 0.5), damage)
                        
                        # 反弹伤害
                        reflect_dmg = EffectCalculator.calculate_reflect(player_effects, damage)
                        if reflect_dmg > 0:
                            m["hp"] -= reflect_dmg
                            defense_effects.append(f"反弹{reflect_dmg}")
                        
                        player_hp -= damage
                        log_msg = f"{m['name']}对你造成 {damage} 点伤害"
                        if defense_effects:
                            log_msg += f" [{'/'.join(defense_effects)}]"
                        logs.append(log_msg)
                        if player_hp <= 0:
                            break
            
            # 隐身回合递减
            if player_invisible > 0:
                player_invisible -= 1
                if player_invisible == 0:
                    logs.append("👻 隐身状态结束")
            
            # 魔法盾回合递减
            if magic_shield_rounds > 0:
                magic_shield_rounds -= 1
                if magic_shield_rounds == 0:
                    logs.append("🛡️ 魔法盾效果结束")
                    magic_shield_reduction = 0.0
            
            # 状态更新
            monster_hp_info = "|".join([f"#{m['idx']}{m['name']}[{m['quality']}]:{max(0, m['hp'])}/{m['max_hp']}" for m in monster_states])
            summon_info = f"|SUMMON:{summon_state['name']}:{summon_state['hp']}/{summon_state['max_hp']}" if summon_state and summon_state.get("alive") else ""
            logs.append(f"COMBAT_STATUS|{player_hp}/{player_max_hp}|{player_mp}/{player_max_mp}|{monster_hp_info}{summon_info}")
        
        victory = all(m["hp"] <= 0 for m in monster_states)
        player_died = player_hp <= 0
        
        exp_gained = 0
        gold_gained = 0
        drops = []
        
        if victory:
            for m in monster_states:
                exp_gained += m["exp"]
                gold_gained += m["gold"]
                quality_drop_bonus = CombatEngine.QUALITY_DROP_BONUS.get(m["quality"], 1.0)

                # 处理直接掉落
                for drop in m["drops"]:
                    base_rate = CombatEngine.parse_rate(drop.get("rate", 0.1))
                    # 应用全局爆率倍数
                    final_rate = min(1.0, base_rate * quality_drop_bonus * game_config.DROP_RATE_MULTIPLIER)
                    if random.random() < final_rate:
                        quality = roll_quality(base_rate)
                        item_id = drop["item"]
                        # 获取基础物品数据并生成随机属性
                        random_attrs = None
                        if data_loader:
                            base_item = data_loader.get_item(item_id)
                            # 只对装备类型生成随机属性
                            if base_item and base_item.get("type") in ["weapon", "armor", "accessory"]:
                                rolled_item = roll_item_attributes(base_item, quality)
                                random_attrs = rolled_item.get("_random_attrs")
                        drops.append({"item_id": item_id, "quality": quality, "random_attrs": random_attrs})

                # 处理掉落组
                drop_groups = m.get("drop_groups", [])
                if drop_groups and data_loader:
                    for group_id in drop_groups:
                        group = data_loader.get_drop_group(group_id)
                        for drop in group.get("drops", []):
                            base_rate = CombatEngine.parse_rate(drop.get("rate", 0.1))
                            final_rate = min(1.0, base_rate * quality_drop_bonus * game_config.DROP_RATE_MULTIPLIER)
                            if random.random() < final_rate:
                                quality = roll_quality(base_rate)
                                item_id = drop["item"]
                                # 获取基础物品数据并生成随机属性
                                random_attrs = None
                                base_item = data_loader.get_item(item_id)
                                # 只对装备类型生成随机属性
                                if base_item and base_item.get("type") in ["weapon", "armor", "accessory"]:
                                    rolled_item = roll_item_attributes(base_item, quality)
                                    random_attrs = rolled_item.get("_random_attrs")
                                drops.append({"item_id": item_id, "quality": quality, "random_attrs": random_attrs})
            
            # 应用全局倍数
            exp_gained = int(exp_gained * game_config.EXP_MULTIPLIER)
            gold_gained = int(gold_gained * game_config.GOLD_MULTIPLIER)
            logs.append(f"🎉 胜利! 获得 {exp_gained} 经验, {gold_gained} 金币")
            for drop in drops:
                item_name = drop['item_id']
                if data_loader:
                    item_info = data_loader.get_item(drop['item_id'])
                    if item_info:
                        item_name = item_info.get('name', drop['item_id'])
                logs.append(f"💎 获得物品: {item_name}")
        else:
            logs.append(f"💀 战斗失败...")
        
        return CombatResult(
            victory=victory,
            logs=logs,
            exp_gained=exp_gained,
            gold_gained=gold_gained,
            drops=drops,
            player_died=player_died,
            skills_used=skills_used,
            passive_skills=passive_skills,
            summon_died=summon_died
        )
    
    @staticmethod
    def pvp_combat(player1: dict, player2: dict, p1_equipment: List[dict] = None, 
                   p2_equipment: List[dict] = None) -> dict:
        """PVP战斗 - 支持装备特效"""
        logs = []
        p1_hp = player1.get("max_hp", 100)
        p2_hp = player2.get("max_hp", 100)
        p1_name = player1.get("name", "玩家1")
        p2_name = player2.get("name", "玩家2")
        
        p1_effects = EffectCalculator.get_equipment_effects(p1_equipment or [])
        p2_effects = EffectCalculator.get_equipment_effects(p2_equipment or [])
        
        logs.append(f"⚔️ PVP战斗: {p1_name} vs {p2_name}")
        
        round_num = 0
        attacker, defender = (player1, p1_name, "p1", p1_effects), (player2, p2_name, "p2", p2_effects)
        hp = {"p1": p1_hp, "p2": p2_hp}
        stunned = {"p1": False, "p2": False}
        
        while hp["p1"] > 0 and hp["p2"] > 0 and round_num < 100:
            round_num += 1
            
            atk_data, atk_name, atk_key, atk_fx = attacker
            def_data, def_name, def_key, def_fx = defender
            
            if stunned[atk_key]:
                logs.append(f"😵 {atk_name} 被眩晕，无法行动!")
                stunned[atk_key] = False
            else:
                is_magic = atk_data.get("char_class") == "mage"
                base_damage = CombatEngine.calculate_damage(atk_data, def_data, is_magic, atk_fx, def_fx)
                result = EffectCalculator.process_attack(atk_data, def_data, base_damage, [], [], is_magic)
                
                if result.is_missed:
                    logs.append(f"{atk_name}的攻击未命中!")
                elif result.is_dodged:
                    logs.append(f"{def_name}闪避了攻击!")
                else:
                    # 应用防御特效
                    blocked, damage = EffectCalculator.calculate_block(def_fx, result.damage)
                    damage = EffectCalculator.apply_damage_reduction(def_fx, damage)
                    
                    hp[def_key] -= damage
                    log_msg = f"{atk_name}对{def_name}造成 {damage} 点伤害"
                    if result.is_crit:
                        log_msg += " [暴击]"
                    if blocked:
                        log_msg += " [被格挡]"
                    logs.append(log_msg + f" (剩余HP: {max(0, hp[def_key])})")
                    
                    # 反弹伤害
                    reflect_dmg = EffectCalculator.calculate_reflect(def_fx, damage)
                    if reflect_dmg > 0:
                        hp[atk_key] -= reflect_dmg
                        logs.append(f"⚡ 反弹 {reflect_dmg} 点伤害")
                    
                    # 眩晕
                    if result.is_stunned:
                        stunned[def_key] = True
                        logs.append(f"😵 {def_name} 被眩晕!")
            
            attacker, defender = defender, attacker
        
        winner = p1_name if hp["p1"] > 0 else p2_name
        winner_id = player1.get("id") if hp["p1"] > 0 else player2.get("id")
        loser_id = player2.get("id") if hp["p1"] > 0 else player1.get("id")
        
        logs.append(f"🏆 {winner} 获胜!")
        
        return {
            "winner_id": winner_id,
            "loser_id": loser_id,
            "logs": logs
        }
    
    @staticmethod
    def parse_rate(rate_str: str) -> float:
        """解析掉率字符串"""
        if isinstance(rate_str, (int, float)):
            return float(rate_str)
        if '/' in str(rate_str):
            frac = Fraction(rate_str)
            return float(frac)
        return float(rate_str)
    
    @staticmethod
    def calculate_drops_from_groups(drop_groups: List[str], monster_drops: List[dict], data_loader) -> List[dict]:
        """从掉落组计算掉落物品"""
        drops = []
        all_drops = {}

        for drop in monster_drops:
            item_id = drop.get("item")
            rate = CombatEngine.parse_rate(drop.get("rate", 0))
            if item_id in all_drops:
                all_drops[item_id] = 1 - (1 - all_drops[item_id]) * (1 - rate)
            else:
                all_drops[item_id] = rate

        for group_id in drop_groups:
            group = data_loader.get_drop_group(group_id)
            for drop in group.get("drops", []):
                item_id = drop.get("item")
                rate = CombatEngine.parse_rate(drop.get("rate", 0))
                if item_id in all_drops:
                    all_drops[item_id] = 1 - (1 - all_drops[item_id]) * (1 - rate)
                else:
                    all_drops[item_id] = rate

        for item_id, rate in all_drops.items():
            if random.random() < rate:
                quality = roll_quality(rate)
                # 获取基础物品数据并生成随机属性
                random_attrs = None
                base_item = data_loader.get_item(item_id)
                # 只对装备类型生成随机属性
                if base_item and base_item.get("type") in ["weapon", "armor", "accessory"]:
                    rolled_item = roll_item_attributes(base_item, quality)
                    random_attrs = rolled_item.get("_random_attrs")
                drops.append({
                    "item_id": item_id,
                    "quality": quality,
                    "random_attrs": random_attrs
                })

        return drops