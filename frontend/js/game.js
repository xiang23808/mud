const API = '';
let token = localStorage.getItem('token');
let currentChar = null;
let ws = null;
let mapState = null;

const $ = id => document.getElementById(id);
const show = id => $(id).classList.remove('hidden');
const hide = id => $(id).classList.add('hidden');
const classNames = { warrior: '战士', mage: '法师', taoist: '道士' };

// API请求
async function api(path, data = null) {
    const opts = { headers: { 'Content-Type': 'application/json' } };
    if (data) { opts.method = 'POST'; opts.body = JSON.stringify(data); }
    const url = token ? `${API}${path}${path.includes('?') ? '&' : '?'}token=${token}` : `${API}${path}`;
    const res = await fetch(url, opts);
    if (!res.ok) throw new Error((await res.json()).detail || '请求失败');
    return res.json();
}

// 登录
async function login() {
    try {
        const res = await api('/api/login', { username: $('username').value, password: $('password').value });
        token = res.token;
        localStorage.setItem('token', token);
        showCharacterScreen();
    } catch (e) { $('login-error').textContent = e.message; }
}

// 注册
async function register() {
    try {
        const res = await api('/api/register', {
            username: $('username').value,
            password: $('password').value,
            email: $('username').value + '@game.com'  // 使用用户名生成默认email
        });
        token = res.token;
        localStorage.setItem('token', token);
        showCharacterScreen();
    } catch (e) { $('login-error').textContent = e.message; }
}

// 显示角色选择
async function showCharacterScreen() {
    hide('login-screen'); show('character-screen'); hide('game-screen');
    const chars = await api('/api/characters');
    $('character-list').innerHTML = chars.map(c => `
        <div class="char-card" onclick="enterGame(${c.id})">
            <div class="name">${c.name}</div>
            <div class="class ${c.char_class}">${classNames[c.char_class]}</div>
            <div class="level">Lv.${c.level}</div>
        </div>
    `).join('');
}

// 创建角色
async function createCharacter() {
    try {
        await api('/api/characters', { name: $('char-name').value, char_class: $('char-class').value });
        showCharacterScreen();
    } catch (e) { $('char-error').textContent = e.message; }
}

// 进入游戏
async function enterGame(charId) {
    const chars = await api('/api/characters');
    currentChar = chars.find(c => c.id === charId);
    hide('character-screen'); show('game-screen');
    updateCharInfo();
    connectWebSocket(charId);
}

function updateCharInfo() {
    const expNeeded = Math.floor(currentChar.level * 150 * Math.pow(1.15, currentChar.level - 1));
    const expPercent = Math.floor((currentChar.exp / expNeeded) * 100);
    $('char-info').textContent = `${currentChar.name} | ${classNames[currentChar.char_class]} | Lv.${currentChar.level} | HP:${currentChar.hp}/${currentChar.max_hp} | MP:${currentChar.mp}/${currentChar.max_mp} | 经验:${currentChar.exp}/${expNeeded}(${expPercent}%) | 金币:${currentChar.gold} | 元宝:${currentChar.yuanbao}`;
}

