import random
from typing import List, Dict, Optional
from dataclasses import dataclass

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
    def pve_combat(player: dict, monster: dict, skills: List[dict] = None) -> CombatResult:
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
        
        # 可用技能列表
        available_skills = skills or []
        
        while player_hp > 0 and monster_hp > 0 and round_num < max_rounds:
            round_num += 1
            logs.append(f"--- 第{round_num}回合 ---")
            
            # 玩家攻击 - 随机选择是否使用技能
            used_skill = False
            skill_multiplier = 1.0
            mp_cost = 0
            
            # 30%概率使用技能
            if available_skills and player_mp > 0 and random.random() < 0.3:
                usable_skills = [s for s in available_skills if s.get("mp_cost", 0) <= player_mp]
                if usable_skills:
                    skill = random.choice(usable_skills)
                    mp_cost = skill.get("mp_cost", 0)
                    skill_multiplier = skill.get("effect", {}).get("damage_multiplier", 1.0)
                    player_mp -= mp_cost
                    used_skill = True
                    logs.append(f"使用技能: {skill['name']} (消耗{mp_cost}MP)")
            
            damage = int(CombatEngine.calculate_damage(player, monster) * skill_multiplier)
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
            
            # 掉落判定
            for drop in monster.get("drops", []):
                if random.random() < drop.get("rate", 0.1):
                    drops.append({"item_id": drop["item"], "quality": CombatEngine._roll_quality()})
                    logs.append(f"💎 获得物品: {drop['item']}")
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
    def _roll_quality() -> str:
        """随机品质"""
        roll = random.random()
        if roll < 0.6:
            return "white"
        elif roll < 0.85:
            return "green"
        elif roll < 0.95:
            return "blue"
        elif roll < 0.99:
            return "purple"
        else:
            return "red"