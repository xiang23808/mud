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
        <div>攻击(DC): ${total_stats.attack}</div>
        <div>魔法(MC): ${total_stats.magic}</div>
        <div>防御(AC): ${total_stats.defense}</div>
        <div>魔御(MAC): ${total_stats.magic_defense}</div>
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
    crit_rate: '暴击率', crit_damage: '暴击伤'
};

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
    
    // 左边：玩家HP/MP
    const playerDiv = document.createElement('div');
    playerDiv.style.cssText = 'flex:1;';
    playerDiv.innerHTML = `
        <div style="color:#0f0;font-weight:bold;margin-bottom:5px;">${currentChar.name}</div>
        <div style="margin-bottom:3px;">HP: <span id="player-hp">${playerHp}</span>/${playerMaxHp}</div>
        <div style="height:8px;background:#333;border-radius:4px;margin-bottom:5px;"><div id="player-hp-fill" style="height:100%;width:100%;background:#0f0;border-radius:4px;transition:width 0.3s;"></div></div>
        <div style="margin-bottom:3px;">MP: <span id="player-mp">${playerMp}</span>/${playerMaxMp}</div>
        <div style="height:8px;background:#333;border-radius:4px;"><div id="player-mp-fill" style="height:100%;width:100%;background:#00f;border-radius:4px;transition:width 0.3s;"></div></div>
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
            // 更新怪物血量（按索引匹配）
            const monsterParts = parts.slice(3).filter(p => p);
            for (const mp of monsterParts) {
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

function renderInventory(data) {
    const items = data.items || data;
    const storage_type = data.storage_type || 'inventory';
    currentStorageType = storage_type;
    const max_slots = storage_type === 'warehouse' ? 1000 : 200;
    const used_slots = items.length;
    const free_slots = max_slots - used_slots;
    
    const grid = $('inventory-grid');
    // 背包显示全部回收按钮，仓库不显示
    const recycleAllBtn = storage_type === 'inventory' && items.length > 0
        ? `<button onclick="recycleAll()" style="background:#c00;margin-left:10px;">全部回收</button>`
        : '';
    const organizeBtn = `<button onclick="organizeInventory('${storage_type}')" style="background:#060;margin-left:10px;">整理</button>`;
    grid.innerHTML = `<div style="grid-column: 1/-1; color: #ffd700; text-align: center; margin-bottom: 10px;">
        已使用: ${used_slots}/${max_slots} | 可用空间: ${free_slots} ${organizeBtn} ${recycleAllBtn}
    </div>` + items.map(item => {
        const isEquipable = item.info?.type === 'weapon' || item.info?.type === 'armor' || item.info?.type === 'accessory';
        const isSkillbook = item.info?.type === 'skillbook';
        const isBossSummon = item.info?.type === 'boss_summon';
        const info = item.info || {};
        const attrs = [];
        // 等级需求
        if (info.level_req && info.level_req > 1) attrs.push(`需Lv.${info.level_req}`);
        // 支持min-max格式
        if (info.attack_min || info.attack_max) attrs.push(`DC:${info.attack_min||0}-${info.attack_max||0}`);
        else if (info.attack) attrs.push(`DC:${info.attack}`);
        if (info.magic_min || info.magic_max) attrs.push(`MC:${info.magic_min||0}-${info.magic_max||0}`);
        else if (info.magic) attrs.push(`MC:${info.magic}`);
        if (info.defense_min || info.defense_max) attrs.push(`AC:${info.defense_min||0}-${info.defense_max||0}`);
        else if (info.defense) attrs.push(`AC:${info.defense}`);
        if (info.magic_defense_min || info.magic_defense_max) attrs.push(`MAC:${info.magic_defense_min||0}-${info.magic_defense_max||0}`);
        else if (info.magic_defense) attrs.push(`MAC:${info.magic_defense}`);
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
        return `
        <div class="inv-slot quality-${item.quality}">
            <div class="item-name">${setTag}${info.name || item.item_id}</div>
            ${attrs.length ? `<div style="font-size:10px;color:#8f8;">${attrs.join(' ')}</div>` : ''}
            ${effectsHtml ? `<div>${effectsHtml}</div>` : ''}
            <div>x${item.quantity}</div>
            <div class="item-actions">
                ${isEquipable && storage_type === 'inventory' ? `<button onclick="equipItem(${item.slot},'${info.slot || ''}')">装备</button>` : ''}
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
    if (confirm('确定回收背包中所有物品？此操作不可撤销！')) {
        ws.send(JSON.stringify({ type: 'recycle_all' }));
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
                    <span style="color:#ffd700;">${s.name}</span> <span style="color:#0f0;">(${s.count}/4件)</span>
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
                <div>攻击(DC): ${total_stats.attack}</div>
                <div>魔法(MC): ${total_stats.magic}</div>
                <div>防御(AC): ${total_stats.defense}</div>
                <div>魔御(MAC): ${total_stats.magic_defense}</div>
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
                return `
                    <div class="equip-slot ${item ? 'quality-' + item.quality : ''}"
                         style="background: #0f3460; padding: 12px; border-radius: 5px; min-height: 80px;">
                        <div style="color: #ffd700; font-weight: bold; margin-bottom: 5px;">${name}</div>
                        ${item ? `
                            <div style="font-size: 14px; margin-bottom: 3px;">${setTag}${item.info?.name || item.item_id}</div>
                            ${item.info?.level_req > 1 ? `<div style="font-size: 10px; color: #aaa;">需Lv.${item.info.level_req}</div>` : ''}
                            <div style="font-size: 10px; color: #8f8;">
                                ${item.info?.attack_min || item.info?.attack_max ? `DC:${item.info.attack_min||0}-${item.info.attack_max||0} ` : (item.info?.attack ? `DC:${item.info.attack} ` : '')}
                                ${item.info?.magic_min || item.info?.magic_max ? `MC:${item.info.magic_min||0}-${item.info.magic_max||0} ` : (item.info?.magic ? `MC:${item.info.magic} ` : '')}
                                ${item.info?.defense_min || item.info?.defense_max ? `AC:${item.info.defense_min||0}-${item.info.defense_max||0} ` : (item.info?.defense ? `AC:${item.info.defense} ` : '')}
                                ${item.info?.magic_defense_min || item.info?.magic_defense_max ? `MAC:${item.info.magic_defense_min||0}-${item.info.magic_defense_max||0} ` : (item.info?.magic_defense ? `MAC:${item.info.magic_defense} ` : '')}
                                ${item.info?.hp_bonus ? `HP+${item.info.hp_bonus} ` : ''}
                                ${item.info?.mp_bonus ? `MP+${item.info.mp_bonus}` : ''}
                            </div>
                            ${itemEffects ? `<div style="margin-top:3px;">${itemEffects}</div>` : ''}
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
        { id: 'hp_potion_medium', name: '中红瓶', price: 60, currency: 'gold', desc: '恢复150HP' },
        { id: 'hp_potion_large', name: '大红瓶', price: 200, currency: 'gold', desc: '恢复500HP' },
        { id: 'mp_potion_small', name: '小蓝瓶', price: 15, currency: 'gold', desc: '恢复30MP' },
        { id: 'mp_potion_medium', name: '中蓝瓶', price: 50, currency: 'gold', desc: '恢复100MP' },
        { id: 'mp_potion_large', name: '大蓝瓶', price: 150, currency: 'gold', desc: '恢复300MP' },
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