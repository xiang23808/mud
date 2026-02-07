"""符文之语系统核心模块"""
import random
from typing import Dict, List, Optional, Tuple, Any

from backend.game.data_loader import DataLoader


def roll_sockets_for_white_equipment(slot: str) -> int:
    """
    为白色装备随机生成孔数

    Args:
        slot: 装备槽位 (weapon, armor, helmet, boots, belt)

    Returns:
        孔数量 (0 - max_sockets[slot])
    """
    socket_config = DataLoader.get_socket_config()
    if not socket_config:
        return 0

    # 检查槽位是否支持符文之语
    allowed_slots = socket_config.get("runeword_allowed_slots", [])
    if slot not in allowed_slots:
        return 0

    # 获取该槽位的孔权重
    weights = socket_config.get("socket_drop_weights", {}).get(slot)
    if not weights:
        return 0

    # 按权重随机选择孔数 (索引0=1孔, 索引1=2孔, ...)
    total_weight = sum(weights)
    roll = random.random() * total_weight
    cumulative = 0

    for i, weight in enumerate(weights):
        cumulative += weight
        if roll < cumulative:
            return i + 1  # 孔数从1开始

    return 1  # 默认1孔


def can_socket_rune(equipment_data: dict, rune_id: str) -> Tuple[bool, str]:
    """
    检查是否可以将符文镶嵌到装备中

    Args:
        equipment_data: 装备数据 (包含 quality, sockets, socketed_runes, slot, runeword_id)
        rune_id: 符文ID

    Returns:
        (是否可镶嵌, 错误信息)
    """
    # 检查是否为白色品质
    if equipment_data.get("quality") != "white":
        return False, "只有白色品质装备可以镶嵌符文"

    # 检查是否有孔
    sockets = equipment_data.get("sockets", 0)
    if sockets <= 0:
        return False, "该装备没有孔"

    # 检查是否已完成符文之语
    if equipment_data.get("runeword_id"):
        return False, "该装备已完成符文之语，无法继续镶嵌"

    # 检查已镶嵌符文数量
    socketed_runes = equipment_data.get("socketed_runes", []) or []
    if len(socketed_runes) >= sockets:
        return False, "没有空闲的孔位"

    # 检查符文是否存在
    rune_data = DataLoader.get_rune(rune_id)
    if not rune_data:
        return False, "无效的符文"

    # 检查符文是否支持该装备槽位
    slot = equipment_data.get("slot")
    socketed_effects = rune_data.get("socketed_effects", {})
    if slot not in socketed_effects:
        return False, f"该符文不支持{slot}槽位"

    return True, ""


def socket_rune(equipment_data: dict, rune_id: str) -> Tuple[bool, str, Optional[str]]:
    """
    执行符文镶嵌操作

    Args:
        equipment_data: 装备数据 (会被修改)
        rune_id: 符文ID

    Returns:
        (是否成功, 消息, 完成的符文之语ID或None)
    """
    can_socket, error = can_socket_rune(equipment_data, rune_id)
    if not can_socket:
        return False, error, None

    # 添加符文到已镶嵌列表
    socketed_runes = equipment_data.get("socketed_runes", []) or []
    socketed_runes = list(socketed_runes)  # 确保是可变列表
    socketed_runes.append(rune_id)
    equipment_data["socketed_runes"] = socketed_runes

    # 检查是否完成符文之语
    runeword_id = check_runeword_completion(equipment_data)
    if runeword_id:
        equipment_data["runeword_id"] = runeword_id
        runeword = DataLoader.get_runeword(runeword_id)
        runeword_name = runeword.get("name", runeword_id) if runeword else runeword_id
        return True, f"符文之语【{runeword_name}】完成！", runeword_id

    rune_data = DataLoader.get_rune(rune_id)
    rune_name = rune_data.get("name", rune_id) if rune_data else rune_id
    return True, f"成功镶嵌{rune_name}", None


