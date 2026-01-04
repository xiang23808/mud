import random
from typing import List, Dict, Optional
from dataclasses import dataclass
from fractions import Fraction

@dataclass
class CombatResult:
    victory: bool
    logs: List[str]
    exp_gained: int
    gold_gained: int
    drops: List[dict]
    player_died: bool

class CombatEngine:
    """战斗引擎 - 一次性计算完整战斗"""
    
    @staticmethod
    def calculate_damage(attacker: dict, defender: dict) -> int:
        """计算伤害"""
        base_damage = attacker.get("attack", 10) - defender.get("defense", 0)
        base_damage = max(1, base_damage)
        
        # 暴击判定 (10%几率，1.5倍伤害)
        if random.random() < 0.1:
            base_damage = int(base_damage * 1.5)
        
        # 随机浮动 ±10%
        variance = random.uniform(0.9, 1.1)
        return max(1, int(base_damage * variance))
    
    @staticmethod
    def pve_combat(player: dict, monster: dict, skills: List[dict] = None, drop_groups: List[str] = None, data_loader=None) -> CombatResult:
        """PVE战斗"""
        logs = []
        player_hp = player.get("max_hp", 100)
        player_mp = player.get("max_mp", 50)
        monster_hp = monster.get("hp", 50)
        monster_name = monster.get("name", "怪物")
        player_name = player.get("name", "玩家")
        
        logs.append(f"⚔️ 战斗开始: {player_name} vs {monster_name}")
        logs.append(f"你的HP: {player_hp}/{player.get('max_hp')} MP: {player_mp}/{player.get('max_mp')} | {monster_name}的HP: {monster_hp}")
        
        round_num = 0
        max_rounds = 50
        
        # 可用技能列表 - 按等级要求降序排列（优先使用高级技能）
        available_skills = sorted(skills or [], key=lambda s: s.get("level_req", 1), reverse=True)
        
        # 技能CD追踪 {skill_name: remaining_cd}
        skill_cooldowns = {}
        
        while player_hp > 0 and monster_hp > 0 and round_num < max_rounds:
            round_num += 1
            logs.append(f"--- 第{round_num}回合 ---")
            
            # 减少所有技能CD
            for skill_name in list(skill_cooldowns.keys()):
                skill_cooldowns[skill_name] -= 1
                if skill_cooldowns[skill_name] <= 0:
                    del skill_cooldowns[skill_name]
            
            # 玩家攻击 - 优先使用高级技能
            used_skill = False
            extra_damage = 0
            mp_cost = 0
            skill_name = ""
            
            # 50%概率使用技能
            if available_skills and player_mp > 0 and random.random() < 0.5:
                # 按等级要求降序遍历，优先使用高级技能
                for skill in available_skills:
                    s_name = skill.get("name", "技能")
                    # 检查MP和CD
                    if skill.get("mp_cost", 0) <= player_mp and s_name not in skill_cooldowns:
                        mp_cost = skill.get("mp_cost", 0)
                        effect = skill.get("effect", {})
                        player_mp -= mp_cost
                        used_skill = True
                        skill_name = s_name
                        skill_level = skill.get("level", 1)
                        cooldown = skill.get("cooldown", 1)
                        
                        # 设置CD
                        skill_cooldowns[skill_name] = cooldown
                        
                        logs.append(f"使用技能: {skill_name} Lv.{skill_level} (消耗{mp_cost}MP, CD:{cooldown}回合)")
                        
                        # 计算技能伤害
                        if effect.get("magic_damage"):
                            extra_damage = int(effect["magic_damage"] * skill_level)
                        elif effect.get("damage_multiplier"):
                            base = CombatEngine.calculate_damage(player, monster)
                            extra_damage = int(base * (effect["damage_multiplier"] - 1) * skill_level)
                        
                        # 无视防御
                        if effect.get("ignore_defense"):
                            extra_damage += int(monster.get("defense", 0) * effect["ignore_defense"] * skill_level)
                        
                        # 火焰伤害
                        if effect.get("fire_damage"):
                            extra_damage += int(effect["fire_damage"] * skill_level)
                        
                        # 治愈术
                        if effect.get("heal_hp"):
                            heal = int(effect["heal_hp"] * skill_level)
                            player_hp = min(player.get("max_hp", 100), player_hp + heal)
                            logs.append(f"恢复 {heal} 点生命值")
                        
                        break  # 使用一个技能后退出循环
            
            damage = CombatEngine.calculate_damage(player, monster) + extra_damage
            monster_hp -= damage
            
            if used_skill:
                logs.append(f"你对{monster_name}造成 {damage} 点技能伤害")
            else:
                logs.append(f"你对{monster_name}造成 {damage} 点伤害")
            
            if monster_hp <= 0:
                break
            
            # 怪物攻击
            damage = CombatEngine.calculate_damage(monster, player)
            player_hp -= damage
            logs.append(f"{monster_name}对你造成 {damage} 点伤害")
            logs.append(f"你的HP: {player_hp} MP: {player_mp} | {monster_name}的HP: {monster_hp}")
        
        victory = monster_hp <= 0
        player_died = player_hp <= 0
        
        exp_gained = 0
        gold_gained = 0
        drops = []
        
        if victory:
            exp_gained = monster.get("exp", 10)
            gold_gained = monster.get("gold", random.randint(1, monster.get("level", 1) * 10))
            logs.append(f"🎉 胜利! 获得 {exp_gained} 经验, {gold_gained} 金币")
            
            # 掉落判定 - 使用掉落组系统
            if drop_groups and data_loader:
                drops = CombatEngine.calculate_drops_from_groups(drop_groups, monster.get("drops", []), data_loader)
            else:
                # 兼容旧的掉落方式
                for drop in monster.get("drops", []):
                    rate = CombatEngine.parse_rate(drop.get("rate", 0.1))
                    if random.random() < rate:
                        drops.append({"item_id": drop["item"], "quality": CombatEngine._roll_quality(rate)})
            
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
            player_died=player_died
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