// WebSocket连接
function connectWebSocket(charId) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws?token=${token}&char_id=${charId}`);
    
    ws.onmessage = e => {
        const msg = JSON.parse(e.data);
        handleMessage(msg);
    };
    ws.onclose = () => output('[系统] 连接断开');
}

function handleMessage(msg) {
    switch(msg.type) {
        case 'enter_game':
            currentChar = msg.data.character;
            mapState = msg.data.map;
            updateCharInfo();
            updateCharStats();
            renderMap();
            addBattleLog('欢迎来到传奇世界！');
            break;
        case 'map_state':
            mapState = msg.data;
            renderMap();
            break;
        case 'map_change':
            if (msg.data.state) {
                mapState = msg.data.state;
                renderMap();
                output(`进入地图: ${mapState.map_id || msg.data.map_id}`);
            } else if (msg.data.error) {
                output(`[错误] ${msg.data.error}`);
            }
            break;
        case 'move_result':
            if (!msg.data.success) output(`[移动失败] ${msg.data.error}`);
            break;
        case 'combat_result':
            showCombat(msg.data);
            break;
        case 'inventory':
            renderInventory(msg.data);
            break;
        case 'equipment':
            renderEquipment(msg.data);
            // 同时更新角色属性面板，使用装备界面的综合属性和特效
            updateCharStatsFromEquipment(msg.data.total_stats, msg.data.total_effects);
            break;
        case 'chat':
            const chatEl = $('chat-messages');
            if (chatEl) {
                const div = document.createElement('div');
                div.textContent = `[${msg.name}] ${msg.message}`;
                div.style.color = '#888';
                chatEl.appendChild(div);
                chatEl.scrollTop = chatEl.scrollHeight;
            }
            break;
        case 'equip_result':
        case 'recycle_result':
        case 'learn_result':
            if (msg.data.success) output('[成功]');
            else output(`[失败] ${msg.data.error}`);
            break;
        case 'skillbook_result':
            if (msg.data.success) {
                output(`[成功] ${msg.data.message}`);
                ws.send(JSON.stringify({ type: 'get_inventory', storage: 'inventory' }));
            } else {
                output(`[失败] ${msg.data.error}`);
            }
            break;
        case 'disabled_skills':
            window.disabledSkills = msg.data || [];
            break;
        case 'skill_toggled':
            output(`[技能] ${msg.data.skill_id} ${msg.data.enabled ? '已启用' : '已禁用'}`);
            break;
        case 'runewords':
            runewordsData = msg.data;
            break;
        case 'runes':
            runesData = msg.data;
            break;
        case 'socket_rune_result':
            if (msg.data.success) {
                output(`[符文] ${msg.data.message}`);
                if (msg.data.runeword_id) {
                    addBattleLog(`[符文之语] ${msg.data.message}`);
                }
            } else {
                output(`[符文] 镶嵌失败: ${msg.data.error}`);
            }
            break;
    }
}

// 地图渲染
const CELL_SIZE = 20;
const canvas = $('map-canvas');
const ctx = canvas.getContext('2d', { alpha: false });

// 离屏canvas用于优化渲染
let offscreenCanvas = null;
let offscreenCtx = null;

function renderMap() {
    if (!mapState) return;
    
    // 初始化离屏canvas（Safari优化）
    if (!offscreenCanvas) {
        offscreenCanvas = document.createElement('canvas');
        offscreenCanvas.width = 480;
        offscreenCanvas.height = 480;
        offscreenCtx = offscreenCanvas.getContext('2d', { alpha: false });
    }
    
    $('map-name').textContent = mapState.map_name || mapState.map_id;
    offscreenCtx.fillStyle = '#000';
    offscreenCtx.fillRect(0, 0, 480, 480);
    
    const revealed = new Set(mapState.revealed.map(p => `${p[0]},${p[1]}`));
    
    for (let y = 0; y < 24; y++) {
        for (let x = 0; x < 24; x++) {
            const px = x * CELL_SIZE;
            const py = y * CELL_SIZE;
            
            if (!revealed.has(`${x},${y}`)) {
                offscreenCtx.fillStyle = '#222';
                offscreenCtx.fillRect(px, py, CELL_SIZE - 1, CELL_SIZE - 1);
                continue;
            }
            
            const isWall = mapState.maze[y][x] === 1;
            offscreenCtx.fillStyle = isWall ? '#444' : '#1a1a2e';
            offscreenCtx.fillRect(px, py, CELL_SIZE - 1, CELL_SIZE - 1);
            
            // 标记出入口（非主城地图）- 只在特定位置显示
            if (mapState.map_id !== 'main_city') {
                if ((x === 2 && y === 2) || (x === 21 && y === 21)) {
                    offscreenCtx.fillStyle = '#0ff';
                    offscreenCtx.fillRect(px + 5, py + 5, 10, 10);
                }
            }
        }
    }
    
    // 绘制入口 - 修复显示
    if (mapState.entrances) {
        for (const [id, entrance] of Object.entries(mapState.entrances)) {
            const [x, y] = entrance.position;
            if (revealed.has(`${x},${y}`)) {
                offscreenCtx.fillStyle = '#ff0';
                offscreenCtx.fillRect(x * CELL_SIZE + 5, y * CELL_SIZE + 5, 10, 10);
            }
        }
    }
    
    // 绘制NPC
    if (mapState.npcs) {
        for (const npc of mapState.npcs) {
            const [x, y] = npc.position;
            if (revealed.has(`${x},${y}`)) {
                offscreenCtx.fillStyle = '#00f';
                offscreenCtx.beginPath();
                offscreenCtx.arc(x * CELL_SIZE + 10, y * CELL_SIZE + 10, 6, 0, Math.PI * 2);
                offscreenCtx.fill();
            }
        }
    }
    
    // 怪物
    for (const [pos, monster] of Object.entries(mapState.monsters || {})) {
        const [x, y] = pos.split(',').map(Number);
        const px = x * CELL_SIZE;
        const py = y * CELL_SIZE;
        offscreenCtx.fillStyle = monster.is_boss ? '#ff0' : '#f00';
        offscreenCtx.beginPath();
        offscreenCtx.arc(px + 10, py + 10, 6, 0, Math.PI * 2);
        offscreenCtx.fill();
    }
    
    // 玩家
    if (mapState.position) {
        const [x, y] = mapState.position;
        offscreenCtx.fillStyle = '#0f0';
        offscreenCtx.beginPath();
        offscreenCtx.arc(x * CELL_SIZE + 10, y * CELL_SIZE + 10, 8, 0, Math.PI * 2);
        offscreenCtx.fill();
    }
    
    // 一次性绘制到主canvas
    ctx.drawImage(offscreenCanvas, 0, 0);
    
    // 更新右侧信息面板
    updateMapInfo();
}

// 更新角色属性面板
function updateCharStats() {
    if (!currentChar) return;
    // 请求装备信息以获取完整属性
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'get_equipment' }));
    }
}

// 使用装备界面的综合属性更新角色属性面板
function updateCharStatsFromEquipment(total_stats, total_effects) {
    const el = $('char-stats-info');
    if (!el) return;
    const effectsHtml = total_effects && Object.keys(total_effects).length > 0 ? `
        <div style="margin-top:8px;padding-top:8px;border-top:1px solid #333;color:#ff0;font-size:11px;">
            ${Object.entries(total_effects).map(([k,v]) => formatEffect(k,v)).join(' ')}
        </div>
    ` : '';
    el.innerHTML = `
        <div>等级: ${total_stats.level}</div>
        <div>HP: ${total_stats.hp}</div>
        <div>MP: ${total_stats.mp}</div>
        <div>攻击: ${total_stats.attack}</div>
        <div>魔法: ${total_stats.magic}</div>
        <div>防御: ${total_stats.defense}</div>
        <div>魔御: ${total_stats.magic_defense}</div>
        <div>幸运: ${total_stats.luck}</div>
        ${effectsHtml}
    `;
    // 同步更新currentChar的max_hp/max_mp用于顶部面板显示
    if (currentChar) {
        currentChar.max_hp = total_stats.hp;
        currentChar.max_mp = total_stats.mp;
        updateCharInfo();
    }
}

// 更新地图信息
function updateMapInfo() {
    if (!mapState) return;
    const el = $('map-info');
    if (!el) return;
    const monsterCount = Object.keys(mapState.monsters || {}).length;
    const explorePercent = Math.floor((mapState.revealed.length / (24 * 24)) * 100);
    el.innerHTML = `
        <div>当前地图: ${mapState.map_name || mapState.map_id}</div>
        <div>怪物数量: ${monsterCount}</div>
        <div>探索度: ${explorePercent}%</div>
    `;
}

// 添加战斗日志
function addBattleLog(msg) {
    const el = $('battle-log');
    if (!el) return;
    const div = document.createElement('div');
    div.textContent = msg;
    div.style.marginBottom = '3px';
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
    // 限制日志条数
    while (el.children.length > 20) {
        el.removeChild(el.firstChild);
    }
}

// 折叠/展开聊天框
function toggleChat() {
    const panel = $('chat-panel');
    const toggle = $('chat-toggle');
    if (panel.classList.contains('collapsed')) {
        panel.classList.remove('collapsed');
        toggle.textContent = '▼';
    } else {
        panel.classList.add('collapsed');
        toggle.textContent = '▶';
    }
}

// 地图点击
canvas.onclick = e => {
    if (!mapState) return;
    const rect = canvas.getBoundingClientRect();
    // 计算缩放比例以修复手机端点击错位
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = Math.floor((e.clientX - rect.left) * scaleX / CELL_SIZE);
    const y = Math.floor((e.clientY - rect.top) * scaleY / CELL_SIZE);
    
    // 检查是否在迷雾中（未揭示的区域）
    const revealed = new Set(mapState.revealed.map(p => `${p[0]},${p[1]}`));
    if (!revealed.has(`${x},${y}`)) {
        output('[系统] 该区域尚未探索，无法前往');
        return;
    }
    
    // 检查是否是墙壁
    if (mapState.maze[y][x] === 1) {
        output('[系统] 此处无法通行');
        return;
    }
    
    // 检查是否点击怪物 - 需要先验证是否可达
    const monsterKey = `${x},${y}`;
    if (mapState.monsters && mapState.monsters[monsterKey]) {
        // 获取当前位置
        const currentPos = mapState.position;
        // 检查是否相邻（可直接攻击）
        const dx = Math.abs(x - currentPos[0]);
        const dy = Math.abs(y - currentPos[1]);
        if (dx <= 1 && dy <= 1) {
            // 相邻位置，直接攻击
            ws.send(JSON.stringify({ type: 'attack', pos: [x, y] }));
        } else {
            // 不相邻，尝试移动到怪物位置
            ws.send(JSON.stringify({ type: 'move', x, y }));
        }
        return;
    }
    
    // 检查是否点击NPC（只在已揭示区域）- 玩家需要在NPC附近才能对话
    if (mapState.npcs && revealed.has(`${x},${y}`)) {
        for (const npc of mapState.npcs) {
            if (npc.position[0] === x && npc.position[1] === y) {
                // 检查玩家是否在NPC附近（相邻）
                const currentPos = mapState.position;
                const dx = Math.abs(x - currentPos[0]);
                const dy = Math.abs(y - currentPos[1]);
                if (dx <= 1 && dy <= 1) {
                    // 在NPC附近，触发对话
                    handleNPCClick(npc);
                } else {
                    // 不在附近，先移动到NPC位置附近
                    ws.send(JSON.stringify({ type: 'move', x, y }));
                }
                return;
            }
        }
    }
    
    // 检查是否点击入口（需要站在入口位置）
    if (mapState.entrances && mapState.position[0] === x && mapState.position[1] === y) {
        for (const [id, entrance] of Object.entries(mapState.entrances)) {
            if (entrance.position[0] === x && entrance.position[1] === y) {
                if (confirm(`进入${entrance.name}?`)) {
                    ws.send(JSON.stringify({ type: 'use_entrance', entrance_id: id }));
                }
                return;
            }
        }
    }
    
    // 检查是否点击出口（非主城）- 只在特定位置(2,2)和(21,21)
    if (mapState.map_id !== 'main_city') {
        const isEntrance = x === 2 && y === 2;
        const isExit = x === 21 && y === 21;
        
        if (isEntrance || isExit) {
            const exitType = isEntrance ? 'entrance' : 'exit';
            // 检查玩家是否在出入口位置
            const px = mapState.position[0];
            const py = mapState.position[1];
            if ((isEntrance && px === 2 && py === 2) || (isExit && px === 21 && py === 21)) {
                ws.send(JSON.stringify({ type: 'use_exit', exit_type: exitType }));
                return;
            }
        }
    }
    
    // 移动
    ws.send(JSON.stringify({ type: 'move', x, y }));
};

// 品质颜色映射
const QUALITY_COLORS = {
    white: '#fff', green: '#0f0', blue: '#00bfff', purple: '#a020f0', orange: '#ffa500'
};

// 特效名称映射
const EFFECT_NAMES = {
    double_attack: '双击', hit_rate: '命中', dodge_rate: '闪避', crush_rate: '压碎',
    lifesteal: '吸血', reflect: '反弹', hp_on_hit: '击回HP', mp_on_hit: '击回MP',
    block_rate: '格挡率', block_amount: '格挡量', extra_phys: '附物伤', extra_magic: '附魔伤',
    damage_reduction: '减伤', stun_rate: '眩晕', splash_rate: '溅射', poison_damage: '毒伤',
    poison_rounds: '毒回合', ignore_defense: '穿防', ignore_magic_def: '穿魔御',
    crit_rate: '暴击率', crit_damage: '暴击伤', attack_speed: '攻速'
};

// 符文之语数据缓存
let runewordsData = null;
let runesData = null;

// 格式化特效值
function formatEffect(key, value) {
    if (['hp_on_hit', 'mp_on_hit', 'extra_phys', 'extra_magic', 'poison_damage', 'poison_rounds'].includes(key)) {
        return `${EFFECT_NAMES[key]}+${value}`;
    }
    return `${EFFECT_NAMES[key]}${Math.round(value * 100)}%`;
}

// 生成特效显示HTML
function renderEffects(effects) {
    if (!effects || Object.keys(effects).length === 0) return '';
    return Object.entries(effects)
        .filter(([k, v]) => v > 0 && EFFECT_NAMES[k])
        .map(([k, v]) => `<span style="color:#ff0;font-size:10px;">${formatEffect(k, v)}</span>`)
        .join(' ');
}

// 格式化套装加成
function formatSetBonus(bonus) {
    const parts = [];
    if (bonus.hp_bonus) parts.push(`HP+${bonus.hp_bonus}`);
    if (bonus.mp_bonus) parts.push(`MP+${bonus.mp_bonus}`);
    if (bonus.defense) parts.push(`防御+${bonus.defense}`);
    if (bonus.magic_defense) parts.push(`魔御+${bonus.magic_defense}`);
    if (bonus.effects) {
        for (const [k, v] of Object.entries(bonus.effects)) {
            if (EFFECT_NAMES[k]) parts.push(formatEffect(k, v));
        }
    }
    return parts.join(' ');
}

// 战斗显示
function showCombat(data) {
    // 处理错误情况
    if (!data.success && data.error) {
        output(`[战斗错误] ${data.error}`);
        return;
    }
    if (!data.logs || data.logs.length === 0) {
        output('[战斗错误] 无战斗数据');
        return;
    }

    show('combat-modal');
    const log = $('combat-log');
    log.innerHTML = '';
    $('combat-close').classList.add('hidden');
    
    // 解析初始状态
    let playerHp = currentChar.max_hp, playerMaxHp = currentChar.max_hp;
    let playerMp = currentChar.max_mp, playerMaxMp = currentChar.max_mp;
    let monsters = []; // [{name, quality, hp, maxHp}]
    
    // 从COMBAT_INIT解析初始血量
    for (const line of data.logs) {
        if (line.startsWith('COMBAT_INIT|')) {
            const parts = line.split('|');
            const [pHp, pMaxHp] = parts[1].split('/').map(Number);
            const [pMp, pMaxMp] = parts[2].split('/').map(Number);
            playerHp = pHp; playerMaxHp = pMaxHp;
            playerMp = pMp; playerMaxMp = pMaxMp;
            // 解析怪物列表（从parts[3]开始都是怪物，格式：#idx名字[品质]:hp/maxHp）
            for (let j = 3; j < parts.length; j++) {
                const m = parts[j];
                if (!m) continue;
                const match = m.match(/#(\d+)(.+)\[(\w+)\]:(\d+)\/(\d+)/);
                if (match) {
                    monsters.push({idx: parseInt(match[1]), name: match[2], quality: match[3], hp: parseInt(match[4]), maxHp: parseInt(match[5])});
                }
            }
            break;
        }
    }
    
    // 构建血量显示区域（左边玩家，右边怪物）
    const hpBar = document.createElement('div');
    hpBar.id = 'combat-hp-bar';
    hpBar.style.cssText = 'display:flex;gap:15px;margin-bottom:10px;padding:10px;background:#1a1a2e;border-radius:5px;';
    
    // 左边：玩家HP/MP + 召唤物
    const playerDiv = document.createElement('div');
    playerDiv.style.cssText = 'flex:1;';
    playerDiv.innerHTML = `
        <div style="color:#0f0;font-weight:bold;margin-bottom:5px;">${currentChar.name}</div>
        <div style="margin-bottom:3px;">HP: <span id="player-hp">${playerHp}</span>/${playerMaxHp}</div>
        <div style="height:8px;background:#333;border-radius:4px;margin-bottom:5px;"><div id="player-hp-fill" style="height:100%;width:100%;background:#0f0;border-radius:4px;transition:width 0.3s;"></div></div>
        <div style="margin-bottom:3px;">MP: <span id="player-mp">${playerMp}</span>/${playerMaxMp}</div>
        <div style="height:8px;background:#333;border-radius:4px;"><div id="player-mp-fill" style="height:100%;width:100%;background:#00f;border-radius:4px;transition:width 0.3s;"></div></div>
        <div id="summon-hp-area" style="margin-top:8px;display:none;">
            <div style="color:#ff0;font-weight:bold;margin-bottom:3px;"><span id="summon-name">召唤物</span></div>
            <div style="margin-bottom:3px;">HP: <span id="summon-hp">0</span>/<span id="summon-max-hp">0</span></div>
            <div style="height:6px;background:#333;border-radius:3px;"><div id="summon-hp-fill" style="height:100%;width:100%;background:#ff0;border-radius:3px;transition:width 0.3s;"></div></div>
        </div>
    `;
    hpBar.appendChild(playerDiv);
    
    // 右边：所有怪物HP（不限制高度，全部显示）
    const monstersDiv = document.createElement('div');
    monstersDiv.id = 'monsters-hp-area';
    monstersDiv.style.cssText = 'flex:1;';
    monsters.forEach(m => {
        const color = QUALITY_COLORS[m.quality] || '#fff';
        monstersDiv.innerHTML += `
            <div style="margin-bottom:5px;">
                <span style="color:${color};font-weight:bold;">${m.name}</span>
                : <span id="monster-hp-${m.idx}">${m.hp}</span>/${m.maxHp}
                <div style="height:6px;background:#333;border-radius:3px;"><div id="monster-hp-fill-${m.idx}" style="height:100%;width:100%;background:${color};border-radius:3px;transition:width 0.3s;"></div></div>
            </div>
        `;
    });
    hpBar.appendChild(monstersDiv);
    log.appendChild(hpBar);
    
    // 战斗信息区域
    const battleInfo = document.createElement('div');
    battleInfo.id = 'battle-info-area';
    battleInfo.style.cssText = 'max-height:250px;overflow-y:auto;';
    log.appendChild(battleInfo);
    
    let i = 0;
    const interval = setInterval(() => {
        if (i >= data.logs.length) {
            clearInterval(interval);
            $('combat-close').classList.remove('hidden');
            if (data.victory) {
                currentChar = data.character;
                updateCharInfo();
                updateCharStats();
            }
            return;
        }
        const line = data.logs[i];
        
        // 解析COMBAT_STATUS更新血量
        if (line.startsWith('COMBAT_STATUS|')) {
            const parts = line.split('|');
            const [pHp] = parts[1].split('/').map(Number);
            const [pMp] = parts[2].split('/').map(Number);
            $('player-hp').textContent = Math.max(0, pHp);
            $('player-mp').textContent = Math.max(0, pMp);
            $('player-hp-fill').style.width = Math.max(0, (pHp / playerMaxHp) * 100) + '%';
            $('player-mp-fill').style.width = Math.max(0, (pMp / playerMaxMp) * 100) + '%';
            // 更新怪物血量和召唤物血量
            const monsterParts = parts.slice(3).filter(p => p);
            let hasSummon = false;
            for (const mp of monsterParts) {
                // 召唤物血量格式: SUMMON:名字:hp/maxHp
                const summonMatch = mp.match(/SUMMON:(.+):(\d+)\/(\d+)/);
                if (summonMatch) {
                    hasSummon = true;
                    const summonArea = $('summon-hp-area');
                    if (summonArea) {
                        summonArea.style.display = 'block';
                        $('summon-name').textContent = summonMatch[1];
                        $('summon-hp').textContent = summonMatch[2];
                        $('summon-max-hp').textContent = summonMatch[3];
                        $('summon-hp-fill').style.width = Math.max(0, (parseInt(summonMatch[2]) / parseInt(summonMatch[3])) * 100) + '%';
                    }
                    continue;
                }
                const match = mp.match(/#(\d+).+:(\d+)\/(\d+)/);
                if (match) {
                    const idx = parseInt(match[1]);
                    const hp = parseInt(match[2]);
                    const hpEl = $(`monster-hp-${idx}`);
                    const fillEl = $(`monster-hp-fill-${idx}`);
                    const m = monsters.find(mon => mon.idx === idx);
                    if (hpEl && fillEl && m) {
                        hpEl.textContent = hp;
                        fillEl.style.width = Math.max(0, (hp / m.maxHp) * 100) + '%';
                    }
                }
            }
            // 如果没有召唤物信息，隐藏召唤物区域
            if (!hasSummon) {
                const summonArea = $('summon-hp-area');
                if (summonArea) summonArea.style.display = 'none';
            }
            i++;
            return;
        }
        
        // 跳过COMBAT_INIT行
        if (line.startsWith('COMBAT_INIT|')) { i++; return; }
        
        const div = document.createElement('div');
        if (line.includes('回合')) div.className = 'round';
        else if (line.includes('胜利')) div.className = 'victory';
        else if (line.includes('失败')) div.className = 'defeat';
        else if (line.includes('暴击') || line.includes('压碎')) div.style.color = '#ff6600';
        else if (line.includes('吸血') || line.includes('击回')) div.style.color = '#00ff88';
        else if (line.includes('眩晕')) div.style.color = '#ffff00';
        else if (line.includes('中毒') || line.includes('毒伤')) div.style.color = '#aa00ff';
        else if (line.includes('溅射')) div.style.color = '#ff00ff';
        else if (line.includes('格挡') || line.includes('减伤') || line.includes('反弹')) div.style.color = '#00aaff';
        else if (line.includes('闪避')) div.style.color = '#88ff88';
        else if (line.includes('双次攻击')) div.style.color = '#ffaa00';
        else if (line.includes('伤害')) div.className = 'damage';
        div.textContent = line;
        $('battle-info-area').appendChild(div);
        $('battle-info-area').scrollTop = $('battle-info-area').scrollHeight;
        i++;
    }, 200);
}

function closeCombat() {
    hide('combat-modal');
    ws.send(JSON.stringify({ type: 'get_map_state' }));
}

// 背包
function openInventory() {
    show('inventory-modal');
    ws.send(JSON.stringify({ type: 'get_inventory', storage: 'inventory' }));
}

function switchStorage(type) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    ws.send(JSON.stringify({ type: 'get_inventory', storage: type }));
}

let currentStorageType = 'inventory';
let currentItemFilter = 'all';

function renderInventory(data) {
    const items = data.items || data;
    const storage_type = data.storage_type || 'inventory';
    currentStorageType = storage_type;
    const max_slots = storage_type === 'warehouse' ? 1000 : 200;
    const used_slots = items.length;
    const free_slots = max_slots - used_slots;
    
    // 根据筛选条件过滤物品
    const filteredItems = currentItemFilter === 'all' ? items : items.filter(item => {
        const type = item.info?.type;
        const slot = item.info?.slot;
        if (currentItemFilter === 'weapon') return type === 'weapon';
        if (currentItemFilter === 'armor') return type === 'armor' && (slot === 'body' || slot === 'helmet' || slot === 'head');
        if (currentItemFilter === 'accessory') return type === 'accessory' || (type === 'armor' && ['boots', 'belt'].includes(slot));
        if (currentItemFilter === 'consumable') return type === 'consumable';
        if (currentItemFilter === 'material') return type === 'material' || type === 'boss_summon' || type === 'skillbook';
        if (currentItemFilter === 'rune') return type === 'rune';
        if (currentItemFilter === 'runeword') return item.runeword_id;
        return true;
    });
    
    const grid = $('inventory-grid');
    // 筛选按钮
    const filterBtns = `
        <div style="grid-column: 1/-1; margin-bottom: 10px; display: flex; gap: 5px; flex-wrap: wrap; justify-content: center;">
            <button onclick="setItemFilter('all')" style="background:${currentItemFilter === 'all' ? '#0a0' : '#333'};">全部</button>
            <button onclick="setItemFilter('weapon')" style="background:${currentItemFilter === 'weapon' ? '#0a0' : '#333'};">武器</button>
            <button onclick="setItemFilter('armor')" style="background:${currentItemFilter === 'armor' ? '#0a0' : '#333'};">衣服</button>
            <button onclick="setItemFilter('accessory')" style="background:${currentItemFilter === 'accessory' ? '#0a0' : '#333'};">饰品</button>
            <button onclick="setItemFilter('consumable')" style="background:${currentItemFilter === 'consumable' ? '#0a0' : '#333'};">消耗品</button>
            <button onclick="setItemFilter('material')" style="background:${currentItemFilter === 'material' ? '#0a0' : '#333'};">材料</button>
            <button onclick="setItemFilter('rune')" style="background:${currentItemFilter === 'rune' ? '#f80' : '#333'};color:${currentItemFilter === 'rune' ? '#fff' : '#f80'};">符文</button>
            <button onclick="setItemFilter('runeword')" style="background:${currentItemFilter === 'runeword' ? '#ff0' : '#333'};color:${currentItemFilter === 'runeword' ? '#000' : '#ff0'};">符文之语</button>
        </div>
    `;
    // 背包显示全部回收按钮，仓库不显示
    const recycleAllBtn = storage_type === 'inventory' && items.length > 0
        ? `<button onclick="recycleAll()" style="background:#c00;margin-left:10px;">全部回收</button>`
        : '';
    const organizeBtn = `<button onclick="organizeInventory('${storage_type}')" style="background:#060;margin-left:10px;">整理</button>`;
    grid.innerHTML = filterBtns + `<div style="grid-column: 1/-1; color: #ffd700; text-align: center; margin-bottom: 10px;">
        已使用: ${used_slots}/${max_slots} | 可用空间: ${free_slots} | 显示: ${filteredItems.length}/${items.length} ${organizeBtn} ${recycleAllBtn}
    </div>` + filteredItems.map(item => {
        const isEquipable = item.info?.type === 'weapon' || item.info?.type === 'armor' || item.info?.type === 'accessory';
        const isSkillbook = item.info?.type === 'skillbook';
        const isBossSummon = item.info?.type === 'boss_summon';
        const info = item.info || {};
        const attrs = [];
        // 等级需求
        if (info.level_req && info.level_req > 1) attrs.push(`需Lv.${info.level_req}`);
        // 支持min-max格式
        if (info.attack_min || info.attack_max) attrs.push(`攻击:${info.attack_min||0}-${info.attack_max||0}`);
        else if (info.attack) attrs.push(`攻击:${info.attack}`);
        if (info.magic_min || info.magic_max) attrs.push(`魔法:${info.magic_min||0}-${info.magic_max||0}`);
        else if (info.magic) attrs.push(`魔法:${info.magic}`);
        if (info.defense_min || info.defense_max) attrs.push(`防御:${info.defense_min||0}-${info.defense_max||0}`);
        else if (info.defense) attrs.push(`防御:${info.defense}`);
        if (info.magic_defense_min || info.magic_defense_max) attrs.push(`魔御:${info.magic_defense_min||0}-${info.magic_defense_max||0}`);
        else if (info.magic_defense) attrs.push(`魔御:${info.magic_defense}`);
        if (info.hp_bonus) attrs.push(`HP+${info.hp_bonus}`);
        if (info.mp_bonus) attrs.push(`MP+${info.mp_bonus}`);
        const effectsHtml = renderEffects(info.effects);
        const moveBtn = storage_type === 'inventory'
            ? `<button onclick="moveToWarehouse(${item.slot})">存仓</button>`
            : `<button onclick="moveToInventory(${item.slot})">取出</button>`;
        // 仓库不显示回收按钮
        const recycleBtn = storage_type === 'inventory' ? `<button onclick="recycleItem(${item.slot})">回收</button>` : '';
        // 套装标识
        const setTag = info.set_id ? '<span style="color:#a020f0;">[套]</span>' : '';
        // 孔位显示 - 优先使用后端返回的socket_display
        const socketCount = item.sockets || 0;
        const socketedCount = item.socketed_runes?.length || 0;
        const socketDisplay = item.socket_display
            ? `<span style="color:#0ff;font-size:11px;">${item.socket_display}</span>`
            : (socketCount > 0 ? `<span style="color:#0ff;font-size:11px;">[孔:${'◆'.repeat(socketedCount)}${'◇'.repeat(socketCount - socketedCount)}]</span>` : '');
        // 符文之语标识 - 显示具体名称
        const runewordTag = item.runeword_id
            ? `<span style="color:#ffd700;font-weight:bold;">[${info.runeword_name || '符文之语'}]</span>`
            : '';
        // 符文之语描述
        const runewordDesc = info.runeword_description
            ? `<div style="font-size:10px;color:#ffd700;">${info.runeword_description}</div>`
            : '';
        // 镶嵌按钮（白色品质有孔装备且未完成符文之语且有空孔时显示）
        const canSocketInv = storage_type === 'inventory' && item.quality === 'white' && socketCount > 0 && !item.runeword_id && socketedCount < socketCount;
        const socketBtnInv = canSocketInv ? `<button onclick="openSocketRunePopupInventory(${item.slot})" style="background:#f80;">镶嵌</button>` : '';
        return `
        <div class="inv-slot quality-${item.quality}">
            <div class="item-name">${runewordTag}${setTag}${info.name || item.item_id}</div>
            ${socketDisplay ? `<div>${socketDisplay}</div>` : ''}
            ${attrs.length ? `<div style="font-size:10px;color:#8f8;">${attrs.join(' ')}</div>` : ''}
            ${effectsHtml ? `<div>${effectsHtml}</div>` : ''}
            ${runewordDesc}
            <div>x${item.quantity}</div>
            <div class="item-actions">
                ${isEquipable && storage_type === 'inventory' ? `<button onclick="equipItem(${item.slot},'${info.slot || ''}')">装备</button>` : ''}
                ${socketBtnInv}
                ${isSkillbook && storage_type === 'inventory' ? `<button onclick="useSkillbook(${item.slot})">学习</button>` : ''}
                ${isBossSummon && storage_type === 'inventory' ? `<button onclick="useBossItem(${item.slot})">使用</button>` : ''}
                ${moveBtn}
                ${recycleBtn}
            </div>
        </div>
    `;
    }).join('');
}

function equipItem(slot, itemSlot) {
    // 如果是戒指或手镯，显示选择对话框
    if (itemSlot === 'ring' || itemSlot === 'bracelet') {
        const leftSlot = itemSlot + '_left';
        const rightSlot = itemSlot + '_right';
        const leftName = itemSlot === 'ring' ? '左戒指' : '左手镯';
        const rightName = itemSlot === 'ring' ? '右戒指' : '右手镯';
        
        const dialog = document.createElement('div');
        dialog.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#0f3460;border:2px solid #ffd700;padding:20px;border-radius:10px;z-index:1001;';
        dialog.innerHTML = `
            <h3 style="color:#ffd700;margin-bottom:15px;">选择装备位置</h3>
            <button onclick="doEquip(${slot},'${leftSlot}');this.parentElement.remove()" style="margin:5px;padding:10px 20px;">${leftName}</button>
            <button onclick="doEquip(${slot},'${rightSlot}');this.parentElement.remove()" style="margin:5px;padding:10px 20px;">${rightName}</button>
            <br><button onclick="this.parentElement.remove()" style="margin-top:10px;">取消</button>
        `;
        document.body.appendChild(dialog);
    } else {
        doEquip(slot);
    }
}

function doEquip(slot, targetSlot = null) {
    const msg = { type: 'equip', slot };
    if (targetSlot) msg.target_slot = targetSlot;
    ws.send(JSON.stringify(msg));
    setTimeout(() => ws.send(JSON.stringify({ type: 'get_inventory', storage: 'inventory' })), 500);
}

function recycleItem(slot) {
    if (confirm('确定回收此物品？')) {
        ws.send(JSON.stringify({ type: 'recycle', slot }));
        setTimeout(() => ws.send(JSON.stringify({ type: 'get_inventory', storage: 'inventory' })), 500);
    }
}

function recycleAll() {
    const filterNames = {
        'all': '全部物品',
        'weapon': '武器',
        'armor': '衣服',
        'accessory': '饰品',
        'consumable': '消耗品',
        'material': '材料',
        'rune': '符文',
        'runeword': '符文之语装备'
    };
    const filterName = filterNames[currentItemFilter] || '当前筛选';
    if (confirm(`确定回收背包中的${filterName}？此操作不可撤销！`)) {
        ws.send(JSON.stringify({ type: 'recycle_all', filter: currentItemFilter }));
        setTimeout(() => ws.send(JSON.stringify({ type: 'get_inventory', storage: 'inventory' })), 500);
    }
}

function useSkillbook(slot) {
    ws.send(JSON.stringify({ type: 'use_skillbook', slot }));
}

function useBossItem(slot) {
    if (confirm('确定使用此物品召唤Boss战斗？')) {
        ws.send(JSON.stringify({ type: 'use_boss_item', slot }));
    }
}

function moveToWarehouse(slot) {
    ws.send(JSON.stringify({ type: 'move_to_warehouse', slot }));
    setTimeout(() => ws.send(JSON.stringify({ type: 'get_inventory', storage: 'inventory' })), 300);
}

function organizeInventory(storage) {
    ws.send(JSON.stringify({ type: 'organize_inventory', storage }));
}

function moveToInventory(slot) {
    ws.send(JSON.stringify({ type: 'move_to_inventory', slot }));
    setTimeout(() => ws.send(JSON.stringify({ type: 'get_inventory', storage: 'warehouse' })), 300);
}

function setItemFilter(filter) {
    currentItemFilter = filter;
    ws.send(JSON.stringify({ type: 'get_inventory', storage: currentStorageType }));
}

// 装备
function openEquipment() {
    show('equipment-modal');
    ws.send(JSON.stringify({ type: 'get_equipment' }));
}

function renderEquipment(data) {
    const { equipment, total_stats, total_effects, set_bonuses } = data;
    
    // 综合特效显示
    const effectsHtml = total_effects && Object.keys(total_effects).length > 0 ? `
        <div style="margin-top:10px;padding-top:10px;border-top:1px solid #333;">
            <div style="color:#ff0;margin-bottom:5px;">综合特效:</div>
            <div style="display:flex;flex-wrap:wrap;gap:8px;">
                ${Object.entries(total_effects).map(([k,v]) => `<span style="color:#ff0;font-size:11px;">${formatEffect(k,v)}</span>`).join('')}
            </div>
        </div>
    ` : '';
    
    // 套装加成显示（显示所有阶段，激活亮色，未激活灰色）
    const setBonusHtml = set_bonuses && set_bonuses.length > 0 ? `
        <div style="margin-top:10px;padding-top:10px;border-top:1px solid #333;">
            <div style="color:#a020f0;margin-bottom:5px;">套装效果:</div>
            ${set_bonuses.map(s => {
                const fullBonuses = s.full_bonuses || s.bonuses;
                return `
                <div style="margin-bottom:8px;">
                    <span style="color:#ffd700;">${s.name}</span> <span style="color:#0f0;">(${s.count}/9件)</span>
                    ${Object.entries(fullBonuses).map(([threshold, bonus]) => {
                        const isActive = s.count >= parseInt(threshold);
                        const color = isActive ? '#0f0' : '#666';
                        return `
                        <div style="font-size:11px;color:${color};margin-left:10px;">
                            ${isActive ? '✓' : '○'} ${threshold}件: ${formatSetBonus(bonus)}
                        </div>
                    `;}).join('')}
                </div>
            `;}).join('')}
        </div>
    ` : '';
    
    // 显示综合属性
    const statsHtml = `
        <div style="background: #0f3460; padding: 15px; margin-bottom: 15px; border-radius: 5px;">
            <h4 style="color: #ffd700; margin-bottom: 10px;">综合属性</h4>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; color: #0f0;">
                <div>等级: ${total_stats.level}</div>
                <div>幸运: ${total_stats.luck}</div>
                <div>HP: ${total_stats.hp}</div>
                <div>MP: ${total_stats.mp}</div>
                <div>攻击: ${total_stats.attack}</div>
                <div>魔法: ${total_stats.magic}</div>
                <div>防御: ${total_stats.defense}</div>
                <div>魔御: ${total_stats.magic_defense}</div>
            </div>
            ${effectsHtml}
            ${setBonusHtml}
        </div>
    `;
    
    // 装备槽位名称映射
    const slotNames = {
        weapon: '武器',
        helmet: '头盔',
        armor: '衣服',
        belt: '腰带',
        boots: '鞋子',
        necklace: '项链',
        ring_left: '左戒指',
        ring_right: '右戒指',
        bracelet_left: '左手镯',
        bracelet_right: '右手镯'
    };
    
    // 显示装备槽位
    const slotsHtml = `
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;">
            ${Object.entries(slotNames).map(([slot, name]) => {
                const item = equipment[slot];
                const itemEffects = item?.info?.effects ? renderEffects(item.info.effects) : '';
                const setTag = item?.info?.set_id ? '<span style="color:#a020f0;">[套]</span>' : '';
                // 符文之语显示
                const runewordTag = item?.runeword_id ? `<span style="color:#ffd700;font-weight:bold;">[${item.info?.runeword_name || '符文之语'}]</span>` : '';
                // 孔位显示
                const socketDisplay = item?.socket_display ? `<span style="color:#0ff;font-size:12px;">${item.socket_display}</span>` : '';
                // 镶嵌按钮（仅白色品质有孔装备且未完成符文之语时显示）
                const canSocket = item && item.quality === 'white' && item.sockets > 0 && !item.runeword_id && (item.socketed_runes?.length || 0) < item.sockets;
                const socketBtn = canSocket ? `<button onclick="openSocketRunePopup('${slot}')" style="font-size:10px;margin-top:5px;background:#f80;">镶嵌符文</button>` : '';
                return `
                    <div class="equip-slot ${item ? 'quality-' + item.quality : ''}"
                         style="background: #0f3460; padding: 12px; border-radius: 5px; min-height: 80px;">
                        <div style="color: #ffd700; font-weight: bold; margin-bottom: 5px;">${name}</div>
                        ${item ? `
                            <div style="font-size: 14px; margin-bottom: 3px;">${runewordTag}${setTag}${item.info?.name || item.item_id}</div>
                            ${item.info?.level_req > 1 ? `<div style="font-size: 10px; color: #aaa;">需Lv.${item.info.level_req}</div>` : ''}
                            ${socketDisplay ? `<div style="margin-bottom:3px;">${socketDisplay}</div>` : ''}
                            <div style="font-size: 10px; color: #8f8;">
                                ${item.info?.attack_min || item.info?.attack_max ? `攻击:${item.info.attack_min||0}-${item.info.attack_max||0} ` : (item.info?.attack ? `攻击:${item.info.attack} ` : '')}
                                ${item.info?.magic_min || item.info?.magic_max ? `魔法:${item.info.magic_min||0}-${item.info.magic_max||0} ` : (item.info?.magic ? `魔法:${item.info.magic} ` : '')}
                                ${item.info?.defense_min || item.info?.defense_max ? `防御:${item.info.defense_min||0}-${item.info.defense_max||0} ` : (item.info?.defense ? `防御:${item.info.defense} ` : '')}
                                ${item.info?.magic_defense_min || item.info?.magic_defense_max ? `魔御:${item.info.magic_defense_min||0}-${item.info.magic_defense_max||0} ` : (item.info?.magic_defense ? `魔御:${item.info.magic_defense} ` : '')}
                                ${item.info?.hp_bonus ? `HP+${item.info.hp_bonus} ` : ''}
                                ${item.info?.mp_bonus ? `MP+${item.info.mp_bonus}` : ''}
                            </div>
                            ${itemEffects ? `<div style="margin-top:3px;">${itemEffects}</div>` : ''}
                            ${item.info?.runeword_description ? `<div style="margin-top:3px;color:#ffd700;font-size:10px;">${item.info.runeword_description}</div>` : ''}
                            ${socketBtn}
                        ` : '<div style="color: #666;">未装备</div>'}
                    </div>
                `;
            }).join('')}
        </div>
    `;
    
    $('equipment-stats').innerHTML = statsHtml;
    $('equipment-slots').innerHTML = slotsHtml;
}

// 技能
async function openSkills() {
    show('skills-modal');
    // 获取禁用技能列表
    ws.send(JSON.stringify({ type: 'get_disabled_skills' }));
    await new Promise(r => setTimeout(r, 100)); // 等待响应
    const disabledSkills = window.disabledSkills || [];
    
    const skillData = await api(`/api/skills/${currentChar.id}`);
    const list = $('skills-list');
    
    // 已学习技能（带开关）
    const learnedHtml = skillData.learned.length > 0 ? `
        <div class="skills-section">
            <h3>已学习技能 (${skillData.learned.length})</h3>
            ${skillData.learned.map(skill => {
                const isDisabled = disabledSkills.includes(skill.skill_id);
                const isActive = skill.info?.type === 'active';
                return `
                <div class="skill-item learned">
                    <div class="skill-info">
                        <div class="skill-name">✓ ${skill.info?.name || skill.skill_id}</div>
                        <div class="skill-desc">${skill.info?.description || ''}</div>
                        <div class="skill-level">等级: ${skill.level}/3 | 熟练度: ${skill.proficiency}/1000</div>
                    </div>
                    ${isActive ? `
                        <label style="display:flex;align-items:center;gap:5px;cursor:pointer;">
                            <input type="checkbox" ${isDisabled ? '' : 'checked'} onchange="toggleSkill('${skill.skill_id}', this.checked)">
                            <span style="font-size:12px;">${isDisabled ? '已禁用' : '战斗中使用'}</span>
                        </label>
                    ` : '<span style="font-size:11px;color:#888;">被动</span>'}
                </div>
            `;}).join('')}
        </div>
    ` : '';
    
    // 可学习技能（分为可购买和掉落获取）
    const buyable = skillData.available.filter(s => !s.learned && s.info?.buy_price > 0);
    const dropOnly = skillData.available.filter(s => !s.learned && (!s.info?.buy_price || s.info.buy_price === 0));
    
    const buyableHtml = buyable.length > 0 ? `
        <div class="skills-section">
            <h3>可购买技能 (${buyable.length})</h3>
            ${buyable.map(skill => {
                const canLearn = skill.can_learn;
                const buttonText = canLearn ? `学习 (${skill.info.buy_price}金币)` : `需要Lv.${skill.info.level_req}`;
                return `
                    <div class="skill-item ${canLearn ? '' : 'disabled'}">
                        <div class="skill-info">
                            <div class="skill-name">${skill.info?.name || skill.skill_id}</div>
                            <div class="skill-desc">${skill.info?.description || ''} (需要等级:${skill.info?.level_req || 1})</div>
                        </div>
                        <button onclick="learnSkill('${skill.skill_id}')" ${canLearn ? '' : 'disabled'}>${buttonText}</button>
                    </div>
                `;
            }).join('')}
        </div>
    ` : '';
    
    const dropHtml = dropOnly.length > 0 ? `
        <div class="skills-section">
            <h3>掉落获取技能 (${dropOnly.length})</h3>
            ${dropOnly.map(skill => `
                <div class="skill-item disabled">
                    <div class="skill-info">
                        <div class="skill-name">${skill.info?.name || skill.skill_id}</div>
                        <div class="skill-desc">${skill.info?.description || ''} (需要等级:${skill.info?.level_req || 1})</div>
                    </div>
                    <span style="color:#ff0;font-size:12px;">怪物掉落</span>
                </div>
            `).join('')}
        </div>
    ` : '';
    
    list.innerHTML = learnedHtml + buyableHtml + dropHtml;
}

function learnSkill(skillId) {
    ws.send(JSON.stringify({ type: 'learn_skill', skill_id: skillId }));
    setTimeout(() => openSkills(), 500);
}

function toggleSkill(skillId, enabled) {
    ws.send(JSON.stringify({ type: 'toggle_skill', skill_id: skillId, enabled }));
    if (!window.disabledSkills) window.disabledSkills = [];
    if (enabled) {
        window.disabledSkills = window.disabledSkills.filter(s => s !== skillId);
    } else if (!window.disabledSkills.includes(skillId)) {
        window.disabledSkills.push(skillId);
    }
}

// 回城
function returnToCity() {
    ws.send(JSON.stringify({ type: 'return_city' }));
}

// 商城
let currentShopTab = 'consumable';
const SHOP_ITEMS = {
    consumable: [
        { id: 'hp_potion_small', name: '小红瓶', price: 20, currency: 'gold', desc: '恢复50HP' },
        { id: 'hp_potion_small_100', name: '小红瓶(100个)', price: 1800, currency: 'gold', desc: '恢复50HP x100' },
        { id: 'hp_potion_medium', name: '中红瓶', price: 60, currency: 'gold', desc: '恢复150HP' },
        { id: 'hp_potion_medium_100', name: '中红瓶(100个)', price: 5400, currency: 'gold', desc: '恢复150HP x100' },
        { id: 'hp_potion_large', name: '大红瓶', price: 200, currency: 'gold', desc: '恢复500HP' },
        { id: 'hp_potion_large_100', name: '大红瓶(100个)', price: 18000, currency: 'gold', desc: '恢复500HP x100' },
        { id: 'hp_potion_super', name: '特大红瓶', price: 500, currency: 'gold', desc: '恢复1500HP' },
        { id: 'hp_potion_super_100', name: '特大红瓶(100个)', price: 45000, currency: 'gold', desc: '恢复1500HP x100' },
        { id: 'mp_potion_small', name: '小蓝瓶', price: 15, currency: 'gold', desc: '恢复30MP' },
        { id: 'mp_potion_small_100', name: '小蓝瓶(100个)', price: 1350, currency: 'gold', desc: '恢复30MP x100' },
        { id: 'mp_potion_medium', name: '中蓝瓶', price: 50, currency: 'gold', desc: '恢复100MP' },
        { id: 'mp_potion_medium_100', name: '中蓝瓶(100个)', price: 4500, currency: 'gold', desc: '恢复100MP x100' },
        { id: 'mp_potion_large', name: '大蓝瓶', price: 150, currency: 'gold', desc: '恢复300MP' },
        { id: 'mp_potion_large_100', name: '大蓝瓶(100个)', price: 13500, currency: 'gold', desc: '恢复300MP x100' },
        { id: 'mp_potion_super', name: '特大蓝瓶', price: 400, currency: 'gold', desc: '恢复800MP' },
        { id: 'mp_potion_super_100', name: '特大蓝瓶(100个)', price: 36000, currency: 'gold', desc: '恢复800MP x100' },
        { id: 'return_scroll', name: '回城卷', price: 50, currency: 'gold', desc: '传送回主城' }
    ],
    equipment: [
        { id: 'wooden_sword', name: '木剑', price: 100, currency: 'gold', desc: '战士初级武器' },
        { id: 'wooden_staff', name: '木杖', price: 100, currency: 'gold', desc: '法师初级武器' },
        { id: 'wooden_wand', name: '木制魔杖', price: 100, currency: 'gold', desc: '道士初级武器' },
        { id: 'cloth_armor', name: '布衣', price: 80, currency: 'gold', desc: '通用初级防具' },
        { id: 'leather_boots', name: '皮靴', price: 200, currency: 'gold', desc: '通用初级鞋子' },
        { id: 'leather_belt', name: '皮带', price: 150, currency: 'gold', desc: '通用初级腰带' }
    ],
    special: [
        { id: 'blessing_oil', name: '祝福油', price: 100, currency: 'yuanbao', desc: '永久+1幸运' },
        { id: 'woma_horn', name: '沃玛号角', price: 50, currency: 'yuanbao', desc: '召唤沃玛教主' },
        { id: 'zuma_piece', name: '祖玛碎片', price: 80, currency: 'yuanbao', desc: '召唤祖玛教主' },
        { id: 'demon_heart', name: '魔族之心', price: 120, currency: 'yuanbao', desc: '召唤魔族领主' }
    ]
};

function openShop() {
    show('shop-modal');
    renderShop();
}

function switchShopTab(tab) {
    currentShopTab = tab;
    document.querySelectorAll('#shop-modal .tab').forEach((t, i) => {
        t.classList.toggle('active', ['consumable', 'equipment', 'special'][i] === tab);
    });
    renderShop();
}

function renderShop() {
    const items = SHOP_ITEMS[currentShopTab] || [];
    $('shop-grid').innerHTML = items.map(item => `
        <div class="inv-slot" style="background:#1a1a2e;">
            <div class="item-name" style="color:#ffd700;">${item.name}</div>
            <div style="font-size:11px;color:#888;">${item.desc}</div>
            <div style="color:${item.currency === 'yuanbao' ? '#ff0' : '#0f0'};">
                ${item.price} ${item.currency === 'yuanbao' ? '元宝' : '金币'}
            </div>
            <div class="item-actions">
                <button onclick="shopBuy('${item.id}', 1, '${item.currency}', ${item.price})">购买x1</button>
                <button onclick="shopBuy('${item.id}', 10, '${item.currency}', ${item.price})">x10</button>
            </div>
        </div>
    `).join('');
}

async function shopBuy(itemId, quantity, currency, price) {
    const total = price * quantity;
    const currencyName = currency === 'yuanbao' ? '元宝' : '金币';
    const balance = currency === 'yuanbao' ? currentChar.yuanbao : currentChar.gold;
    
    if (balance < total) {
        output(`[商城] ${currencyName}不足`);
        return;
    }
    
    try {
        const res = await fetch(`/api/shop/buy?token=${token}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ item_id: itemId, quantity, char_id: currentChar.id, currency })
        });
        const result = await res.json();
        if (result.success) {
            output(`[商城] 购买成功`);
            if (currency === 'yuanbao') currentChar.yuanbao -= total;
            else currentChar.gold -= total;
            updateCharInfo();
            // 刷新背包
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'get_inventory', storage: 'inventory' }));
            }
        } else {
            output(`[商城] ${result.error || '购买失败'}`);
        }
    } catch (e) {
        output(`[商城] 购买失败`);
    }
}