def check_runeword_completion(equipment_data: dict) -> Optional[str]:
    """
    检查装备是否完成符文之语

    Args:
        equipment_data: 装备数据

    Returns:
        完成的符文之语ID, 或None
    """
    socketed_runes = equipment_data.get("socketed_runes", []) or []
    if not socketed_runes:
        return None

    slot = equipment_data.get("slot")
    sockets = equipment_data.get("sockets", 0)

    # 获取所有符文之语配方
    all_runewords = DataLoader.get_all_runewords()
    if not all_runewords:
        return None

    for runeword_id, runeword in all_runewords.items():
        # 检查槽位是否匹配
        allowed_slots = runeword.get("allowed_slots", [])
        if slot not in allowed_slots:
            continue

        # 检查符文序列是否完全匹配
        required_runes = runeword.get("runes", [])
        if len(required_runes) != len(socketed_runes):
            continue

        # 检查符文顺序是否正确
        if required_runes == socketed_runes:
            return runeword_id

    return None


def calculate_socketed_effects(equipment_data: dict) -> dict:
    """
    计算已镶嵌符文的属性加成

    Args:
        equipment_data: 装备数据

    Returns:
        属性加成字典 {attack_min, attack_max, defense_min, ..., effects: {...}}
    """
    socketed_runes = equipment_data.get("socketed_runes", []) or []
    if not socketed_runes:
        return {}

    slot = equipment_data.get("slot")

    # 如果已完成符文之语，返回符文之语效果而非单独符文效果
    runeword_id = equipment_data.get("runeword_id")
    if runeword_id:
        return get_runeword_effects(runeword_id, slot)

    # 累加各符文的属性加成
    result = {"effects": {}}

    for rune_id in socketed_runes:
        rune_data = DataLoader.get_rune(rune_id)
        if not rune_data:
            continue

        socketed_effects = rune_data.get("socketed_effects", {})
        slot_effects = socketed_effects.get(slot, {})

        for key, value in slot_effects.items():
            if key == "effects":
                # 累加特效
                for eff_key, eff_val in value.items():
                    result["effects"][eff_key] = result["effects"].get(eff_key, 0) + eff_val
            else:
                # 累加属性
                result[key] = result.get(key, 0) + value

    return result


def get_runeword_effects(runeword_id: str, slot: str) -> dict:
    """
    获取符文之语的完整属性

    Args:
        runeword_id: 符文之语ID
        slot: 装备槽位

    Returns:
        属性加成字典
    """
    runeword = DataLoader.get_runeword(runeword_id)
    if not runeword:
        return {}

    effects = runeword.get("effects", {})
    if not effects:
        return {}

    # 复制效果以避免修改原始数据
    result = {}
    for key, value in effects.items():
        if key == "effects":
            result["effects"] = dict(value)
        else:
            result[key] = value

    # 确保有 effects 键
    if "effects" not in result:
        result["effects"] = {}

    return result


def get_rune_display_name(rune_id: str) -> str:
    """获取符文显示名称"""
    rune = DataLoader.get_rune(rune_id)
    if rune:
        return rune.get("name", rune_id)
    return rune_id


def get_socket_display(equipment_data: dict) -> str:
    """
    获取孔位显示字符串

    Args:
        equipment_data: 装备数据

    Returns:
        如 "◆◆◇◇" (已填充2孔，空2孔)
    """
    sockets = equipment_data.get("sockets", 0)
    if sockets <= 0:
        return ""

    socketed_runes = equipment_data.get("socketed_runes", []) or []
    filled = len(socketed_runes)
    empty = sockets - filled

    return "◆" * filled + "◇" * empty


