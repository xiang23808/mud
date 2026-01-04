# 传奇MUD游戏

基于传奇2题材的纯文字MUD网页游戏。

## 快速开始

### 1. 启动数据库
```bash
docker-compose up -d
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 运行数据库迁移（可选）
如果是首次运行或需要更新数据库结构：
```bash
# 手动执行SQL迁移文件
psql -h localhost -U mud_user -d mud_game < database/migrations/001_add_skill_proficiency.sql
```

### 4. 运行服务器
```bash
python -m backend.main
```

### 5. 访问游戏
打开浏览器访问 http://localhost:8000

## 功能特性

### 已实现功能

#### 基础系统
- 用户注册/登录（JWT认证）
- 角色创建（战士/法师/道士）
- WebSocket实时通信
- 世界聊天

#### 地图系统
- **24x24随机迷宫生成**（已更新）
- 视野迷雾系统
- A*寻路算法
- 点击移动
- **多地图入口选择**（已改进）
- 地图切换（沃玛、僵尸洞、蜈蚣洞等）
- 一键回城

#### 战斗系统
- PVE回合制战斗
- 战斗日志逐条播放
- 经验/金币/物品掉落
- **怪物定时自动刷新**（已修复）
- Boss系统

#### 物品系统
- 5种品质（白/绿/蓝/紫/红）
- 200格背包 + 1000格仓库
- 装备穿戴
- 物品回收（金币/元宝）
- **完整的装备和物品数据**（已补充）

#### 技能系统
- 三职业技能树
- **已学习/未学习标识清晰**（已改进）
- **技能熟练度系统（0-1000，每1000升1级）**（已实现）
- 基础技能商店购买
- 高级技能怪物掉落
- 技能等级上限3级

#### PVP系统
- 野外自由PK
- 红名系统
- 死亡掉落

#### 行会系统
- 创建行会
- 行会成员管理
- 行会聊天

#### 充值系统
- 元宝充值（模拟）
- VIP等级
- 元宝商城

## 技术栈

- 后端: Python 3.11+ / FastAPI / WebSocket
- 数据库: PostgreSQL + Redis
- 前端: HTML + CSS + JavaScript + Canvas

## 项目结构

```
mud-legend/
├── backend/
│   ├── main.py              # FastAPI入口
│   ├── config.py            # 配置
│   ├── database.py          # 数据库连接
│   ├── auth.py              # JWT认证
│   ├── schemas.py           # Pydantic模型
│   ├── models/              # 数据库模型
│   │   ├── character.py     # 角色模型
│   │   ├── inventory.py     # 物品/技能模型
│   │   └── ...
│   ├── game/                # 游戏逻辑
│   │   ├── engine.py        # 游戏引擎
│   │   ├── combat.py        # 战斗系统
│   │   ├── map_manager.py   # 地图管理
│   │   ├── maze.py          # 迷宫生成
│   │   ├── pvp.py           # PVP系统
│   │   ├── spawner.py       # 怪物刷新
│   │   └── data_loader.py   # 数据加载
│   ├── api/
│   │   └── recharge.py      # 充值API
│   └── websocket/
│       └── manager.py       # WebSocket管理
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/game.js
├── data/                    # 游戏配置数据
│   ├── maps/
│   │   └── maps.json        # 地图配置（含多入口）
│   ├── monsters/
│   │   └── monsters.json    # 怪物数据（已补充完整）
│   ├── items/
│   │   ├── weapons.json     # 武器数据（已补充）
│   │   ├── armors.json      # 防具数据（已补充）
│   │   ├── accessories.json # 饰品数据（已补充）
│   │   └── consumables.json # 消耗品数据（已补充）
│   ├── skills/
│   │   ├── warrior.json     # 战士技能（已完善）
│   │   ├── mage.json        # 法师技能（已完善）
│   │   └── taoist.json      # 道士技能（已完善）
│   ├── npcs/
│   │   └── shops.json       # 商店NPC
│   └── config/
│       └── quality.json     # 品质配置
├── database/
│   └── migrations/          # 数据库迁移文件
│       └── 001_add_skill_proficiency.sql
├── plans/
│   └── mud-game-plan.md     # 设计文档
├── requirements.txt
├── docker-compose.yml
└── README.md
```

## 游戏指南

### 职业选择
- **战士**: 高血量高防御，近战物理输出
- **法师**: 低血量高魔法，远程魔法输出
- **道士**: 平衡型，可治疗可召唤

### 地图
- **主城（比奇省）**: 安全区，所有NPC，多个地图入口可选
- **沃玛森林** → 沃玛寺庙1-3层（沃玛教主）
- **僵尸洞1-3层**（尸王）
- **蜈蚣洞1-2层**

### 操作
- 点击地图格子移动（24x24格子）
- 点击怪物攻击
- 到达入口可选择进入对应地图
- 技能界面显示已学习和未学习技能
- 使用技能可增加熟练度，满1000升级

### 技能系统
- 学习技能后自动显示在"已学习"区域
- 每个技能最高3级
- 通过使用技能增加熟练度（每次+10）
- 熟练度达到1000自动升级

## 配置说明

所有游戏数据都在 `data/` 目录下的JSON文件中，可自由修改：

- `maps/maps.json` - 地图配置（含入口设置）
- `monsters/monsters.json` - 怪物属性（完整数据）
- `items/*.json` - 物品属性（武器、防具、饰品、消耗品）
- `skills/*.json` - 技能属性（战士、法师、道士）
- `config/quality.json` - 品质配置

## 最近更新

### v1.2.0 (2026-01-04)
- ✅ 地图尺寸从12x12扩展到24x24
- ✅ 修复怪物刷新系统
- ✅ 实现多入口地图选择机制
- ✅ 完善技能系统（已学习标识、熟练度升级）
- ✅ 补充完整的怪物数据（25+种怪物）
- ✅ 补充完整的装备数据（武器、防具、饰品）
- ✅ 补充完整的技能数据（三职业共20+技能）
- ✅ 数据库迁移文件生成

## 开发说明

### 数据库迁移
执行新的迁移文件以更新数据库结构：
```bash
psql -h localhost -U mud_user -d mud_game < database/migrations/001_add_skill_proficiency.sql
```

### 添加新内容
1. **新怪物**: 编辑 `data/monsters/monsters.json`
2. **新装备**: 编辑 `data/items/` 下对应文件
3. **新技能**: 编辑 `data/skills/` 下对应职业文件
4. **新地图**: 编辑 `data/maps/maps.json`

## 技术特点

- 24x24动态迷宫生成
- 实时怪物刷新系统
- 多入口地图传送机制
- 技能熟练度渐进式升级
- 完整的游戏数据体系

## 故障排除

### 怪物不刷新
- 确认服务器启动时spawner已启动
- 检查控制台是否有错误信息

### 地图入口不显示
- 确认 `data/maps/maps.json` 配置正确
- 检查地图实例是否正确加载

### 技能无法学习
- 确认等级是否满足要求
- 检查金币是否足够
- 确认该技能是否已学习

## 许可证

MIT License