// 刷新地图
function refreshMap() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'reset_map' }));
        addBattleLog('[系统] 地图已重置');
    }
}

// 聊天
function sendChat() {
    const input = $('chat-input');
    if (ws && input.value.trim()) {
        ws.send(JSON.stringify({ type: 'chat', message: input.value }));
        const el = $('chat-messages');
        if (el) {
            const div = document.createElement('div');
            div.textContent = `[${currentChar.name}] ${input.value}`;
            div.style.color = '#0f0';
            el.appendChild(div);
            el.scrollTop = el.scrollHeight;
        }
        input.value = '';
    }
}

// NPC交互
function handleNPCClick(npc) {
    switch(npc.id) {
        case 'weapon_shop':
            output(`[${npc.npc_name}] 欢迎来到武器店！这里有各种精良的武器装备。`);
            showShopDialog('武器店', 'weapon');
            break;
        case 'armor_shop':
            output(`[${npc.npc_name}] 欢迎来到防具店！这里有最好的防护装备。`);
            showShopDialog('防具店', 'armor');
            break;
        case 'potion_shop':
            output(`[${npc.npc_name}] 欢迎来到药店！需要补充药水吗？`);
            showShopDialog('药店', 'consumable');
            break;
        case 'skill_shop':
            output(`[${npc.npc_name}] 欢迎来到书店！想要学习新技能吗？`);
            openSkills();
            break;
        case 'recycle_shop':
            output(`[${npc.npc_name}] 我这里回收各种装备和物品，价格公道！`);
            openInventory();
            break;
        case 'warehouse':
            output(`[${npc.npc_name}] 欢迎使用仓库服务！`);
            openInventory();
            break;
    }
}

