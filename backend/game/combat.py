import random
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from fractions import Fraction

@dataclass
class CombatResult:
    victory: bool
    logs: List[str]
    exp_gained: int
    gold_gained: int
    drops: List[dict]
    player_died: bool
    skills_used: List[str]  # 记录使用的技能ID
    passive_skills: List[str] = field(default_factory=list)  # 被动技能ID列表
    summon_died: bool = False  # 召唤物是否死亡

class CombatEngine:
    """战斗引擎 - 一次性计算完整战斗"""
    
    @staticmethod
    def calculate_damage(attacker: dict, defender: dict, is_magic: bool = False) -> int:
        """计算伤害（支持min-max范围和减伤百分比）"""
        # 获取攻击值（支持min-max范围）
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
        
        # 随机取攻击和防御值
        attack = random.randint(int(atk_min), max(int(atk_min), int(atk_max)))
        defense = random.randint(int(def_min), max(int(def_min), int(def_max)))
        
        # 使用减伤百分比公式，避免不破防
        # 减伤率 = 防御 / (防御 + 100)，最高减伤80%
        reduction = min(0.8, defense / (defense + 100))
        base_damage = int(attack * (1 - reduction))
        base_damage = max(1, base_damage)
        
        # 暴击判定 (10%几率，1.5倍伤害)
        if random.random() < 0.1:
            base_damage = int(base_damage * 1.5)
        
        # 随机浮动 ±10%
        variance = random.uniform(0.9, 1.1)
        return max(1, int(base_damage * variance))
    
    # 品质爆率加成
    QUALITY_DROP_BONUS = {"white": 1.0, "green": 1.5, "blue": 2.0, "purple": 3.0, "orange": 5.0}
    
    @staticmethod
    def calculate_skill_power(player: dict, skill: dict) -> int:
        """根据职业计算技能威力：战士用攻击，法师道士用魔法"""
        char_class = player.get("char_class", "warrior")
        skill_level = skill.get("level", 1)
        level_mult = 1 + (skill_level - 1) * 0.5  # 每级+50%
        
        if char_class == "warrior":
            base = (player.get("attack_min", 10) + player.get("attack_max", 10)) // 2
        else:  # mage, taoist
            base = (player.get("magic_min", 10) + player.get("magic_max", 10)) // 2
        
        return int(base * level_mult)
    
    @staticmethod
    def calculate_heal_amount(player: dict, skill: dict) -> int:
        """计算治愈量：按魔法和等级计算"""
        skill_level = skill.get("level", 1)
        magic = (player.get("magic_min", 0) + player.get("magic_max", 0)) // 2
        base_heal = skill.get("effect", {}).get("heal_hp", 50)
        # 治愈量 = 基础值 + 魔法*0.5 + 等级加成
        return int((base_heal + magic * 0.5) * (1 + (skill_level - 1) * 0.3))
    
    @staticmethod
    def create_summon(player: dict, skill: dict) -> dict:
        """创建召唤物：属性根据魔法和等级计算"""
        skill_level = skill.get("level", 1)
        magic = (player.get("magic_min", 0) + player.get("magic_max", 0)) // 2
        summon_type = skill.get("effect", {}).get("summon", "skeleton")
        
        # 基础属性
        base_hp = 100 if summon_type == "skeleton" else 200
        base_atk = 15 if summon_type == "skeleton" else 30
        base_def = 5 if summon_type == "skeleton" else 15
        
        # 根据魔法和等级计算
        mult = 1 + magic * 0.02 + (skill_level - 1) * 0.3
        return {
            "name": "骷髅战士" if summon_type == "skeleton" else "神兽",
            "type": summon_type,
            "hp": int(base_hp * mult),
            "max_hp": int(base_hp * mult),
            "attack": int(base_atk * mult),
            "defense": int(base_def * mult),
            "alive": True
        }
    
    @staticmethod
    def pve_combat(player: dict, monsters: list, skills: List[dict] = None, drop_groups: List[str] = None, data_loader=None, inventory: List[dict] = None, summon: dict = None, disabled_skills: List[str] = None) -> CombatResult:
        """PVE战斗 - 支持多怪物、召唤物、技能开关"""
        # 兼容单怪物传入
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
        
        # 初始化怪物状态，应用品质加成
        monster_states = []
        for m in monsters:
            quality = m.get("quality", "white")
            quality_bonus = {"white": 1.0, "green": 1.2, "blue": 1.5, "purple": 2.0, "orange": 3.0}.get(quality, 1.0)
            monster_states.append({
                "name": m.get("name", "怪物"),
                "hp": int(m.get("hp", 50) * quality_bonus),
                "max_hp": int(m.get("hp", 50) * quality_bonus),
                "attack": int(m.get("attack", 10) * quality_bonus),
                "defense": int(m.get("defense", 0) * quality_bonus),
                "exp": int(m.get("exp", 10) * quality_bonus),
                "gold": int(m.get("gold", 5) * quality_bonus),
                "drops": m.get("drops", []),
                "quality": quality,
                "is_boss": m.get("is_boss", False)
            })
        
        # 给每个怪物加上索引
        for idx, m in enumerate(monster_states):
            m['idx'] = idx
        
        # 构建怪物信息（带品质颜色标记）
        monster_names = ", ".join([f"{m['name']}[{m['quality']}]" for m in monster_states])
        logs.append(f"⚔️ 战斗开始: {player_name} vs {monster_names}")
        # 第二行：玩家HP/MP和所有怪物HP（用于前端解析，带索引）
        monster_hp_list = "|".join([f"#{m['idx']}{m['name']}[{m['quality']}]:{m['hp']}/{m['max_hp']}" for m in monster_states])
        logs.append(f"COMBAT_INIT|{player_hp}/{player_max_hp}|{player_mp}/{player_max_mp}|{monster_hp_list}")
        
        round_num = 0
        max_rounds = 100
        skills_used = []
        passive_skills = []
        
        # 分离主动和被动技能，过滤禁用的技能
        active_skills = []
        for skill in (skills or []):
            skill_id = skill.get("skill_id", skill.get("id", ""))
            if skill_id in disabled_skills:
                continue  # 跳过禁用的技能
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
        
        # 获取背包中的恢复物品
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
            
            # 自动使用HP恢复物品（HP低于30%时）
            if player_hp < player_max_hp * 0.3 and hp_potions:
                potion = hp_potions.pop(0)
                heal = potion.get("info", {}).get("effect", {}).get("heal_hp", 0)
                player_hp = min(player_max_hp, player_hp + heal)
                potion["used"] = True
                logs.append(f"🧪 自动使用 {potion.get('info', {}).get('name', '药水')} 恢复 {heal} HP")
            
            # 自动使用MP恢复物品（MP低于30%时）
            if player_mp < player_max_mp * 0.3 and mp_potions:
                potion = mp_potions.pop(0)
                heal = potion.get("info", {}).get("effect", {}).get("heal_mp", 0)
                player_mp = min(player_max_mp, player_mp + heal)
                potion["used"] = True
                logs.append(f"🧪 自动使用 {potion.get('info', {}).get('name', '药水')} 恢复 {heal} MP")
            
            # 减少所有技能CD
            for skill_name in list(skill_cooldowns.keys()):
                skill_cooldowns[skill_name] -= 1
                if skill_cooldowns[skill_name] <= 0:
                    del skill_cooldowns[skill_name]
            
            # 玩家攻击 - 选择存活的怪物
            alive_targets = [m for m in monster_states if m["hp"] > 0]
            if not alive_targets:
                break
            
            used_skill = False
            extra_damage = 0
            skill_name = ""
            is_aoe = False
            
            if available_skills and player_mp > 0 and random.random() < 0.5:
                for skill in available_skills:
                    s_name = skill.get("name", "技能")
                    if skill.get("mp_cost", 0) <= player_mp and s_name not in skill_cooldowns:
                        mp_cost = skill.get("mp_cost", 0)
                        effect = skill.get("effect", {})
                        skill_level = skill.get("level", 1)
                        
                        # 召唤技能特殊处理
                        if effect.get("summon"):
                            if summon_state and summon_state.get("alive"):
                                continue  # 已有召唤物，跳过
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
                        
                        # 根据职业计算技能威力
                        skill_power = CombatEngine.calculate_skill_power(player, skill)
                        
                        if effect.get("magic_damage"):
                            extra_damage = int(effect["magic_damage"] * (1 + skill_power * 0.02))
                        elif effect.get("damage_multiplier"):
                            is_magic = char_class != "warrior"
                            base = CombatEngine.calculate_damage(player, alive_targets[0], is_magic)
                            extra_damage = int(base * (effect["damage_multiplier"] - 1) * (1 + skill_level * 0.3))
                        
                        if effect.get("ignore_defense"):
                            extra_damage += int(alive_targets[0].get("defense", 0) * effect["ignore_defense"] * (1 + skill_level * 0.2))
                        
                        if effect.get("fire_damage"):
                            extra_damage += int(effect["fire_damage"] * (1 + skill_power * 0.02))
                        
                        # 治愈技能按魔法计算
                        if effect.get("heal_hp"):
                            heal = CombatEngine.calculate_heal_amount(player, skill)
                            player_hp = min(player_max_hp, player_hp + heal)
                            logs.append(f"恢复 {heal} 点生命值")
                        
                        break
            
            # 召唤物攻击
            if summon_state and summon_state.get("alive") and alive_targets:
                target = alive_targets[0]
                s_damage = CombatEngine.calculate_damage(summon_state, target)
                target["hp"] -= s_damage
                logs.append(f"{summon_state['name']}对{target['name']}造成 {s_damage} 点伤害")
                if target["hp"] <= 0:
                    logs.append(f"💀 {target['name']} 被击败!")
            
            # AOE技能攻击多个目标（最多3个）
            is_magic = char_class != "warrior"
            if is_aoe:
                targets = alive_targets[:3]
                for t in targets:
                    damage = CombatEngine.calculate_damage(player, t, is_magic) + extra_damage
                    t["hp"] -= damage
                    logs.append(f"你对{t['name']}造成 {damage} 点技能伤害")
                    if t["hp"] <= 0:
                        logs.append(f"💀 {t['name']} 被击败!")
            else:
                target = alive_targets[0]
                damage = CombatEngine.calculate_damage(player, target, is_magic) + extra_damage
                target["hp"] -= damage
                if used_skill:
                    logs.append(f"你对{target['name']}造成 {damage} 点技能伤害")
                else:
                    logs.append(f"你对{target['name']}造成 {damage} 点伤害")
                if target["hp"] <= 0:
                    logs.append(f"💀 {target['name']} 被击败!")
            
            # 所有存活怪物攻击（优先攻击召唤物）
            for m in monster_states:
                if m["hp"] > 0:
                    # 50%几率攻击召唤物
                    if summon_state and summon_state.get("alive") and random.random() < 0.5:
                        damage = CombatEngine.calculate_damage(m, summon_state)
                        summon_state["hp"] -= damage
                        logs.append(f"{m['name']}对{summon_state['name']}造成 {damage} 点伤害")
                        if summon_state["hp"] <= 0:
                            summon_state["alive"] = False
                            summon_died = True
                            logs.append(f"💀 {summon_state['name']} 死亡!")
                    else:
                        damage = CombatEngine.calculate_damage(m, player)
                        player_hp -= damage
                        logs.append(f"{m['name']}对你造成 {damage} 点伤害")
                        if player_hp <= 0:
                            break
            
            # 发送所有怪物状态（包括死亡的，用于前端正确显示）
            monster_hp_info = "|".join([f"#{m['idx']}{m['name']}[{m['quality']}]:{max(0, m['hp'])}/{m['max_hp']}" for m in monster_states])
            logs.append(f"COMBAT_STATUS|{player_hp}/{player_max_hp}|{player_mp}/{player_max_mp}|{monster_hp_info}")
        
        victory = all(m["hp"] <= 0 for m in monster_states)
        player_died = player_hp <= 0
        
        exp_gained = 0
        gold_gained = 0
        drops = []
        
        if victory:
            for m in monster_states:
                exp_gained += m["exp"]
                gold_gained += m["gold"]
                # 根据怪物品质计算爆率加成
                quality_drop_bonus = CombatEngine.QUALITY_DROP_BONUS.get(m["quality"], 1.0)
                # 每个物品单独计算掉落
                for drop in m["drops"]:
                    base_rate = CombatEngine.parse_rate(drop.get("rate", 0.1))
                    final_rate = min(1.0, base_rate * quality_drop_bonus)  # 最高100%
                    if random.random() < final_rate:
                        drops.append({"item_id": drop["item"], "quality": CombatEngine._roll_quality(base_rate)})
            
            logs.append(f"🎉 胜利! 获得 {exp_gained} 经验, {gold_gained} 金币")
            # 获取物品中文名称
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
    def pvp_combat(player1: dict, player2: dict) -> dict:
        """PVP战斗"""
        logs = []
        p1_hp = player1.get("max_hp", 100)
        p2_hp = player2.get("max_hp", 100)
        p1_name = player1.get("name", "玩家1")
        p2_name = player2.get("name", "玩家2")
        
        logs.append(f"⚔️ PVP战斗: {p1_name} vs {p2_name}")
        
        round_num = 0
        attacker, defender = (player1, p1_name, "p1"), (player2, p2_name, "p2")
        hp = {"p1": p1_hp, "p2": p2_hp}
        
        while hp["p1"] > 0 and hp["p2"] > 0 and round_num < 100:
            round_num += 1
            
            # 交替攻击
            atk_data, atk_name, atk_key = attacker
            def_data, def_name, def_key = defender
            
            damage = CombatEngine.calculate_damage(atk_data, def_data)
            hp[def_key] -= damage
            logs.append(f"{atk_name}对{def_name}造成 {damage} 点伤害 (剩余HP: {max(0, hp[def_key])})")
            
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
    def _roll_quality(base_rate: float = 1.0) -> str:
        """随机品质 - 掉率越低品质越高概率"""
        roll = random.random()
        # 基础掉率越低，高品质概率越高
        quality_boost = min(0.3, (1 - base_rate) * 0.5)
        
        if roll < 0.5 - quality_boost:
            return "white"
        elif roll < 0.75 - quality_boost * 0.5:
            return "green"
        elif roll < 0.9:
            return "blue"
        elif roll < 0.97:
            return "purple"
        else:
            return "red"
    
    @staticmethod
    def parse_rate(rate_str: str) -> float:
        """解析掉率字符串，支持分数格式如 '1/100'"""
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
        all_drops = {}  # 合并重复物品的掉率
        
        # 收集怪物自身的掉落
        for drop in monster_drops:
            item_id = drop.get("item")
            rate = CombatEngine.parse_rate(drop.get("rate", 0))
            if item_id in all_drops:
                # 合并掉率：1 - (1-r1)*(1-r2)
                all_drops[item_id] = 1 - (1 - all_drops[item_id]) * (1 - rate)
            else:
                all_drops[item_id] = rate
        
        # 收集掉落组的掉落
        for group_id in drop_groups:
            group = data_loader.get_drop_group(group_id)
            for drop in group.get("drops", []):
                item_id = drop.get("item")
                rate = CombatEngine.parse_rate(drop.get("rate", 0))
                if item_id in all_drops:
                    all_drops[item_id] = 1 - (1 - all_drops[item_id]) * (1 - rate)
                else:
                    all_drops[item_id] = rate
        
        # 计算掉落
        for item_id, rate in all_drops.items():
            if random.random() < rate:
                drops.append({
                    "item_id": item_id,
                    "quality": CombatEngine._roll_quality(rate)
                })
        
        return drops