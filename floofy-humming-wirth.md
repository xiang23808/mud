# MUD套装系统改造计划

## 一、改造目标

### 1.1 套装件数扩展
- **当前**：每套4件（头盔、胸甲、腰带、战靴）
- **改造后**：每套9件（头盔、胸甲、腰带、战靴、项链、戒指×2、手镯×2）

### 1.2 套装加成阶段
- **当前**：2件、4件
- **改造后**：2件、4件、6件、8件、9件（完美加成）

### 1.3 套装等级重新分布
- **当前**：15、30、45、50、60、70级（70级有8套过于集中）
- **改造后**：15、20、25、30、35、40、45、50、55、60、65、70、75级
- **70级拆分**：70级保留4套，4套调整为75级

### 1.4 后期怪物属性差异化
- 50-75级怪物属性按等级指数增长
- 每级差距约20-30%，每5级差距约1.5-2倍

---

## 二、套装等级重新分布方案

### 当前套装统计
| 等级 | 套装ID | 名称 | 职业 |
|------|--------|------|------|
| 15 | wildheart | 野性套装 | 战士/道士 |
| 15 | magister | 魔导套装 | 法师 |
| 30 | molten | 熔火套装 | 战士 |
| 30 | arcanist | 奥术套装 | 法师 |
| 30 | cenarion | 塞纳里奥套装 | 道士 |
| 45 | dragon | 龙鳞套装 | 战士 |
| 45 | nether | 灵风套装 | 法师 |
| 45 | earth | 碎地套装 | 道士 |
| 50 | insect_warrior | 昆虫战甲 | 战士 |
| 50 | insect_mage | 昆虫法袍 | 法师 |
| 60 | icecrown | 冰冠套装 | 战士 |
| 60 | shadowfrost | 暗影套装 | 法师 |
| 60 | lichking | 巫妖套装 | 道士 |
| 60 | qiraji_warrior | 其拉战甲 | 战士 |
| 60 | qiraji_mage | 其拉法袍 | 法师 |
| 70 | arcane_warrior | 奥术战铠 | 战士 |
| 70 | dragonscale_warrior | 龙鳞重甲 | 战士 |
| 70 | abyss_warrior | 深渊战甲 | 战士 |
| 70 | tidecaller_warrior | 潮汐战铠 | 战士 |
| 70 | phoenix_warrior | 凤凰战甲 | 战士 |
| 70 | shadowfiend_warrior | 影魔战铠 | 战士 |
| 70 | fury_warrior | 怒火战甲 | 战士 |
| 70 | sunfury_warrior | 日怒战铠 | 战士 |
| ... | (法师类似) | ... | ... |

### 新的套装等级分布

| 等级 | 战士套装 | 法师套装 | 道士套装 | 说明 |
|------|----------|----------|----------|------|
| **15** | wildheart（野性） | magister（魔导） | - | 保持，新增道士20级套 |
| **20** | courage（勇气）-新 | illumination（光辉）-新 | nature（自然）-新 | 全新低级套装 |
| **25** | guardian（守护）-新 | mystic（奥秘）-新 | spirit（野性之灵）-新 | 全新中级套装 |
| **30** | molten（熔火） | arcanist（奥术） | cenarion（塞纳里奥） | 保持不变 |
| **35** | flame（烈焰）-新 | frost（寒冰）-新 | poison（剧毒）-新 | 全新套装 |
| **40** | valor（勇气）-新 | arcane（魔能）-新 | healing（治愈）-新 | 全新套装 |
| **45** | dragon（龙鳞） | nether（灵风） | earth（碎地） | 保持不变 |
| **50** | insect_warrior（昆虫） | insect_mage（昆虫） | - | 其拉从60降到50，新增道士50级套 |
| **55** | thunder（雷霆）-新 | void（虚空）-新 | shadow（暗影）-新 | 全新高级套装 |
| **60** | icecrown（冰冠） | shadowfrost（暗影） | lichking（巫妖） | 保持不变 |
| **65** | storm（风暴）-新 | lava（熔岩）-新 | divine（神圣）-新 | 全新套装 |
| **70** | arcane_warrior, dragonscale_warrior, phoenix_warrior, fury_warrior | arcane_mage, phoenix_mage, fury_mage | - | 保留4套 |
| **75** | abyss_warrior, tidecaller_warrior, shadowfiend_warrior, sunfury_warrior | abyss_mage, tidecaller_mage, shadowfiend_mage, sunfury_mage | - | 4套从70调至75 |

---

## 三、套装加成配置（9件套）

