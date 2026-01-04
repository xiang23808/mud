from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from contextlib import asynccontextmanager
import asyncio

from backend.database import get_db, init_db
from backend.models import User, Character, CharacterClass, Guild, GuildMember, GuildRank
from backend.schemas import UserRegister, UserLogin, TokenResponse, CharacterCreate, CharacterResponse
from backend.auth import hash_password, verify_password, create_token, decode_token
from backend.websocket.manager import manager
from backend.game.engine import GameEngine
from backend.game.data_loader import DataLoader
from backend.game.map_manager import map_manager
from backend.game.spawner import spawner
from backend.game.pvp import PVPSystem
from backend.api.recharge import router as recharge_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # 启动怪物刷新器
    asyncio.create_task(spawner.start())
    yield
    spawner.stop()

app = FastAPI(title="MUD Legend", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="frontend"), name="static")
app.include_router(recharge_router)

@app.get("/")
async def index():
    return FileResponse("frontend/index.html")

# ============ 用户认证 ============
@app.post("/api/register", response_model=TokenResponse)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "用户名已存在")
    user = User(username=data.username, password_hash=hash_password(data.password), email=data.email)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return TokenResponse(token=create_token(user.id), user_id=user.id)

@app.post("/api/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    return TokenResponse(token=create_token(user.id), user_id=user.id)

# ============ 角色管理 ============
@app.get("/api/characters", response_model=list[CharacterResponse])
async def get_characters(token: str, db: AsyncSession = Depends(get_db)):
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(401, "无效token")
    result = await db.execute(select(Character).where(Character.user_id == user_id))
    return result.scalars().all()

@app.post("/api/characters", response_model=CharacterResponse)
async def create_character(data: CharacterCreate, token: str, db: AsyncSession = Depends(get_db)):
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(401, "无效token")
    existing = await db.execute(select(Character).where(Character.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "角色名已存在")
    
    base_stats = {
        CharacterClass.WARRIOR: {"hp": 150, "mp": 30, "attack": 15, "defense": 10},
        CharacterClass.MAGE: {"hp": 80, "mp": 100, "attack": 20, "defense": 3},
        CharacterClass.TAOIST: {"hp": 100, "mp": 80, "attack": 12, "defense": 6},
    }
    stats = base_stats[data.char_class]
    char = Character(
        user_id=user_id, name=data.name, char_class=data.char_class,
        hp=stats["hp"], max_hp=stats["hp"], mp=stats["mp"], max_mp=stats["mp"],
        attack=stats["attack"], defense=stats["defense"]
    )
    db.add(char)
    await db.commit()
    await db.refresh(char)
    return char

# ============ 商店 ============
@app.get("/api/shop/{shop_type}")
async def get_shop(shop_type: str):
    return DataLoader.get_shop_items(shop_type)

@app.get("/api/skills/{char_id}")
async def get_skills(char_id: int, token: str, db: AsyncSession = Depends(get_db)):
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(401, "无效token")
    return await GameEngine.get_character_skills(char_id, db)

@app.post("/api/shop/buy")
async def buy_item(data: dict, token: str, db: AsyncSession = Depends(get_db)):
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(401, "无效token")
    
    item_id = data.get("item_id")
    quantity = data.get("quantity", 1)
    char_id = data.get("char_id")
    
    if not item_id or not char_id:
        raise HTTPException(400, "缺少必要参数")
    
    return await GameEngine.buy_item(char_id, item_id, quantity, db)

# ============ 行会 ============
@app.post("/api/guild/create")
async def create_guild(name: str, token: str, char_id: int, db: AsyncSession = Depends(get_db)):
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(401, "无效token")
    
    char = await db.get(Character, char_id)
    if not char or char.user_id != user_id:
        raise HTTPException(400, "角色不存在")
    
    if char.gold < 10000:
        raise HTTPException(400, "金币不足(需要10000)")
    
    existing = await db.execute(select(Guild).where(Guild.name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "行会名已存在")
    
    # 检查是否已有行会
    member = await db.execute(select(GuildMember).where(GuildMember.character_id == char_id))
    if member.scalar_one_or_none():
        raise HTTPException(400, "已加入其他行会")
    
    char.gold -= 10000
    guild = Guild(name=name, leader_id=char_id)
    db.add(guild)
    await db.commit()
    await db.refresh(guild)
    
    member = GuildMember(guild_id=guild.id, character_id=char_id, rank=GuildRank.LEADER)
    db.add(member)
    await db.commit()
    
    return {"success": True, "guild_id": guild.id}

@app.get("/api/guild/{guild_id}")
async def get_guild(guild_id: int, db: AsyncSession = Depends(get_db)):
    guild = await db.get(Guild, guild_id)
    if not guild:
        raise HTTPException(404, "行会不存在")
    
    result = await db.execute(select(GuildMember).where(GuildMember.guild_id == guild_id))
    members = result.scalars().all()
    
    return {
        "id": guild.id,
        "name": guild.name,
        "level": guild.level,
        "notice": guild.notice,
        "members": [{"character_id": m.character_id, "rank": m.rank.value} for m in members]
    }

# ============ WebSocket游戏通信 ============
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str, char_id: int, db: AsyncSession = Depends(get_db)):
    user_id = decode_token(token)
    if not user_id:
        await websocket.close(code=4001)
        return
    
    char = await db.get(Character, char_id)
    if not char or char.user_id != user_id:
        await websocket.close(code=4002)
        return
    
    await manager.connect(char_id, websocket)
    
    # 进入游戏
    enter_result = await GameEngine.enter_game(char_id, db)
    await manager.send(char_id, {"type": "enter_game", "data": enter_result})
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "move":
                result = await GameEngine.move(char_id, data["x"], data["y"], db)
                await manager.send(char_id, {"type": "move_result", "data": result})
                # 无论移动成功还是失败（遇到怪物），都更新地图状态
                # 这样可以显示阻挡路径的怪物
                await manager.send(char_id, {"type": "map_state", "data": map_manager.get_state(char_id)})
                if result.get("success"):
                    state = GameEngine._char_to_dict(await db.get(Character, char_id))
            
            elif msg_type == "attack":
                pos = tuple(data["pos"])
                result = await GameEngine.attack_monster(char_id, pos, db)
                await manager.send(char_id, {"type": "combat_result", "data": result})
                if result.get("victory"):
                    await manager.send(char_id, {"type": "map_state", "data": map_manager.get_state(char_id)})
            
            elif msg_type == "use_entrance":
                result = await GameEngine.use_entrance(char_id, data.get("entrance_id"), db)
                await manager.send(char_id, {"type": "map_change", "data": result})
            
            elif msg_type == "use_exit":
                result = await GameEngine.use_exit(char_id, data.get("exit_type", "exit"), db)
                await manager.send(char_id, {"type": "map_change", "data": result})
            
            elif msg_type == "return_city":
                result = await GameEngine.return_to_city(char_id, db)
                await manager.send(char_id, {"type": "map_change", "data": result})
            
            elif msg_type == "get_inventory":
                items = await GameEngine.get_inventory(char_id, data.get("storage", "inventory"), db)
                await manager.send(char_id, {"type": "inventory", "data": items})
            
            elif msg_type == "equip":
                result = await GameEngine.equip_item(char_id, data["slot"], db)
                await manager.send(char_id, {"type": "equip_result", "data": result})
            
            elif msg_type == "recycle":
                result = await GameEngine.recycle_item(char_id, data["slot"], db)
                await manager.send(char_id, {"type": "recycle_result", "data": result})
            
            elif msg_type == "move_to_warehouse":
                result = await GameEngine.move_to_warehouse(char_id, data["slot"], db)
                await manager.send(char_id, {"type": "move_result", "data": result})
            
            elif msg_type == "move_to_inventory":
                result = await GameEngine.move_to_inventory(char_id, data["slot"], db)
                await manager.send(char_id, {"type": "move_result", "data": result})
            
            elif msg_type == "learn_skill":
                result = await GameEngine.learn_skill(char_id, data["skill_id"], db)
                await manager.send(char_id, {"type": "learn_result", "data": result})
            
            elif msg_type == "use_skillbook":
                result = await GameEngine.use_skillbook(char_id, data["slot"], db)
                await manager.send(char_id, {"type": "skillbook_result", "data": result})
            
            elif msg_type == "use_skill":
                result = await GameEngine.use_skill(char_id, data["skill_id"], db)
                await manager.send(char_id, {"type": "skill_used", "data": result})
            
            elif msg_type == "get_equipment":
                result = await GameEngine.get_equipment(char_id, db)
                await manager.send(char_id, {"type": "equipment", "data": result})
            
            elif msg_type == "attack_player":
                target_id = data.get("target_id")
                result = await PVPSystem.attack_player(char_id, target_id, db)
                await manager.send(char_id, {"type": "pvp_result", "data": result})
                if result.get("success"):
                    await manager.send(target_id, {"type": "pvp_attacked", "data": result})
            
            elif msg_type == "get_map_state":
                await manager.send(char_id, {"type": "map_state", "data": map_manager.get_state(char_id)})
            
            elif msg_type == "chat":
                await manager.broadcast({"type": "chat", "char_id": char_id, "name": char.name, "message": data.get("message", "")})
            
            elif msg_type == "ping":
                await manager.send(char_id, {"type": "pong"})
    
    except WebSocketDisconnect:
        manager.disconnect(char_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)