// 显示商店对话框
async function showShopDialog(shopName, itemType) {
    try {
        const items = await api(`/api/shop/${itemType}`);
        const itemList = Object.entries(items).map(([id, item]) => `
            <div style="padding: 10px; border-bottom: 1px solid #333;">
                <div style="color: #ffd700;">${item.name}</div>
                <div style="color: #888; font-size: 12px;">价格: ${item.buy_price || 0} 金币</div>
                <button onclick="buyItem('${id}', 1)" style="margin-top: 5px;">购买</button>
            </div>
        `).join('');
        
        const dialog = document.createElement('div');
        dialog.style.cssText = 'position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: #0f3460; border: 2px solid #ffd700; padding: 20px; border-radius: 10px; max-width: 400px; max-height: 500px; overflow-y: auto; z-index: 1000;';
        dialog.innerHTML = `
            <h3 style="color: #ffd700; margin-bottom: 15px;">${shopName}</h3>
            <div>${itemList}</div>
            <button onclick="this.parentElement.remove()" style="margin-top: 15px; width: 100%;">关闭</button>
        `;
        document.body.appendChild(dialog);
    } catch (e) {
        output('[错误] 无法打开商店');
    }
}

// 购买物品
async function buyItem(itemId, quantity) {
    try {
        const url = `/api/shop/buy?token=${token}`;
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ item_id: itemId, quantity, char_id: currentChar.id })
        });
        
        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail || '购买失败');
        }
        
        const result = await res.json();
        if (result.success) {
            output('[购买成功]');
            // 更新角色信息
            const chars = await api('/api/characters');
            currentChar = chars.find(c => c.id === currentChar.id);
            updateCharInfo();
        } else {
            output(`[购买失败] ${result.error}`);
        }
    } catch (e) {
        output(`[错误] ${e.message}`);
    }
}