### 套装加成结构示例
```json
{
  "wildheart": {
    "name": "野性套装",
    "class": ["warrior", "taoist"],
    "level": 15,
    "pieces": [
      "wildheart_helm", "wildheart_armor", "wildheart_belt", "wildheart_boots",
      "wildheart_necklace", "wildheart_ring", "wildheart_ring2",
      "wildheart_bracelet", "wildheart_bracelet2"
    ],
    "bonuses": {
      "2": {"hp_bonus": 30, "defense": 3, "attack_bonus": 3},
      "4": {"hp_bonus": 60, "defense": 8, "attack_bonus": 8, "effects": {"hit_rate": 0.01}},
      "6": {"hp_bonus": 120, "defense": 18, "attack_bonus": 18, "effects": {"hit_rate": 0.02, "dodge_rate": 0.02}},
      "8": {"hp_bonus": 200, "defense": 30, "attack_bonus": 30, "effects": {"hit_rate": 0.03, "dodge_rate": 0.03, "crush_rate": 0.03}},
      "9": {"hp_bonus": 100, "defense": 15, "attack_bonus": 15, "effects": {"double_attack": 0.05}}
    }
  }
}
```

### 加成设计原则
- **2件**：基础属性加成（HP/MP/攻击/防御约10-20%）
- **4件**：进阶属性 + 1个特效（约2-4%特效触发率）
- **6件**：高级属性 + 2个特效（约4-6%特效触发率）
- **8件**：终极属性 + 3个特效（约6-8%特效触发率）
- **9件**：完美加成（额外5-10%的强力特效，如双击、吸血等）

---

## 四、需要修改的文件

### 4.1 后端文件

| 文件 | 修改内容 |
|------|----------|
| `backend/game/effects.py` | 修改`calculate_set_bonuses`函数，支持6/8/9件加成检查 |

**修改位置**：`effects.py` 第420行
```python
# 当前：
for threshold in ["2", "4", "6"]:
    if count >= int(threshold) and threshold in set_cfg.get("bonuses", {}):

# 修改为：
for threshold in ["2", "4", "6", "8", "9"]:
    if count >= int(threshold) and threshold in set_cfg.get("bonuses", {}):
```

### 4.2 配置文件

| 文件 | 修改内容 |
|------|----------|
| `data/config/sets.json` | 1. 重构所有套装配置（添加项链/戒指/手镯到pieces）<br>2. 添加6/8/9件加成<br>3. 调整部分套装等级（70→75）<br>4. 添加新套装配置 |
| `data/items/set_items.json` | 为每套套装添加5件新装备：项链、戒指×2、手镯×2 |
| `data/config/drop_groups.json` | 添加新套装装备的掉落配置 |

### 4.3 前端文件

| 文件 | 修改内容 |
|------|----------|
| `frontend/js/game.js` | 修改套装显示：第853行显示"X/4件"改为"X/9件" |

**修改位置**：`game.js` 第853行
```javascript
// 当前：
<span style="color:#0f0;">(${s.count}/4件)</span>

// 修改为：
<span style="color:#0f0;">(${s.count}/9件)</span>
```

### 4.4 文档

| 文件 | 修改内容 |
|------|----------|
| `README.md` | 更新套装系统说明 |

---

## 五、新装备命名规范

### 项链
- 格式：`{套装名}_necklace`
- 示例：`wildheart_necklace`（野性项链）

### 戒指
- 格式：`{套装名}_ring` 和 `{套装名}_ring2`
- 示例：`wildheart_ring`（野性戒指）、`wildheart_ring2`（野性指环）

### 手镯
- 格式：`{套装名}_bracelet` 和 `{套装名}_bracelet2`
- 示例：`wildheart_bracelet`（野性手镯）、`wildheart_bracelet2`（野性护腕）

---

## 六、实施步骤

### Step 1: 修改套装加成计算逻辑
- 修改 `backend/game/effects.py` 支持6/8/9件加成

### Step 2: 创建新套装配置
- 重构 `data/config/sets.json`
- 添加新套装（20/25/35/40/55/65级）
- 调整70级部分套装到75级
- 添加6/8/9件加成

### Step 3: 添加新套装装备
- 在 `data/items/set_items.json` 中为每套套装添加5件装备
- 装备属性约为对应等级紫装水平的80-100%

### Step 4: 更新掉落配置
- 修改 `data/config/drop_groups.json` 添加新装备掉落

### Step 5: 修改前端显示
- 修改 `frontend/js/game.js` 套装件数显示

### Step 6: 更新文档
- 更新 `README.md`

---

## 七、验证测试

### 7.1 功能验证
1. 创建角色，装备套装各部位装备
2. 验证2/4/6/8/9件加成正确生效
3. 验证套装效果显示正确（X/9件）
4. 验证怪物掉落新装备

### 7.2 平衡性验证
1. 测试各等级套装的属性是否合理
2. 测试新怪物属性难度曲线
3. 验证高级副本挑战性

---

## 八、关键代码位置汇总

| 功能 | 文件路径 | 行号 |
|------|----------|------|
| 套装加成计算 | `backend/game/effects.py` | 381-436 |
| 套装配置 | `data/config/sets.json` | 全文 |
| 套装装备数据 | `data/items/set_items.json` | 全文 |
| 套装显示 | `frontend/js/game.js` | 472, 846-865 |
| 掉落配置 | `data/config/drop_groups.json` | 全文 |
