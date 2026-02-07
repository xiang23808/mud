# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

传奇MUD游戏 - 基于Python FastAPI后端和原生JavaScript前端的文字MUD游戏。包含复杂战斗系统、动态迷宫生成、装备进阶和符文之语系统。

## 常用命令

```bash
# 启动服务 (MySQL + Redis)
docker-compose up -d

# 安装依赖
pip install -r requirements.txt

# 运行服务器 (端口8000)
python -m backend.main
# 或
.venv/Scripts/python.exe backend/main.py

# 访问游戏: http://localhost:8000
```

## 架构

### 后端 (`backend/`)
- **main.py**: FastAPI入口，REST + WebSocket端点
- **game/engine.py**: 核心GameEngine类（移动、战斗、装备、技能、背包）
- **game/combat.py**: CombatEngine战斗引擎，20+装备特效的伤害计算
- **game/effects.py**: EffectCalculator装备特效聚合器
- **game/runeword.py**: 镶嵌孔和符文之语组合系统
- **game/data_loader.py**: DataLoader，JSON资源缓存加载
- **game/map_manager.py**: 实例化地图管理
- **game/maze.py**: 24x24程序化迷宫生成
- **models/**: SQLAlchemy ORM模型（User、Character、InventoryItem、Equipment、CharacterSkill、Guild）
- **websocket/manager.py**: WebSocket连接管理和广播

### 前端 (`frontend/`)
- **index.html**: 单页应用（登录 -> 选角 -> 游戏）
- **js/game.js**: 游戏UI和WebSocket客户端逻辑
- Canvas渲染24x24地图，支持战争迷雾

### 数据 (`data/`)
- **maps/maps.json**: 16+地图定义，含入口/出口
- **monsters/monsters.json**: 怪物属性、掉落、伤害类型
- **items/**: weapons_new.json、armors_new.json、set_items.json、runes.json
- **skills/**: warrior.json、mage.json、taoist.json（战士/法师/道士）
- **config/**: quality.json（品质）、sets.json（套装）、runewords.json（符文之语）、drop_groups.json（掉落组）

## 核心系统

### 战斗流程
1. 客户端发送 `{type: "attack", pos: [x, y]}`
2. GameEngine.attack_monster() -> CombatEngine.process_attack()
3. EffectCalculator应用装备特效（暴击、闪避、吸血等）
4. 根据怪物等级从drop_groups.json生成掉落

### 装备系统
- 6个品质等级：白 -> 绿 -> 蓝 -> 紫 -> 红 -> 橙（神器）
- 10个装备槽：武器、头盔、衣服、腰带、靴子、项链、2戒指、2手镯
- 套装效果在2/4/6/8/9件时激活
- 33种符文（El到Zod）可镶嵌白色装备
- 40+符文之语配方，按序列组合触发

### WebSocket协议
客户端消息：move、attack、get_inventory、equip、learn_skill、socket_rune、use_skill、chat
服务端消息：enter_game、move_result、combat_result、map_state、inventory、equipment

## 数据库

MySQL 8.0 + Redis 7（通过docker-compose）。核心表：
- User、Character、InventoryItem、Equipment、CharacterSkill、Guild、GuildMember、StorageItem

## 配置文件

- **.env**: DATABASE_URL、REDIS_URL、SECRET_KEY
- **data/config/game_config.json**: exp_multiplier（经验倍率）、drop_rate_multiplier（掉落倍率）、gold_multiplier（金币倍率）

## 开发模式

- 所有数据库/游戏逻辑使用async/await
- 游戏内容通过JSON文件驱动（无硬编码）
- 每个玩家拥有独立的地图实例
- 实时更新通过WebSocket；静态数据（商店、技能）通过REST API