// 输出
function output(msg) {
    addBattleLog(msg);
}

// 关闭弹窗
function closeModal(id) { hide(id); }

// ========== 符文之语系统 ==========

// 当前选中的装备槽位（用于镶嵌）
let currentSocketSlot = null;
// 当前选中的背包槽位（用于背包物品镶嵌）
let currentSocketInventorySlot = null;

// 打开符文镶嵌弹窗（装备界面）
function openSocketRunePopup(equipmentSlot) {
    currentSocketSlot = equipmentSlot;
    currentSocketInventorySlot = null;
    // 获取背包中的符文
    ws.send(JSON.stringify({ type: 'get_inventory', storage: 'inventory' }));
    // 等待背包数据返回后显示弹窗
    setTimeout(() => {
        showSocketRuneDialog(equipmentSlot, false);
    }, 200);
}

// 打开符文镶嵌弹窗（背包界面）
function openSocketRunePopupInventory(inventorySlot) {
    currentSocketSlot = null;
    currentSocketInventorySlot = inventorySlot;
    // 获取背包中的符文
    ws.send(JSON.stringify({ type: 'get_inventory', storage: 'inventory' }));
    // 等待背包数据返回后显示弹窗
    setTimeout(() => {
        showSocketRuneDialog(null, true, inventorySlot);
    }, 200);
}

