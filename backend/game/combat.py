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
    
    @staticmethod
    def pve_combat(player: dict, monsters: list, skills: List[dict] = None, drop_groups: List[str] = None, data_loader=None, inventory: List[dict] = None) -> CombatResult:
        """PVE战斗 - 支持多怪物"""
        # 兼容单怪物传入
        if isinstance(monsters, dict):
            monsters = [monsters]
        
        logs = []
        player_hp = player.get("max_hp", 100)
        player_mp = player.get("max_mp", 50)
        player_max_hp = player.get("max_hp", 100)
        player_name = player.get("name", "玩家")
        
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
        
        monster_names = ", ".join([f"{m['name']}({m['quality']})" for m in monster_states])
        logs.append(f"⚔️ 战斗开始: {player_name} vs {monster_names}")
        logs.append(f"你的HP: {player_hp}/{player_max_hp} MP: {player_mp}/{player.get('max_mp')} | 怪物数量: {len(monster_states)}")
        
        round_num = 0
        max_rounds = 100
        skills_used = []
        passive_skills = []
        
        # 分离主动和被动技能
        active_skills = []
        for skill in (skills or []):
            if skill.get("type") == "passive":
                skill_id = skill.get("skill_id", skill.get("id", ""))
                if skill_id:
                    passive_skills.append(skill_id)
            else:
                active_skills.append(skill)
        
        available_skills = sorted(active_skills, key=lambda s: s.get("level_req", 1), reverse=True)
        skill_cooldowns = {}
        
        # 获取背包中的恢复物品
        hp_potions = []
        if inventory:
            for item in inventory:
                info = item.get("info", {})
                if info.get("type") == "consumable" and info.get("effect", {}).get("heal_hp"):
                    hp_potions.append(item)
            hp_potions.sort(key=lambda x: x.get("info", {}).get("effect", {}).get("heal_hp", 0))
        
        while player_hp > 0 and any(m["hp"] > 0 for m in monster_states) and round_num < max_rounds:
            round_num += 1
            logs.append(f"--- 第{round_num}回合 ---")
            
            # 自动使用恢复物品（HP低于30%时）
            if player_hp < player_max_hp * 0.3 and hp_potions:
                potion = hp_potions.pop(0)
                heal = potion.get("info", {}).get("effect", {}).get("heal_hp", 0)
                player_hp = min(player_max_hp, player_hp + heal)
                logs.append(f"🧪 自动使用 {potion.get('info', {}).get('name', '药水')} 恢复 {heal} HP")
            
            # 减少所有技能CD
            for skill_name in list(skill_cooldowns.keys()):
                skill_cooldowns[skill_name] -= 1
                if skill_cooldowns[skill_name] <= 0:
                    del skill_cooldowns[skill_name]
            
            # 玩家攻击 - 选择第一个存活的怪物
            target = next((m for m in monster_states if m["hp"] > 0), None)
            if not target:
                break
            
            used_skill = False
            extra_damage = 0
            skill_name = ""
            
            if available_skills and player_mp > 0 and random.random() < 0.5:
                for skill in available_skills:
                    s_name = skill.get("name", "技能")
                    if skill.get("mp_cost", 0) <= player_mp and s_name not in skill_cooldowns:
                        mp_cost = skill.get("mp_cost", 0)
                        effect = skill.get("effect", {})
                        player_mp -= mp_cost
                        used_skill = True
                        skill_name = s_name
                        skill_level = skill.get("level", 1)
                        cooldown = skill.get("cooldown", 1)
                        
                        skill_cooldowns[skill_name] = cooldown
                        
                        skill_id = skill.get("skill_id", skill.get("id", ""))
                        if skill_id and skill_id not in skills_used:
                            skills_used.append(skill_id)
                        
                        logs.append(f"使用技能: {skill_name} Lv.{skill_level} (消耗{mp_cost}MP)")
                        
                        # 技能效果随等级增强
                        level_mult = 1 + (skill_level - 1) * 0.5  # 每级+50%效果
                        
                        if effect.get("magic_damage"):
                            extra_damage = int(effect["magic_damage"] * level_mult)
                        elif effect.get("damage_multiplier"):
                            base = CombatEngine.calculate_damage(player, target)
                            extra_damage = int(base * (effect["damage_multiplier"] * level_mult - 1))
                        
                        if effect.get("ignore_defense"):
                            extra_damage += int(target.get("defense", 0) * effect["ignore_defense"] * level_mult)
                        
                        if effect.get("fire_damage"):
                            extra_damage += int(effect["fire_damage"] * level_mult)
                        
                        if effect.get("heal_hp"):
                            heal = int(effect["heal_hp"] * level_mult)
                            player_hp = min(player_max_hp, player_hp + heal)
                            logs.append(f"恢复 {heal} 点生命值")
                        
                        break
            
            damage = CombatEngine.calculate_damage(player, target) + extra_damage
            target["hp"] -= damage
            
            if used_skill:
                logs.append(f"你对{target['name']}造成 {damage} 点技能伤害")
            else:
                logs.append(f"你对{target['name']}造成 {damage} 点伤害")
            
            if target["hp"] <= 0:
                logs.append(f"💀 {target['name']} 被击败!")
            
            # 所有存活怪物攻击玩家
            for m in monster_states:
                if m["hp"] > 0:
                    damage = CombatEngine.calculate_damage(m, player)
                    player_hp -= damage
                    logs.append(f"{m['name']}对你造成 {damage} 点伤害")
                    if player_hp <= 0:
                        break
            
            alive_monsters = [m for m in monster_states if m["hp"] > 0]
            monster_hp_info = ", ".join([f"{m['name']}:{m['hp']}" for m in alive_monsters]) if alive_monsters else "全部击败"
            logs.append(f"你的HP: {player_hp} MP: {player_mp} | {monster_hp_info}")
        
        victory = all(m["hp"] <= 0 for m in monster_states)
        player_died = player_hp <= 0
        
        exp_gained = 0
        gold_gained = 0
        drops = []
        
        if victory:
            for m in monster_states:
                exp_gained += m["exp"]
                gold_gained += m["gold"]
                for drop in m["drops"]:
                    rate = CombatEngine.parse_rate(drop.get("rate", 0.1))
                    if random.random() < rate:
                        drops.append({"item_id": drop["item"], "quality": CombatEngine._roll_quality(rate)})
            
            logs.append(f"🎉 胜利! 获得 {exp_gained} 经验, {gold_gained} 金币")
            for drop in drops:
                logs.append(f"💎 获得物品: {drop['item_id']}")
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
            passive_skills=passive_skills
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