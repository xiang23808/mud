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
    }
}

// 地图渲染
const CELL_SIZE = 20;
const canvas = $('map-canvas');
const ctx = canvas.getContext('2d');

function renderMap() {
    if (!mapState) return;
    
    $('map-name').textContent = mapState.map_name || mapState.map_id;
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, 480, 480);
    
    const revealed = new Set(mapState.revealed.map(p => `${p[0]},${p[1]}`));
    
    for (let y = 0; y < 24; y++) {
        for (let x = 0; x < 24; x++) {
            const px = x * CELL_SIZE;
            const py = y * CELL_SIZE;
            
            if (!revealed.has(`${x},${y}`)) {
                ctx.fillStyle = '#222';
                ctx.fillRect(px, py, CELL_SIZE - 1, CELL_SIZE - 1);
                continue;
            }
            
            const isWall = mapState.maze[y][x] === 1;
            ctx.fillStyle = isWall ? '#444' : '#1a1a2e';
            ctx.fillRect(px, py, CELL_SIZE - 1, CELL_SIZE - 1);
            
            // 标记出入口（非主城地图）- 只在特定位置显示
            if (mapState.map_id !== 'main_city') {
                if ((x === 2 && y === 2) || (x === 21 && y === 21)) {
                    ctx.fillStyle = '#0ff';
                    ctx.fillRect(px + 5, py + 5, 10, 10);
                }
            }
        }
    }
    
    // 绘制入口 - 修复显示
    if (mapState.entrances) {
        for (const [id, entrance] of Object.entries(mapState.entrances)) {
            const [x, y] = entrance.position;
            if (revealed.has(`${x},${y}`)) {
                ctx.fillStyle = '#ff0';
                ctx.fillRect(x * CELL_SIZE + 5, y * CELL_SIZE + 5, 10, 10);
            }
        }
    }
    
    // 绘制NPC
    if (mapState.npcs) {
        for (const npc of mapState.npcs) {
            const [x, y] = npc.position;
            if (revealed.has(`${x},${y}`)) {
                ctx.fillStyle = '#00f';
                ctx.beginPath();
                ctx.arc(x * CELL_SIZE + 10, y * CELL_SIZE + 10, 6, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }
    
    // 怪物
    for (const [pos, monster] of Object.entries(mapState.monsters || {})) {
        const [x, y] = pos.split(',').map(Number);
        const px = x * CELL_SIZE;
        const py = y * CELL_SIZE;
        ctx.fillStyle = monster.is_boss ? '#ff0' : '#f00';
        ctx.beginPath();
        ctx.arc(px + 10, py + 10, 6, 0, Math.PI * 2);
        ctx.fill();
    }
    
    // 玩家
    if (mapState.position) {
        const [x, y] = mapState.position;
        ctx.fillStyle = '#0f0';
        ctx.beginPath();
        ctx.arc(x * CELL_SIZE + 10, y * CELL_SIZE + 10, 8, 0, Math.PI * 2);
        ctx.fill();
    }
    
    // 更新右侧信息面板
    updateMapInfo();
}

// 更新角色属性面板
function updateCharStats() {
    if (!currentChar) return;
    const el = $('char-stats-info');
    if (!el) return;
    el.innerHTML = `
        <div>等级: ${currentChar.level}</div>
        <div>HP: ${currentChar.hp}/${currentChar.max_hp}</div>
        <div>MP: ${currentChar.mp}/${currentChar.max_mp}</div>
        <div>攻击(DC): ${currentChar.attack}</div>
        <div>魔法(MC): ${currentChar.magic || 0}</div>
        <div>防御(AC): ${currentChar.defense}</div>
        <div>魔御(MAC): ${currentChar.magic_defense || 0}</div>
        <div>幸运: ${currentChar.luck}</div>
    `;
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
    const x = Math.floor((e.clientX - rect.left) / CELL_SIZE);
    const y = Math.floor((e.clientY - rect.top) / CELL_SIZE);
    
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
    
    // 检查是否点击怪物
    const monsterKey = `${x},${y}`;
    if (mapState.monsters && mapState.monsters[monsterKey]) {
        ws.send(JSON.stringify({ type: 'attack', pos: [x, y] }));
        return;
    }
    
    // 检查是否点击NPC（只在已揭示区域）
    if (mapState.npcs && revealed.has(`${x},${y}`)) {
        for (const npc of mapState.npcs) {
            if (npc.position[0] === x && npc.position[1] === y) {
                handleNPCClick(npc);
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

// 战斗显示
function showCombat(data) {
    show('combat-modal');
    const log = $('combat-log');
    log.innerHTML = '';
    $('combat-close').classList.add('hidden');
    
    // 解析血量信息
    let playerHp = currentChar.max_hp, playerMaxHp = currentChar.max_hp;
    let monsterHp = 0, monsterMaxHp = 0, monsterName = '怪物';
    
    // 从第一条日志解析初始血量
    if (data.logs.length > 1) {
        const initLog = data.logs[1];
        const match = initLog.match(/你的HP: (\d+)\/(\d+).*?(\S+)的HP: (\d+)/);
        if (match) {
            playerHp = parseInt(match[1]);
            playerMaxHp = parseInt(match[2]);
            monsterName = match[3];
            monsterHp = monsterMaxHp = parseInt(match[4]);
        }
    }
    
    // 血量条
    const hpBar = document.createElement('div');
    hpBar.id = 'combat-hp-bar';
    hpBar.style.cssText = 'margin-bottom:10px;padding:10px;background:#1a1a2e;border-radius:5px;';
    hpBar.innerHTML = `
        <div style="margin-bottom:5px;"><span style="color:#0f0;">你</span>: <span id="player-hp">${playerHp}</span>/${playerMaxHp}</div>
        <div style="height:8px;background:#333;border-radius:4px;margin-bottom:8px;"><div id="player-hp-fill" style="height:100%;width:100%;background:#0f0;border-radius:4px;transition:width 0.3s;"></div></div>
        <div style="margin-bottom:5px;"><span style="color:#f00;">${monsterName}</span>: <span id="monster-hp">${monsterHp}</span>/${monsterMaxHp}</div>
        <div style="height:8px;background:#333;border-radius:4px;"><div id="monster-hp-fill" style="height:100%;width:100%;background:#f00;border-radius:4px;transition:width 0.3s;"></div></div>
    `;
    log.appendChild(hpBar);
    
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
        
        // 更新血量显示
        const hpMatch = line.match(/你的HP: (\d+).*?的HP: (\d+)/);
        if (hpMatch) {
            playerHp = parseInt(hpMatch[1]);
            monsterHp = parseInt(hpMatch[2]);
            $('player-hp').textContent = Math.max(0, playerHp);
            $('monster-hp').textContent = Math.max(0, monsterHp);
            $('player-hp-fill').style.width = Math.max(0, (playerHp / playerMaxHp) * 100) + '%';
            $('monster-hp-fill').style.width = Math.max(0, (monsterHp / monsterMaxHp) * 100) + '%';
        }
        
        const div = document.createElement('div');
        if (line.includes('回合')) div.className = 'round';
        else if (line.includes('伤害')) div.className = 'damage';
        else if (line.includes('胜利')) div.className = 'victory';
        else if (line.includes('失败')) div.className = 'defeat';
        div.textContent = line;
        log.appendChild(div);
        log.scrollTop = log.scrollHeight;
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
    grid.innerHTML = `<div style="grid-column: 1/-1; color: #ffd700; text-align: center; margin-bottom: 10px;">
        已使用: ${used_slots}/${max_slots} | 可用空间: ${free_slots} ${recycleAllBtn}
    </div>` + items.map(item => {
        const isEquipable = item.info?.type === 'weapon' || item.info?.type === 'armor' || item.info?.type === 'accessory';
        const isSkillbook = item.info?.type === 'skillbook';
        const info = item.info || {};
        const attrs = [];
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
        const moveBtn = storage_type === 'inventory'
            ? `<button onclick="moveToWarehouse(${item.slot})">存仓</button>`
            : `<button onclick="moveToInventory(${item.slot})">取出</button>`;
        // 仓库不显示回收按钮
        const recycleBtn = storage_type === 'inventory' ? `<button onclick="recycleItem(${item.slot})">回收</button>` : '';
        return `
        <div class="inv-slot quality-${item.quality}">
            <div class="item-name">${info.name || item.item_id}</div>
            ${attrs.length ? `<div style="font-size:10px;color:#8f8;">${attrs.join(' ')}</div>` : ''}
            <div>x${item.quantity}</div>
            <div class="item-actions">
                ${isEquipable && storage_type === 'inventory' ? `<button onclick="equipItem(${item.slot},'${info.slot || ''}')">装备</button>` : ''}
                ${isSkillbook && storage_type === 'inventory' ? `<button onclick="useSkillbook(${item.slot})">学习</button>` : ''}
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

function moveToWarehouse(slot) {
    ws.send(JSON.stringify({ type: 'move_to_warehouse', slot }));
    setTimeout(() => ws.send(JSON.stringify({ type: 'get_inventory', storage: 'inventory' })), 300);
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
    const { equipment, total_stats } = data;
    
    // 显示综合属性
    const statsHtml = `
        <div style="background: #0f3460; padding: 15px; margin-bottom: 15px; border-radius: 5px;">
            <h4 style="color: #ffd700; margin-bottom: 10px;">综合属性</h4>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; color: #0f0;">
                <div>等级: ${total_stats.level}</div>
                <div>幸运: ${total_stats.luck}</div>
                <div>生命: ${total_stats.hp}</div>
                <div>魔法值: ${total_stats.mp}</div>
                <div>攻击(DC): ${total_stats.attack}</div>
                <div>魔法(MC): ${total_stats.magic}</div>
                <div>防御(AC): ${total_stats.defense}</div>
                <div>魔御(MAC): ${total_stats.magic_defense}</div>
            </div>
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
                return `
                    <div class="equip-slot ${item ? 'quality-' + item.quality : ''}"
                         style="background: #0f3460; padding: 12px; border-radius: 5px; min-height: 80px;">
                        <div style="color: #ffd700; font-weight: bold; margin-bottom: 5px;">${name}</div>
                        ${item ? `
                            <div style="font-size: 14px; margin-bottom: 3px;">${item.info?.name || item.item_id}</div>
                            <div style="font-size: 10px; color: #8f8;">
                                ${item.info?.attack_min || item.info?.attack_max ? `DC:${item.info.attack_min||0}-${item.info.attack_max||0} ` : (item.info?.attack ? `DC:${item.info.attack} ` : '')}
                                ${item.info?.magic_min || item.info?.magic_max ? `MC:${item.info.magic_min||0}-${item.info.magic_max||0} ` : (item.info?.magic ? `MC:${item.info.magic} ` : '')}
                                ${item.info?.defense_min || item.info?.defense_max ? `AC:${item.info.defense_min||0}-${item.info.defense_max||0} ` : (item.info?.defense ? `AC:${item.info.defense} ` : '')}
                                ${item.info?.magic_defense_min || item.info?.magic_defense_max ? `MAC:${item.info.magic_defense_min||0}-${item.info.magic_defense_max||0} ` : (item.info?.magic_defense ? `MAC:${item.info.magic_defense} ` : '')}
                                ${item.info?.hp_bonus ? `HP+${item.info.hp_bonus} ` : ''}
                                ${item.info?.mp_bonus ? `MP+${item.info.mp_bonus}` : ''}
                            </div>
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
    const skillData = await api(`/api/skills/${currentChar.id}`);
    const list = $('skills-list');
    
    // 已学习技能
    const learnedHtml = skillData.learned.length > 0 ? `
        <div class="skills-section">
            <h3>已学习技能 (${skillData.learned.length})</h3>
            ${skillData.learned.map(skill => `
                <div class="skill-item learned">
                    <div class="skill-info">
                        <div class="skill-name">✓ ${skill.info?.name || skill.skill_id}</div>
                        <div class="skill-desc">${skill.info?.description || ''}</div>
                        <div class="skill-level">等级: ${skill.level}/3 | 熟练度: ${skill.proficiency}/1000</div>
                    </div>
                </div>
            `).join('')}
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

// 回城
function returnToCity() {
    ws.send(JSON.stringify({ type: 'return_city' }));
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
    const el = $('output');
    el.innerHTML += `<div>${msg}</div>`;
    el.scrollTop = el.scrollHeight;
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