// 显示符文镶嵌对话框
function showSocketRuneDialog(equipmentSlot, isInventory = false, inventorySlot = null) {
    // 从最近的背包数据中获取符文
    const inventoryGrid = $('inventory-grid');
    if (!inventoryGrid) return;

    const title = isInventory ? '选择符文镶嵌到背包装备' : `选择符文镶嵌到${getSlotName(equipmentSlot)}`;

    // 获取背包数据（需要重新请求）
    // 这里简化处理，创建一个弹窗
    const dialog = document.createElement('div');
    dialog.id = 'socket-rune-dialog';
    dialog.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#0f3460;border:2px solid #f80;padding:20px;border-radius:10px;max-width:600px;max-height:85vh;overflow-y:auto;z-index:1001;';
    dialog.innerHTML = `
        <h3 style="color:#f80;margin-bottom:15px;">${title}</h3>
        <div id="available-runewords" style="margin-bottom:15px;"></div>
        <div id="rune-list" style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;"></div>
        <div style="margin-top:15px;color:#888;font-size:12px;">提示：符文镶嵌后无法取出，请谨慎选择！</div>
        <button onclick="closeSocketRuneDialog()" style="margin-top:15px;width:100%;">关闭</button>
    `;
    document.body.appendChild(dialog);

    // 请求背包数据并填充符文列表
    loadRunesForSocket(isInventory, inventorySlot, equipmentSlot);
}