def get_available_runewords_for_slot(slot: str, sockets: int) -> List[dict]:
    """
    获取指定槽位和孔数可用的符文之语列表

    Args:
        slot: 装备槽位
        sockets: 孔数

    Returns:
        符文之语列表
    """
    all_runewords = DataLoader.get_all_runewords()
    if not all_runewords:
        return []

    result = []
    for runeword_id, runeword in all_runewords.items():
        allowed_slots = runeword.get("allowed_slots", [])
        if slot not in allowed_slots:
            continue

        required_runes = runeword.get("runes", [])
        if len(required_runes) > sockets:
            continue

        result.append({
            "id": runeword_id,
            "name": runeword.get("name", runeword_id),
            "name_en": runeword.get("name_en", ""),
            "level_req": runeword.get("level_req", 1),
            "runes": required_runes,
            "rune_names": [get_rune_display_name(r) for r in required_runes],
            "description": runeword.get("description", "")
        })

    # 按等级需求排序
    result.sort(key=lambda x: x["level_req"])
    return result


def roll_rune_drop(monster_level: int, is_boss: bool = False) -> Optional[str]:
    """
    掉落符文

    Args:
        monster_level: 怪物等级
        is_boss: 是否为Boss

    Returns:
        符文ID, 或None表示未掉落
    """
    socket_config = DataLoader.get_socket_config()
    base_chance = socket_config.get("rune_drop_base_chance", 0.02) if socket_config else 0.02
    boss_mult = socket_config.get("rune_drop_boss_multiplier", 3) if socket_config else 3

    # Boss有更高掉落率
    drop_chance = base_chance * (boss_mult if is_boss else 1)

    if random.random() > drop_chance:
        return None

    # 获取所有符文
    all_runes = DataLoader.get_all_runes()
    if not all_runes:
        return None

    # 根据怪物等级和符文等级需求过滤
    available_runes = []
    weights = []

    for rune_id, rune in all_runes.items():
        level_req = rune.get("level_req", 1)
        # 怪物等级需要至少达到符文等级需求的一半
        if monster_level >= level_req // 2:
            # 高级符文需要高级怪物
            if level_req <= monster_level + 10:
                available_runes.append(rune_id)
                # 使用drop_weight作为权重
                weights.append(rune.get("drop_weight", 1))

    if not available_runes:
        return None

    # 加权随机选择
    total = sum(weights)
    roll = random.random() * total
    cumulative = 0

    for rune_id, weight in zip(available_runes, weights):
        cumulative += weight
        if roll < cumulative:
            return rune_id

    return available_runes[0]


def apply_runeword_to_equipment_info(equipment_info: dict, equipment_data: dict) -> dict:
    """
    将符文/符文之语效果应用到装备信息中

    Args:
        equipment_info: 基础装备信息 (从物品模板获取)
        equipment_data: 装备数据 (包含 socketed_runes, runeword_id 等)

    Returns:
        增强后的装备信息
    """
    result = dict(equipment_info)

    sockets = equipment_data.get("sockets", 0)
    if sockets <= 0:
        return result

    # 添加孔位信息
    result["sockets"] = sockets
    result["socketed_runes"] = equipment_data.get("socketed_runes", []) or []
    result["runeword_id"] = equipment_data.get("runeword_id")
    result["socket_display"] = get_socket_display(equipment_data)

    # 计算符文加成
    socketed_effects = calculate_socketed_effects(equipment_data)

    if socketed_effects:
        # 累加属性
        for key, value in socketed_effects.items():
            if key == "effects":
                # 合并特效
                if "effects" not in result:
                    result["effects"] = {}
                for eff_key, eff_val in value.items():
                    result["effects"][eff_key] = result["effects"].get(eff_key, 0) + eff_val
            else:
                result[key] = result.get(key, 0) + value

    # 如果完成符文之语，添加符文之语信息
    runeword_id = equipment_data.get("runeword_id")
    if runeword_id:
        runeword = DataLoader.get_runeword(runeword_id)
        if runeword:
            result["runeword_name"] = runeword.get("name", runeword_id)
            result["runeword_name_en"] = runeword.get("name_en", "")
            result["runeword_description"] = runeword.get("description", "")

    return result
