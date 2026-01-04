from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, Integer, String, DateTime, select
from datetime import datetime
from backend.database import get_db, Base
from backend.models import Character
from backend.auth import decode_token

router = APIRouter(prefix="/api/recharge", tags=["recharge"])

class RechargeLog(Base):
    __tablename__ = "recharge_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    character_id = Column(Integer, nullable=False)
    amount = Column(Integer, nullable=False)  # 充值金额(分)
    yuanbao = Column(Integer, nullable=False)  # 获得元宝
    created_at = Column(DateTime, default=datetime.utcnow)


# 充值比例: 1元 = 10元宝
YUANBAO_RATE = 10

# VIP等级配置
VIP_LEVELS = {
    0: {"name": "普通玩家", "exp_bonus": 1.0, "drop_bonus": 1.0, "total_recharge": 0},
    1: {"name": "VIP1", "exp_bonus": 1.1, "drop_bonus": 1.05, "total_recharge": 100},
    2: {"name": "VIP2", "exp_bonus": 1.2, "drop_bonus": 1.1, "total_recharge": 500},
    3: {"name": "VIP3", "exp_bonus": 1.3, "drop_bonus": 1.15, "total_recharge": 2000},
    4: {"name": "VIP4", "exp_bonus": 1.5, "drop_bonus": 1.2, "total_recharge": 5000},
    5: {"name": "VIP5", "exp_bonus": 2.0, "drop_bonus": 1.3, "total_recharge": 10000},
}


@router.post("/create")
async def create_recharge(
    char_id: int,
    amount: int,  # 金额(元)
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """创建充值订单（模拟）"""
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(401, "无效token")
    
    char = await db.get(Character, char_id)
    if not char or char.user_id != user_id:
        raise HTTPException(400, "角色不存在")
    
    if amount < 1:
        raise HTTPException(400, "充值金额最少1元")
    
    yuanbao = amount * YUANBAO_RATE
    
    # 记录充值
    log = RechargeLog(
        user_id=user_id,
        character_id=char_id,
        amount=amount * 100,  # 转为分
        yuanbao=yuanbao
    )
    db.add(log)
    
    # 增加元宝
    char.yuanbao += yuanbao
    
    await db.commit()
    
    return {
        "success": True,
        "yuanbao_added": yuanbao,
        "total_yuanbao": char.yuanbao
    }


@router.get("/vip")
async def get_vip_info(
    char_id: int,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """获取VIP信息"""
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(401, "无效token")
    
    char = await db.get(Character, char_id)
    if not char:
        raise HTTPException(400, "角色不存在")
    
    # 计算总充值
    result = await db.execute(
        select(RechargeLog).where(RechargeLog.character_id == char_id)
    )
    logs = result.scalars().all()
    total_recharge = sum(log.amount for log in logs) // 100  # 转为元
    
    # 计算VIP等级
    vip_level = 0
    for level, config in VIP_LEVELS.items():
        if total_recharge >= config["total_recharge"]:
            vip_level = level
    
    vip_config = VIP_LEVELS[vip_level]
    next_level = VIP_LEVELS.get(vip_level + 1)
    
    return {
        "vip_level": vip_level,
        "vip_name": vip_config["name"],
        "exp_bonus": vip_config["exp_bonus"],
        "drop_bonus": vip_config["drop_bonus"],
        "total_recharge": total_recharge,
        "next_level_require": next_level["total_recharge"] if next_level else None
    }


# 商城物品
MALL_ITEMS = {
    "blessing_oil_pack": {
        "name": "祝福油礼包",
        "description": "包含5瓶祝福油",
        "price": 100,
        "items": [{"item_id": "blessing_oil", "quantity": 5}]
    },
    "hp_potion_pack": {
        "name": "红药礼包",
        "description": "包含100瓶大红药",
        "price": 50,
        "items": [{"item_id": "hp_potion_large", "quantity": 100}]
    },
    "mp_potion_pack": {
        "name": "蓝药礼包",
        "description": "包含100瓶大蓝药",
        "price": 50,
        "items": [{"item_id": "mp_potion_large", "quantity": 100}]
    },
    "town_scroll_pack": {
        "name": "回城卷礼包",
        "description": "包含50张回城卷",
        "price": 30,
        "items": [{"item_id": "town_scroll", "quantity": 50}]
    }
}


@router.get("/mall")
async def get_mall():
    """获取商城物品"""
    return MALL_ITEMS


@router.post("/mall/buy")
async def buy_mall_item(
    char_id: int,
    item_key: str,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """购买商城物品"""
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(401, "无效token")
    
    char = await db.get(Character, char_id)
    if not char or char.user_id != user_id:
        raise HTTPException(400, "角色不存在")
    
    if item_key not in MALL_ITEMS:
        raise HTTPException(400, "商品不存在")
    
    mall_item = MALL_ITEMS[item_key]
    
    if char.yuanbao < mall_item["price"]:
        raise HTTPException(400, "元宝不足")
    
    char.yuanbao -= mall_item["price"]
    
    # 添加物品到背包
    from backend.game.engine import GameEngine
    for item in mall_item["items"]:
        await GameEngine._add_item(char_id, item["item_id"], "white", db, item["quantity"])
    
    await db.commit()
    
    return {"success": True, "remaining_yuanbao": char.yuanbao}