// 获取槽位中文名
function getSlotName(slot) {
    const names = { weapon: '武器', helmet: '头盔', armor: '衣服', belt: '腰带', boots: '鞋子' };
    return names[slot] || slot;
}

// 加载可镶嵌的符文
function loadRunesForSocket(isInventory = false, inventorySlot = null, equipmentSlot = null) {
    // 请求背包和符文之语数据
    ws.send(JSON.stringify({ type: 'get_runewords' }));
    ws.send(JSON.stringify({ type: 'get_runes' }));

    const handler = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === 'inventory') {
            ws.removeEventListener('message', handler);
            // 过滤符文（背包镶嵌时要排除目标装备自己）
            const runes = (msg.data.items || []).filter(item =>
                item.info?.type === 'rune' && item.slot !== inventorySlot
            );

            // 获取目标装备信息
            let targetEquipment = null;
            if (isInventory && inventorySlot !== null) {
                // 从背包中获取
                targetEquipment = (msg.data.items || []).find(item => item.slot === inventorySlot);
            } else if (equipmentSlot && characterData?.equipment) {
                // 从已装备中获取
                targetEquipment = characterData.equipment[equipmentSlot];
            }

            // 显示可制作的符文之语
            renderAvailableRunewords(targetEquipment, runes);
            renderRuneList(runes, isInventory);
        }
    };
    ws.addEventListener('message', handler);
    ws.send(JSON.stringify({ type: 'get_inventory', storage: 'inventory' }));
}

