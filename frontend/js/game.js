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
    $('char-info').textContent = `${currentChar.name} | ${classNames[currentChar.char_class]} | Lv.${currentChar.level} | HP:${currentChar.hp}/${currentChar.max_hp} | MP:${currentChar.mp}/${currentChar.max_mp} | 金币:${currentChar.gold} | 元宝:${currentChar.yuanbao}`;
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
            renderMap();
            output('欢迎来到传奇世界！');
            break;
        case 'map_state':
            mapState = msg.data;
            renderMap();
            break;
        case 'map_change':
            mapState = msg.data.state;
            renderMap();
            output(`进入地图: ${msg.data.map_id}`);
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
        case 'chat':
            output(`[${msg.name}] ${msg.message}`);
            break;
        case 'equip_result':
        case 'recycle_result':
        case 'learn_result':
            if (msg.data.success) output('[成功]');
            else output(`[失败] ${msg.data.error}`);
            break;
    }
}

// 地图渲染
const CELL_SIZE = 20;
const canvas = $('map-canvas');
const ctx = canvas.getContext('2d');

function renderMap() {
    if (!mapState) return;
    
    $('map-name').textContent = mapState.map_id;
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
            
            // 标记出入口
            if (x === 1 && y === 0) {
                ctx.fillStyle = '#0ff';
                ctx.fillRect(px + 5, py + 5, 10, 10);
            }
            if (x === 22 && y === 23) {
                ctx.fillStyle = '#0ff';
                ctx.fillRect(px + 5, py + 5, 10, 10);
            }
        }
    }
    
    // 绘制入口
    if (mapState.entrances) {
        for (const [id, entrance] of Object.entries(mapState.entrances)) {
            const [x, y] = entrance.position;
            ctx.fillStyle = '#ff0';
            ctx.fillRect(x * CELL_SIZE + 5, y * CELL_SIZE + 5, 10, 10);
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
}

// 地图点击
canvas.onclick = e => {
    if (!mapState) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / CELL_SIZE);
    const y = Math.floor((e.clientY - rect.top) / CELL_SIZE);
    
    // 检查是否点击怪物
    const monsterKey = `${x},${y}`;
    if (mapState.monsters && mapState.monsters[monsterKey]) {
        ws.send(JSON.stringify({ type: 'attack', pos: [x, y] }));
        return;
    }
    
    // 检查是否点击入口
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
    
    // 检查是否点击出口
    if ((x === 1 && y === 0) || (x === 22 && y === 23)) {
        const exitType = (x === 1 && y === 0) ? 'entrance' : 'exit';
        if (mapState.position[0] === x && mapState.position[1] === y) {
            ws.send(JSON.stringify({ type: 'use_exit', exit_type: exitType }));
            return;
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
    
    let i = 0;
    const interval = setInterval(() => {
        if (i >= data.logs.length) {
            clearInterval(interval);
            $('combat-close').classList.remove('hidden');
            if (data.victory) {
                currentChar = data.character;
                updateCharInfo();
            }
            return;
        }
        const line = data.logs[i];
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

function renderInventory(items) {
    const grid = $('inventory-grid');
    grid.innerHTML = items.map(item => `
        <div class="inv-slot quality-${item.quality}">
            <div class="item-name">${item.info?.name || item.item_id}</div>
            <div>x${item.quantity}</div>
            <div class="item-actions">
                ${item.info?.type === 'weapon' || item.info?.type === 'armor' ? 
                    `<button onclick="equipItem(${item.slot})">装备</button>` : ''}
                <button onclick="recycleItem(${item.slot})">回收</button>
            </div>
        </div>
    `).join('');
}

function equipItem(slot) {
    ws.send(JSON.stringify({ type: 'equip', slot }));
    setTimeout(() => ws.send(JSON.stringify({ type: 'get_inventory', storage: 'inventory' })), 500);
}

function recycleItem(slot) {
    if (confirm('确定回收此物品？')) {
        ws.send(JSON.stringify({ type: 'recycle', slot }));
        setTimeout(() => ws.send(JSON.stringify({ type: 'get_inventory', storage: 'inventory' })), 500);
    }
}

// 技能
async function openSkills() {
    show('skills-modal');
    const skillData = await api(`/api/skills/${currentChar.id}`);
    const list = $('skills-list');
    
    // 已学习技能
    const learnedHtml = skillData.learned.length > 0 ? `
        <div class="skills-section">
            <h3>已学习技能</h3>
            ${skillData.learned.map(skill => `
                <div class="skill-item learned">
                    <div class="skill-info">
                        <div class="skill-name">✓ ${skill.info.name}</div>
                        <div class="skill-desc">${skill.info.description}</div>
                        <div class="skill-level">等级: ${skill.level}/3 | 熟练度: ${skill.proficiency}/1000</div>
                    </div>
                </div>
            `).join('')}
        </div>
    ` : '';
    
    // 可学习技能
    const availableHtml = `
        <div class="skills-section">
            <h3>可学习技能</h3>
            ${skillData.available.map(skill => {
                if (skill.learned) return '';
                const canLearn = skill.can_learn;
                const buttonText = canLearn ?
                    (skill.info.buy_price > 0 ? `学习 (${skill.info.buy_price}金币)` : '学习') :
                    `等级不足(需要Lv.${skill.info.level_req})`;
                return `
                    <div class="skill-item ${canLearn ? '' : 'disabled'}">
                        <div class="skill-info">
                            <div class="skill-name">${skill.info.name}</div>
                            <div class="skill-desc">${skill.info.description} (需要等级:${skill.info.level_req})</div>
                        </div>
                        <button onclick="learnSkill('${skill.skill_id}')" ${canLearn ? '' : 'disabled'}>${buttonText}</button>
                    </div>
                `;
            }).join('')}
        </div>
    `;
    
    list.innerHTML = learnedHtml + availableHtml;
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
        input.value = '';
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