// 渲染可制作的符文之语
function renderAvailableRunewords(targetEquipment, availableRunes) {
    const container = document.getElementById('available-runewords');
    if (!container) return;

    if (!targetEquipment) {
        container.innerHTML = '<div style="color:#888;font-size:12px;">无法获取装备信息</div>';
        return;
    }

    const slot = targetEquipment.info?.slot || targetEquipment.slot;
    const totalSockets = targetEquipment.sockets || 0;
    const socketedRunes = targetEquipment.socketed_runes || [];
    const emptySockets = totalSockets - socketedRunes.length;
    const runewords = runewordsData || {};
    const runes = runesData || {};

    // 获取背包中可用的符文ID列表
    const availableRuneIds = {};
    (availableRunes || []).forEach(r => {
        const runeId = r.item_id || r.id;
        availableRuneIds[runeId] = (availableRuneIds[runeId] || 0) + (r.quantity || 1);
    });

    // 筛选可制作的符文之语
    const matchingRunewords = [];

    for (const [rwId, rw] of Object.entries(runewords)) {
        // 检查槽位是否匹配
        if (!rw.allowed_slots?.includes(slot)) continue;

        // 检查符文数量是否匹配孔数
        const requiredRunes = rw.runes || [];
        if (requiredRunes.length !== totalSockets) continue;

        // 检查是否与已镶嵌的符文兼容
        let isCompatible = true;
        for (let i = 0; i < socketedRunes.length; i++) {
            if (socketedRunes[i] !== requiredRunes[i]) {
                isCompatible = false;
                break;
            }
        }

        if (!isCompatible) continue;

        // 计算还需要的符文
        const remainingRunes = requiredRunes.slice(socketedRunes.length);

        // 检查是否有足够的符文来完成
        const tempAvailable = { ...availableRuneIds };
        let canComplete = true;
        let missingRunes = [];

        for (const runeId of remainingRunes) {
            if (tempAvailable[runeId] && tempAvailable[runeId] > 0) {
                tempAvailable[runeId]--;
            } else {
                canComplete = false;
                missingRunes.push(runeId);
            }
        }

        matchingRunewords.push({
            ...rw,
            id: rwId,
            remainingRunes,
            canComplete,
            missingRunes,
            progress: socketedRunes.length
        });
    }

    // 排序：可完成的优先，然后按等级
    matchingRunewords.sort((a, b) => {
        if (a.canComplete !== b.canComplete) return a.canComplete ? -1 : 1;
        return a.level_req - b.level_req;
    });

    if (matchingRunewords.length === 0) {
        container.innerHTML = `
            <div style="background:#1a1a2e;padding:10px;border-radius:5px;border:1px solid #555;">
                <div style="color:#888;font-size:12px;">
                    当前装备(${getSlotName(slot)}, ${totalSockets}孔)没有匹配的符文之语配方
                    ${socketedRunes.length > 0 ? `<br>已镶嵌: ${socketedRunes.map(r => runes[r]?.name || r).join(' → ')}` : ''}
                </div>
            </div>
        `;
        return;
    }

    const html = `
        <div style="border:1px solid #ffd700;border-radius:5px;padding:10px;background:#1a1a2e;">
            <div style="color:#ffd700;font-weight:bold;margin-bottom:8px;">
                可制作的符文之语 (${getSlotName(slot)}, ${totalSockets}孔)
                ${socketedRunes.length > 0 ? `<span style="color:#0f0;font-size:11px;margin-left:10px;">已镶嵌${socketedRunes.length}/${totalSockets}</span>` : ''}
            </div>
            <div style="max-height:200px;overflow-y:auto;">
                ${matchingRunewords.map(rw => {
                    const runeDisplay = (rw.runes || []).map((r, idx) => {
                        const runeName = runes[r]?.name || r.replace('rune_', '');
                        const isSocketed = idx < rw.progress;
                        const isNext = idx === rw.progress;
                        const isMissing = rw.missingRunes.includes(r);

                        let style = 'color:#888;';
                        if (isSocketed) style = 'color:#0f0;text-decoration:line-through;';
                        else if (isNext) style = 'color:#ff0;font-weight:bold;';
                        else if (isMissing) style = 'color:#f44;';
                        else style = 'color:#0ff;';

                        return `<span style="${style}">${runeName}</span>`;
                    }).join(' → ');

                    const statusIcon = rw.canComplete ? '✓' : '✗';
                    const statusColor = rw.canComplete ? '#0f0' : '#f44';
                    const statusText = rw.canComplete ? '可制作' : `缺少: ${rw.missingRunes.map(r => runes[r]?.name || r).join(', ')}`;

                    return `
                        <div style="padding:8px;margin-bottom:6px;background:#0f3460;border-radius:4px;border-left:3px solid ${rw.canComplete ? '#0f0' : '#555'};">
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <span style="color:#ffd700;font-weight:bold;">${rw.name} <span style="color:#888;font-size:10px;">${rw.name_en}</span></span>
                                <span style="color:${statusColor};font-size:11px;">${statusIcon} ${rw.canComplete ? '可制作' : ''}</span>
                            </div>
                            <div style="font-size:11px;color:#888;margin:4px 0;">Lv.${rw.level_req}</div>
                            <div style="font-size:11px;margin:4px 0;">顺序: ${runeDisplay}</div>
                            <div style="font-size:10px;color:#0ff;">${rw.description || ''}</div>
                            ${!rw.canComplete ? `<div style="font-size:10px;color:#f44;margin-top:4px;">${statusText}</div>` : ''}
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;

    container.innerHTML = html;
}

// 渲染符文列表
function renderRuneList(runes, isInventory = false) {
    const list = document.getElementById('rune-list');
    if (!list) return;

    if (runes.length === 0) {
        list.innerHTML = '<div style="grid-column:1/-1;color:#888;text-align:center;">背包中没有符文</div>';
        return;
    }

    list.innerHTML = runes.map(rune => `
        <div style="background:#1a1a2e;padding:10px;border-radius:5px;cursor:pointer;border:1px solid #f80;" onclick="socketRune(${rune.slot}, ${isInventory})">
            <div style="color:#f80;font-weight:bold;">${rune.info?.name || rune.item_id}</div>
            <div style="font-size:11px;color:#888;">Lv.${rune.info?.level_req || 1}需求</div>
            <div style="font-size:10px;color:#0f0;">x${rune.quantity}</div>
        </div>
    `).join('');
}

// 执行符文镶嵌
function socketRune(runeSlot, isInventory = false) {
    if (!confirm('确定要镶嵌这个符文吗？镶嵌后无法取出！')) return;

    if (isInventory) {
        // 背包物品镶嵌
        if (currentSocketInventorySlot === null) return;
        ws.send(JSON.stringify({
            type: 'socket_rune_inventory',
            target_slot: currentSocketInventorySlot,
            rune_slot: runeSlot
        }));
    } else {
        // 已装备物品镶嵌
        if (!currentSocketSlot) return;
        ws.send(JSON.stringify({
            type: 'socket_rune',
            equipment_slot: currentSocketSlot,
            rune_slot: runeSlot
        }));
    }
    closeSocketRuneDialog();
}

// 关闭符文镶嵌对话框
function closeSocketRuneDialog() {
    const dialog = document.getElementById('socket-rune-dialog');
    if (dialog) dialog.remove();
    currentSocketSlot = null;
}

// 打开符文之语图鉴
function openRunewordCompendium() {
    // 请求符文之语数据
    ws.send(JSON.stringify({ type: 'get_runewords' }));
    ws.send(JSON.stringify({ type: 'get_runes' }));

    setTimeout(() => {
        showRunewordCompendiumDialog();
    }, 300);
}

// 显示符文之语图鉴
function showRunewordCompendiumDialog() {
    const dialog = document.createElement('div');
    dialog.id = 'runeword-compendium-dialog';
    dialog.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#0f3460;border:2px solid #ffd700;padding:20px;border-radius:10px;width:90%;max-width:800px;max-height:80vh;overflow-y:auto;z-index:1001;';

    // 获取符文之语数据
    const runewords = runewordsData || {};
    const runes = runesData || {};

    // 按等级分组
    const grouped = {};
    for (const [id, rw] of Object.entries(runewords)) {
        const level = rw.level_req || 1;
        const tier = Math.floor(level / 10) * 10;
        if (!grouped[tier]) grouped[tier] = [];
        grouped[tier].push({ ...rw, id });
    }

    // 生成HTML
    const tiersHtml = Object.entries(grouped).sort((a, b) => a[0] - b[0]).map(([tier, rws]) => `
        <div style="margin-bottom:20px;">
            <h4 style="color:#ffd700;margin-bottom:10px;">Lv.${tier}-${parseInt(tier)+9}</h4>
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;">
                ${rws.sort((a, b) => a.level_req - b.level_req).map(rw => {
                    const runeNames = rw.runes.map(r => runes[r]?.name || r).join(' + ');
                    const slots = rw.allowed_slots.map(s => getSlotName(s)).join('/');
                    return `
                        <div style="background:#1a1a2e;padding:12px;border-radius:5px;border:1px solid #ffd700;">
                            <div style="color:#ffd700;font-weight:bold;font-size:14px;">${rw.name} <span style="color:#888;font-size:11px;">${rw.name_en}</span></div>
                            <div style="font-size:11px;color:#0f0;margin:5px 0;">Lv.${rw.level_req} | ${slots}</div>
                            <div style="font-size:10px;color:#f80;margin-bottom:5px;">${runeNames}</div>
                            <div style="font-size:10px;color:#0ff;">${rw.description || ''}</div>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `).join('');

    dialog.innerHTML = `
        <div style="position:relative;">
            <button onclick="this.closest('#runeword-compendium-dialog').remove()" style="position:absolute;top:-10px;right:-10px;width:30px;height:30px;border-radius:50%;background:#f44;border:2px solid #ffd700;color:#fff;font-weight:bold;cursor:pointer;font-size:16px;line-height:1;">×</button>
            <h3 style="color:#ffd700;margin-bottom:15px;">符文之语图鉴</h3>
            <div style="margin-bottom:15px;color:#888;font-size:12px;">
                提示：将符文按顺序镶嵌到有孔的白色装备中，可形成强大的符文之语装备！
            </div>
            ${tiersHtml || '<div style="color:#888;">暂无符文之语数据</div>'}
        </div>
    `;
    document.body.appendChild(dialog);
}

// 打开符文列表
function openRuneList() {
    ws.send(JSON.stringify({ type: 'get_runes' }));
    setTimeout(() => {
        showRuneListDialog();
    }, 300);
}

// 显示符文列表
function showRuneListDialog() {
    const dialog = document.createElement('div');
    dialog.id = 'rune-list-dialog';
    dialog.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#0f3460;border:2px solid #f80;padding:20px;border-radius:10px;width:90%;max-width:600px;max-height:80vh;overflow-y:auto;z-index:1001;';

    const runes = runesData || {};
    const runesList = Object.values(runes).sort((a, b) => a.rune_number - b.rune_number);

    dialog.innerHTML = `
        <h3 style="color:#f80;margin-bottom:15px;">符文列表 (${runesList.length}个)</h3>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;">
            ${runesList.map(r => `
                <div style="background:#1a1a2e;padding:8px;border-radius:5px;border:1px solid #f80;">
                    <div style="color:#f80;font-weight:bold;">#${r.rune_number} ${r.name}</div>
                    <div style="font-size:10px;color:#888;">${r.name_en} | Lv.${r.level_req}</div>
                </div>
            `).join('')}
        </div>
        <button onclick="this.parentElement.remove()" style="margin-top:15px;width:100%;">关闭</button>
    `;
    document.body.appendChild(dialog);
}

// 退出
function logout() {
    if (ws) ws.close();
    token = null;
    localStorage.removeItem('token');
    hide('game-screen'); hide('character-screen'); show('login-screen');
}

// 初始化
if (token) {
    showCharacterScreen().catch(() => {
        token = null;
        localStorage.removeItem('token');
    });
}