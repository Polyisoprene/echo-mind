'use strict';

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

const state = {
  view: 'overview',
  chatKey: '',
  snapshot: null,
  sessions: [],
  timer: null,
  traces: [],
  traceByChat: {},
  turns: [],
  openSkillCfgs: new Set(),
  sessionMode: 'turns',
  selectedTurnId: '',
  turnJsonMode: false,
  personaLoaded: false,
  theme: 'dark',
  lastTurnDetailFp: '',
  lastTurnListFp: '',
  turnOpenMap: new Map(),
  lastStreamFp: '',
  openStreamTraces: new Set(),
  llmProviders: [],
  llmFallbacks: [],
};

function applyTheme(theme) {
  const next = theme === 'light' ? 'light' : 'dark';
  state.theme = next;
  document.documentElement.setAttribute('data-theme', next);
  try { localStorage.setItem('echomind_theme', next); } catch (e) { /* ignore */ }
  const btn = $('btn-theme');
  if (btn) btn.textContent = next === 'light' ? '🌙 夜间' : '☀️ 白天';
}

function initTheme() {
  let saved = 'dark';
  try { saved = localStorage.getItem('echomind_theme') || 'dark'; } catch (e) { /* ignore */ }
  applyTheme(saved);
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(path + ' -> HTTP ' + res.status);
  return res.json();
}

let toastTimer = null;
function toast(msg, isErr) {
  const el = $('toast');
  el.textContent = msg;
  el.className = 'toast show' + (isErr ? ' err' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = 'toast'; }, 2600);
}

function fmtTime(ts) {
  if (!ts) return '-';
  const d = new Date(ts);
  const p = (n) => String(n).padStart(2, '0');
  return p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
}

function setBar(barId, valElId, value, max) {
  const bar = $(barId); const val = $(valElId);
  if (val) val.textContent = (Math.round(value * 10) / 10).toFixed(1);
  if (bar) { const i = bar.querySelector('i'); if (i) i.style.width = Math.max(0, Math.min(100, (value / max) * 100)) + '%'; }
}

function setPlainBar(barId, value, max) {
  const bar = $(barId);
  if (bar) { const i = bar.querySelector('i'); if (i) i.style.width = Math.max(0, Math.min(100, (value / max) * 100)) + '%'; }
}

const PERSONA_DIMS = [
  ['persona_warmth', '温柔粘人', 'accent'],
  ['persona_tsundere', '傲娇嘴硬', 'warn'],
  ['persona_playfulness', '古灵精怪', 'pink'],
  ['persona_possessiveness', '独占护食', 'danger'],
  ['persona_confidence', '社交自信', 'ok'],
  ['persona_guile', '狡黠小机灵', 'accent'],
  ['persona_defiance', '叛逆小刺头', 'danger'],
];

function renderPersonaBars(params) {
  const host = $('persona-bars');
  if (!host) return;
  host.innerHTML = PERSONA_DIMS.map(([key, label, cls]) => {
    const p = params[key] || { value: 0, min_bound: 0, max_bound: 100 };
    const pct = ((p.value - p.min_bound) / (p.max_bound - p.min_bound || 1)) * 100;
    return '<div class="row"><span class="lbl">' + label + '</span><span class="val">' + p.value.toFixed(1) + '</span></div>' +
      '<div class="bar ' + cls + '" style="margin:2px 0 8px"><i style="width:' + Math.max(0, Math.min(100, pct)) + '%"></i></div>';
  }).join('');
}

function renderOverview(s) {
  const w = s.working || {}; const a = w.affect || {}; const d = w.drives || {};
  setBar('b-valence', 'm-valence', a.valence ?? 0, 100);
  setBar('b-energy', 'm-energy', a.energy ?? 0, 100);
  setBar('b-jealousy', 'm-jealousy', a.jealousy ?? 0, 100);
  setBar('b-shyness', 'm-shyness', a.shyness ?? 0, 100);
  setBar('b-irritation', 'm-irritation', a.irritation ?? 0, 100);

  $('d-curiosity').textContent = (d.curiosity ?? 0).toFixed(1);
  $('d-attachment').textContent = (d.attachment ?? 0).toFixed(1);
  $('d-jealousy').textContent = (d.jealousy_drive ?? 0).toFixed(1);
  $('d-social').textContent = (d.social_expression ?? 0).toFixed(1);
  setPlainBar('db-curiosity', d.curiosity ?? 0, 100);
  setPlainBar('db-attachment', d.attachment ?? 0, 100);
  setPlainBar('db-jealousy', d.jealousy_drive ?? 0, 100);
  setPlainBar('db-social', d.social_expression ?? 0, 100);

  $('w-activity').textContent = w.current_activity || '日常待机';
  $('w-thought').textContent = w.inner_thought || '（安静中）';
  const intents = (w.intentions || []).map((x) => x.summary || x).join(' · ') || '（无）';
  $('w-intentions').textContent = intents;
  $('w-curiosity').textContent = (w.curiosity_queue || []).join(' · ') || '（无）';

  const wakeBanner = $('overview-wake-banner');
  const gateHost = $('overview-gate-radar');
  if (wakeBanner) {
    const ws = s.wake_state || {};
    const stCls = ws.status === 'asleep' ? 'warn' : (ws.status === 'drowsy' ? 'accent' : 'ok');
    const lastSeen = ws.last_msg_ts ? fmtTime(ws.last_msg_ts) : '尚无';
    wakeBanner.innerHTML =
      '<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:8px 12px;background:var(--panel-2);border:1px solid var(--border);border-radius:8px">' +
      '<span>生理觉醒状态：<span class="badge ' + stCls + '" style="font-size:12.5px">' + esc(ws.badge || '🟢 清醒活跃') + '</span></span>' +
      '<span class="lbl">最近收到消息时间：<b>' + esc(lastSeen) + '</b></span>' +
      '<span class="lbl">正在做：<b>' + esc(w.current_activity || '日常待机') + '</b></span>' +
      '</div>';
  }
  if (gateHost) {
    const radar = s.gate_radar || [];
    const formatGateBadge = (g) => {
      if (g.should_wake) return '<span class="badge ok">🟢 已唤醒回应 (Tier ' + g.tier + ')</span>';
      const r = String(g.reason || '');
      if (r.includes('冷却')) return '<span class="badge warn">⏳ 收到·冷却期未插话</span>';
      if (r.includes('其他群友')) return '<span class="badge muted">🔇 收到·非对我说话</span>';
      if (r.includes('冷暴力')) return '<span class="badge danger">💢 收到·冷暴力已读不回</span>';
      if (r.includes('犯困')) return '<span class="badge warn">💤 收到·犯困休息不插话</span>';
      return '<span class="badge muted">⚪ 收到·不感兴趣(未达阈值)</span>';
    };
    gateHost.innerHTML = radar.length
      ? '<table><tr><th>收到时间</th><th>来源会话</th><th>发言人</th><th>收到的消息内容</th><th>门控状态</th><th>判定依据与显著度</th></tr>' +
        radar.map((g) =>
          '<tr><td style="white-space:nowrap">' + fmtTime(g.ts) + '</td>' +
          '<td style="white-space:nowrap">' + esc((g.chat_key || '').replace('group:', '群 ').replace('private:', '私聊 ')) + '</td>' +
          '<td><b>' + esc(g.sender_name || g.sender_id || '-') + '</b></td>' +
          '<td style="font-size:12px">' + esc(g.text || '') + '</td>' +
          '<td style="white-space:nowrap">' + formatGateBadge(g) + '</td>' +
          '<td style="font-size:12px;color:var(--muted)">' + esc(g.reason || '-') + ' (显著度 ' + (g.salience ?? 0) + ')</td></tr>'
        ).join('') + '</table>'
      : '<div class="empty">服务重启后暂未收到新消息（当群里或私聊有人说话时，这里会实时显示她是否收到、是否感兴趣及为什么回/不回）</div>';
  }

  const cybHost = $('overview-cyber-core');
  if (cybHost) {
    const cy = s.cybernetic_core || {};
    const stance = Number(cy.stance_order ?? 0.2);
    const epist = Number(cy.epistemic_order ?? 0.3);
    const modal = Number(cy.modality_order ?? 0.2);
    const reagents = (cy.active_reagents || ['日常轻装剂']).map((r) => '<span class="badge accent">🧪 ' + esc(r) + '</span>').join(' ');
    const tools = (cy.selected_tools || []).map((t) => '<code class="badge muted" style="font-family:var(--mono)">' + esc(t) + '</code>').join(' ');
    cybHost.innerHTML =
      '<div class="row"><span class="lbl">当前自组织核心磁极态 (Regime)</span>' +
      '<span class="val"><span class="badge ok">' + esc(cy.core_regime || '🌿 日常熟稔接梗态') + '</span>' +
      ' · 役使推荐温度 <b>T=' + (cy.recommended_temperature ?? 0.65) + '</b></span></div>' +
      '<div class="row"><span class="lbl">🧭 主磁针 1 · 社交姿态序参量 (ξ_stance ∈ [-1,+1])</span><span class="val"><b>' + (stance >= 0 ? '+' : '') + stance.toFixed(2) + '</b>（负=防御刺头 ↔ 正=亲昵护短）</span></div>' +
      '<div class="row"><span class="lbl">🧭 主磁针 2 · 认知求真序参量 (ξ_epistemic ∈ [0,1])</span><span class="val"><b>' + epist.toFixed(2) + '</b>（0=直觉快答 ↔ 1=严谨调工具考据）</span></div>' +
      '<div class="row"><span class="lbl">🧭 主磁针 3 · 声情模态序参量 (ξ_modality ∈ [0,1])</span><span class="val"><b>' + modal.toFixed(2) + '</b>（高唤醒自动倾向真语音/唱歌）</span></div>' +
      '<div class="row"><span class="lbl">🔬 激活选矿剂 (Stage-1 Reagents)</span><span class="val">' + reagents + '</span></div>' +
      '<div class="row"><span class="lbl">🛠️ 浮选挂载工具集 (Stage-2 Tools)</span><span class="val">' + (tools || '-') + '</span></div>';
  }

  const expHost = $('overview-exp-logs');
  if (expHost) {
    const expLogs = s.exploration_logs || [];
    const kindLabels = {
      curiosity_explore: '🔍 网页/梗百科求知',
      bili_surf: '📺 刷B站热门榜',
      jealousy_poke: '💢 吃醋冒泡',
      cold_group_topic: '💬 冷场找话题',
      attachment_private: '💌 思念私聊',
    };
    expHost.innerHTML = expLogs.length
      ? '<table><tr><th>时间</th><th>行为类型</th><th>探索主题</th><th>搜到的内容 / 刷到的B站视频摘要</th></tr>' +
        expLogs.map((e) =>
          '<tr><td style="white-space:nowrap">' + fmtTime(e.ts) + '</td>' +
          '<td><span class="badge accent">' + esc(kindLabels[e.kind] || e.kind) + '</span></td>' +
          '<td><b>' + esc(e.topic || '-') + '</b></td>' +
          '<td style="white-space:pre-wrap;font-size:12px">' + esc(e.summary || '-') + '</td></tr>'
        ).join('') + '</table>'
      : '<div class="empty">暂无自主冲浪记录（可点击上方「🔭 立即去刷B站 / 探索未知新梗」触发一次）</div>';
  }

  renderPersonaBars(s.plastic_params || {});

  const facts = s.facts || [];
  $('overview-facts').innerHTML = facts.length
    ? facts.map((f) => '<div class="row"><span class="lbl">' + esc(f.subject) + '</span>' +
        '<span class="val">' + esc(f.fact_text) + ' ' +
        (f.is_locked ? '<span class="badge ok">锁定</span>' : '<span class="badge muted">' + Math.round(f.confidence * 100) + '%</span>') +
        '</span></div>').join('')
    : '<div class="empty">暂无语义事实</div>';
}

function extractSentList(turn) {
  const out = [];
  (turn.steps || []).forEach((s) => {
    if (s.kind !== 'tool') return;
    if ((s.name || '').indexOf('send_message') === 0) {
      try {
        const d = JSON.parse(s.detail || '{}');
        (d.messages || []).forEach((m) => out.push(m));
      } catch (e) {
        if (s.detail) out.push(s.detail);
      }
    } else if (s.name === 'send_sticker') {
      out.push('[发送表情包] ' + (s.detail || ''));
    } else if (s.name === 'feiyu_say') {
      out.push('[发送语音] ' + (s.detail || ''));
    } else if (s.name === 'feiyu_cover') {
      out.push('[全曲AI翻唱] ' + (s.detail || ''));
    }
  });
  return out;
}

function summarizeTurnTokens(turn) {
  let calls = 0; let prompt = 0; let completion = 0; let cached = 0;
  (turn.steps || []).forEach((s) => {
    if (s.kind !== 'llm') return;
    calls += 1;
    const m = String(s.detail || '').match(/(\d+)\s*→\s*(\d+)\s*tok(?:（缓存\s*(\d+)）)?/);
    if (m) {
      prompt += Number(m[1] || 0);
      completion += Number(m[2] || 0);
      cached += Number(m[3] || 0);
    }
  });
  return { calls, prompt, completion, cached, total: prompt + completion };
}

function resolveContextInfo(turn) {
  const rawCtx = Number(turn.context_count ?? 0);
  const rawTrig = Math.max(1, Number(turn.trigger_count || 1));
  if (rawCtx > 0) return { count: rawCtx, trig: rawTrig, known: true };
  const up = String(turn.user_prompt || '');
  if (up.includes('（暂无早期历史）')) return { count: 0, trig: rawTrig, known: true };
  if (up.includes('【已读上下文】')) {
    const sec = up.split('【已读上下文】')[1]?.split('【🧠')[0] || '';
    const lines = sec.split('\n').map((x) => x.trim()).filter((x) => x.startsWith('[#'));
    return { count: lines.length, trig: rawTrig, known: true };
  }
  return { count: 0, trig: rawTrig, known: false };
}

function renderTurnSessionDetail(turn, opts) {
  const force = Boolean(opts && opts.force);
  const host = $('session-detail');
  if (!host) return;
  if (!turn) {
    state.lastTurnDetailFp = '';
    host.innerHTML = '<div class="empty">← 选择左侧会话查看完整执行过程</div>';
    return;
  }
  const fp = [
    turn.turn_id,
    turn.status,
    turn.rounds,
    (turn.steps || []).length,
    turn.sent_count,
    turn.total_ms,
    turn.context_count || 0,
    (turn.system_prompt || '').length,
    (turn.user_prompt || '').length,
    state.turnJsonMode ? 'json' : 'ui',
  ].join('|');
  if (!force && state.lastTurnDetailFp === fp) {
    return;
  }

  // Snapshot current open state of any rendered <details data-coll-key> before re-render
  host.querySelectorAll('details.collapsible[data-coll-key]').forEach((d) => {
    state.turnOpenMap.set(d.dataset.collKey, d.open);
  });
  const keepScroll = host.scrollTop;
  state.lastTurnDetailFp = fp;

  const chatName = (turn.chat_key || state.chatKey || 'group:10002002').replace('group:', '群 ').replace('private:', '私聊 ');
  const sentList = extractSentList(turn);
  const tok = summarizeTurnTokens(turn);
  const ctx = resolveContextInfo(turn);
  const ctxDesc = ctx.known
    ? ('携带 <b>' + ctx.count + '</b> 条历史上下文 + <b>' + ctx.trig + '</b> 条触发消息' +
        (ctx.count <= 1 ? ' <span class="badge warn" title="历史上下文极少，模型短期对话记忆受限">上下文偏少</span>' : ' <span class="badge ok">记忆充足</span>'))
    : ('<span class="badge muted">旧版轨迹（未记录上下文条数）</span>');
  const tokDesc = tok.total > 0
    ? ('<b>' + tok.prompt + '</b> 入 / <b>' + tok.completion + '</b> 出 / <b>' + tok.total + '</b> 总' +
        (tok.cached > 0 ? '（缓存命中 <b>' + tok.cached + '</b>）' : ''))
    : '-';

  const isRunning = turn.status === 'running';
  const statusBadge = isRunning
    ? '<span class="badge accent">⚡ 运行中…</span>'
    : (turn.status === 'error' ? '<span class="badge danger">异常</span>' : '<span class="badge ok">完成</span>');
  const head = '<div class="detail-header">' +
    '<h2>' + esc(chatName) + ' ' + statusBadge +
    '<button class="btn sm" id="btn-json-mode" style="margin-left:8px">' + (state.turnJsonMode ? 'UI 模式' : 'JSON 模式') + '</button></h2>' +
    '<div class="sub">' +
    '<span>触发：<b>' + esc(turn.trigger || '(系统触发)') + '</b></span>' +
    '<span>时间：' + fmtTime(turn.ts) + '</span>' +
    '<span>模型：<b>' + esc(turn.model || '-') + '</b></span>' +
    '<span>上下文：' + ctxDesc + '</span>' +
    '<span>Token：' + tokDesc + '</span>' +
    '<span>' + turn.rounds + ' 轮推理</span>' +
    '<span>已发送 ' + turn.sent_count + ' 条</span>' +
    '<span>总耗时 ' + turn.total_ms + ' ms</span>' +
    '</div></div>';

  const isOpen = (key, defaultOpen) => {
    const scopedKey = turn.turn_id + '::' + key;
    if (state.turnOpenMap.has(scopedKey)) return state.turnOpenMap.get(scopedKey) ? ' open' : '';
    return defaultOpen ? ' open' : '';
  };

  if (state.turnJsonMode) {
    host.innerHTML = head +
      '<details class="collapsible" data-coll-key="' + esc(turn.turn_id + '::json') + '" open>' +
      '<summary>JSON 模式（模型输入/工具调用/输出的完整原始结构）</summary>' +
      '<div class="coll-body" style="max-height:none">' + esc(JSON.stringify(turn, null, 2)) + '</div></details>';
  } else {
    const directive = (state.snapshot && state.snapshot.persona_directive) || '';
    const sysText = turn.system_prompt || ('（历史旧记录未保存 SystemPrompt 快照；当前基础人设预览）\n' + directive);
    const usrText = turn.user_prompt || ('【触发消息】\n' + (turn.trigger || '-') + (directive ? '\n\n' + directive : ''));
    const sysCard = '<details class="collapsible" data-coll-key="' + esc(turn.turn_id + '::sys-prompt') + '"' + isOpen('sys-prompt', false) + '>' +
      '<summary><span class="tool-ico">📜</span><span class="tool-name-flow">系统提示（System Prompt）</span>' +
      '<span class="tool-label">' + sysText.length + ' 字符 —— 基础人设卡 + 情绪轮换表情池 + 发言工具纪律</span></summary>' +
      '<div class="coll-body">' + esc(sysText) + '</div></details>';

    const usrCtxHint = ctx.known
      ? ('携带 ' + ctx.count + ' 条已读聊天上下文 + 12层认知状态帧 + 7维性格量表解释 + ' + ctx.trig + ' 条触发消息')
      : '点击展开查看本轮认知状态与触发输入';
    const usrCard = '<details class="collapsible" data-coll-key="' + esc(turn.turn_id + '::user-prompt') + '"' + isOpen('user-prompt', false) + '>' +
      '<summary><span class="tool-ico">🧠</span><span class="tool-name-flow">本次输入与认知帧（User Prompt）</span>' +
      '<span class="tool-label">' + usrText.length + ' 字符 —— ' + esc(usrCtxHint) + '</span></summary>' +
      '<div class="coll-body">' + esc(usrText) + '</div></details>';

    let llmRound = 0;
    const stepCards = (turn.steps || []).map((s, idx) => {
      const stepKey = 'step-' + (s.seq || idx);
      if (s.kind === 'llm') {
        llmRound += 1;
        return '<details class="collapsible think-flow" data-coll-key="' + esc(turn.turn_id + '::' + stepKey) + '"' + isOpen(stepKey, true) + '>' +
          '<summary><span class="tool-ico">💭</span>' +
          '<span class="tool-name-flow">LLM 推理（第 ' + llmRound + ' 轮）</span>' +
          '<span class="badge accent">' + esc(s.name || turn.model || '-') + '</span>' +
          '<span class="tool-label">' + esc(s.detail || '') + '</span>' +
          '<span style="margin-left:auto;color:var(--warn);font-size:11.5px">' + (s.elapsed_ms || 0) + ' ms</span></summary>' +
          '<div class="coll-body">' + esc(s.output || '（发起工具调用，无直接文本输出）') + '</div></details>';
      }
      const label = (typeof SKILL_LABELS === 'object' && SKILL_LABELS[s.name]) || s.name;
      const isErr = String(s.output || '').includes('执行失败') || String(s.output || '').includes('未找到工具');
      return '<details class="collapsible tool-flow" data-coll-key="' + esc(turn.turn_id + '::' + stepKey) + '"' + isOpen(stepKey, true) + '>' +
        '<summary><span class="tool-ico">⚒</span>' +
        '<span class="tool-name-flow">' + esc(s.name || '-') + '</span>' +
        '<span class="tool-label">' + esc(label) + '</span>' +
        (isErr ? '<span class="badge danger">异常</span>' : '<span class="badge ok">成功</span>') +
        '<span style="margin-left:auto;color:var(--warn);font-size:11.5px">' + (s.elapsed_ms || 0) + ' ms</span></summary>' +
        '<div class="coll-body">' +
        '<div class="tool-args">调用参数：' + esc(s.detail || '{}') + '</div>' +
        (s.output ? '<div class="tool-result">执行返回：' + esc(s.output) + '</div>' : '') +
        '</div></details>';
    }).join('');

    const sentCard = sentList.length
      ? '<details class="collapsible sent-flow" data-coll-key="' + esc(turn.turn_id + '::sent') + '"' + isOpen('sent', true) + '>' +
        '<summary><span class="tool-ico">💬</span><span class="tool-name-flow">已发送到 QQ</span>' +
        '<span class="tool-label">' + sentList.length + ' 条消息</span>' +
        '<span class="badge ok">已发送</span></summary>' +
        '<div class="coll-body">' + sentList.map((m, idx) => (idx + 1) + '. ' + esc(m)).join('\n') + '</div></details>'
      : '';

    const finishCard = '<details class="collapsible finish-flow" data-coll-key="' + esc(turn.turn_id + '::finish') + '"' + isOpen('finish', true) + '>' +
      '<summary><span class="tool-ico">🏁</span><span class="tool-name-flow">finish</span>' +
      '<span class="tool-label">结束本次会话</span></summary>' +
      '<div class="coll-body">状态：' + esc(turn.status || 'done') +
      ' · 携带上下文 ' + (ctx.known ? (ctx.count + ' 条') : '未知') +
      ' · 共 ' + turn.rounds + ' 轮模型调用 · 已发送 ' + turn.sent_count + ' 条 · 总耗时 ' + turn.total_ms + ' ms</div></details>';

    host.innerHTML = head + '<div class="msg-flow">' + sysCard + usrCard + stepCards + sentCard + finishCard + '</div>';
  }

  host.querySelectorAll('details.collapsible[data-coll-key]').forEach((d) => {
    d.addEventListener('toggle', () => {
      state.turnOpenMap.set(d.dataset.collKey, d.open);
    });
  });
  host.scrollTop = keepScroll;

  const jBtn = $('btn-json-mode');
  if (jBtn) {
    jBtn.addEventListener('click', () => {
      state.turnJsonMode = !state.turnJsonMode;
      renderTurnSessionDetail(turn, { force: true });
    });
  }
}

function renderTurnSessionList(opts) {
  const force = Boolean(opts && opts.force);
  const list = state.turns || [];
  $('session-count').textContent = list.length + ' 个会话';
  const host = $('session-list');
  if (!host) return;
  if (!list.length) {
    state.lastTurnListFp = '';
    host.innerHTML = '<div class="empty">暂无会话记录</div>';
    renderTurnSessionDetail(null, { force: true });
    return;
  }
  if (!state.selectedTurnId || !list.some((x) => x.turn_id === state.selectedTurnId)) {
    state.selectedTurnId = list[0].turn_id;
  }
  const listFp = state.selectedTurnId + '|' + list.map((t) => t.turn_id + ':' + t.status + ':' + t.rounds + ':' + (t.steps || []).length + ':' + t.sent_count + ':' + (t.context_count || 0)).join(',');
  if (force || state.lastTurnListFp !== listFp) {
    state.lastTurnListFp = listFp;
    host.innerHTML = list.map((t) => {
      const active = t.turn_id === state.selectedTurnId ? ' active' : '';
      const itemChat = (t.chat_key || state.chatKey || 'group:10002002').replace('group:', '群 ').replace('private:', '私聊 ');
      const stBadge = t.status === 'running'
        ? '<span class="badge accent">⚡ 运行中…</span>'
        : (t.status === 'error' ? '<span class="badge danger">异常</span>' : '<span class="badge ok">完成</span>');
      const ctx = resolveContextInfo(t);
      const tok = summarizeTurnTokens(t);
      const ctxBadge = ctx.known
        ? ('<span class="badge ' + (ctx.count <= 1 ? 'warn' : 'muted') + '" title="本轮携带的已读历史消息条数">上下文 ' + ctx.count + ' 条</span>')
        : '';
      const tokSpan = tok.total > 0 ? ('<span>' + tok.total + ' tok</span>') : '';
      return '<div class="session-item' + active + '" data-turn-id="' + esc(t.turn_id) + '">' +
        '<div class="top"><span class="name">' + esc(itemChat) + '</span><span class="time">' + fmtTime(t.ts) + '</span></div>' +
        '<div class="session-trigger">' + esc(t.trigger || '(系统触发)') + '</div>' +
        '<div class="session-meta">' +
        stBadge +
        '<span class="badge accent">' + esc(t.model || '-') + '</span>' +
        ctxBadge +
        tokSpan +
        '<span>' + t.rounds + ' 轮</span>' +
        '<span>' + t.sent_count + ' 发</span>' +
        '<span>' + t.total_ms + ' ms</span>' +
        '</div></div>';
    }).join('');
    host.querySelectorAll('[data-turn-id]').forEach((el) => {
      el.addEventListener('click', () => {
        state.selectedTurnId = el.dataset.turnId;
        renderTurnSessionList({ force: true });
      });
    });
  }
  const selected = list.find((x) => x.turn_id === state.selectedTurnId) || list[0];
  renderTurnSessionDetail(selected, { force });
}

function setSessionViewMode(mode) {
  state.sessionMode = mode;
  const bTurns = $('btn-mode-turns');
  const bArch = $('btn-mode-archive');
  if (bTurns) bTurns.classList.toggle('primary', mode === 'turns');
  if (bArch) bArch.classList.toggle('primary', mode === 'archive');
  const detailPane = $('session-detail');
  const archPane = $('archive-pane');
  if (detailPane) detailPane.style.display = mode === 'turns' ? 'block' : 'none';
  if (archPane) archPane.style.display = mode === 'archive' ? 'block' : 'none';
  if (mode === 'turns') {
    state.lastTurnListFp = '';
    state.lastTurnDetailFp = '';
    renderTurnSessionList({ force: true });
  } else {
    state.lastTurnListFp = '';
    state.lastStreamFp = '';
    renderArchiveChatList(state.sessions);
    loadStream();
  }
}

function renderArchiveChatList(list) {
  state.lastTurnListFp = '';
  state.sessions = list || [];
  if (!state.chatKey && state.sessions.length) state.chatKey = state.sessions[0].chat_key;
  $('session-count').textContent = state.sessions.length + ' 个聊天';
  const host = $('session-list');
  host.innerHTML = state.sessions.map((s) => {
    const active = s.chat_key === state.chatKey ? ' active' : '';
    const name = s.chat_key.replace('group:', '群 ').replace('private:', '私聊 ');
    const lastModel = (state.traceByChat || {})[s.chat_key];
    const modelTag = lastModel ? ' <span class="badge accent">' + esc(lastModel) + '</span>' : '';
    return '<div class="session-item' + active + '" data-key="' + esc(s.chat_key) + '">' +
      '<div class="top"><span class="name">' + esc(name) + modelTag + '</span><span class="time">' + fmtTime(s.last_ts) + '</span></div>' +
      '<div class="prev">' + s.total + ' 条 · ' + esc(s.last_sender) + '：' + esc(s.preview) + '</div></div>';
  }).join('') || '<div class="empty">暂无会话</div>';
  host.querySelectorAll('[data-key]').forEach((el) => {
    el.addEventListener('click', () => {
      state.chatKey = el.dataset.key;
      renderArchiveChatList(state.sessions);
      loadStream();
    });
  });
}

function renderSessions(list) {
  state.sessions = list || [];
  if (!state.chatKey && state.sessions.length) state.chatKey = state.sessions[0].chat_key;
  if (state.sessionMode === 'archive') {
    renderArchiveChatList(state.sessions);
  }
}

function renderSteps(turn) {
  return (turn.steps || []).map((s) =>
    '<div class="step ' + s.kind + '"><span class="idx">' + s.seq + '</span>' +
    '<span class="kind">' + (s.kind === 'llm' ? 'LLM' : 'TOOL') + '</span>' +
    '<span class="nm">' + esc(s.name || '-') + '</span>' +
    '<span class="dt">' + esc(s.detail || '') + '</span>' +
    '<span class="ms">' + (s.elapsed_ms || 0) + ' ms</span></div>').join('');
}

function assignTurns(msgs) {
  const map = new Map();
  const used = new Set();
  const sendTexts = (tl) => (tl.steps || []).filter((s) =>
    s.kind === 'tool' && (s.name || '').indexOf('send_message') === 0).map((s) => s.detail || '');

  for (const turn of state.turns || []) {
    const details = sendTexts(turn);
    let picked = -1;
    for (let i = msgs.length - 1; i >= 0; i -= 1) {
      const m = msgs[i];
      if (!m.is_self || used.has(i)) continue;
      if (details.some((d) => d.includes(m.text))) { picked = i; break; }
    }
    if (picked >= 0) { used.add(picked); map.set(picked, turn); }
  }
  return map;
}

function tracePanel(turn) {
  const head = '<div class="turn-head-tiny">' +
    '<span>' + turn.rounds + ' 轮 · ' + turn.sent_count + ' 条发送 · ' + turn.total_ms + ' ms</span>' +
    '<span class="badge accent">' + esc(turn.model || '-') + '</span>' +
    '<span>' + fmtTime(turn.ts) + '</span></div>';
  return '<div class="trace-inline">' + head + renderSteps(turn) + '</div>';
}

async function loadTurns() {
  try {
    const d = await api('/api/mind/turns?limit=60');
    state.turns = (d.turns || []).map((x) => ({ ...x, chat_key: x.chat_key || state.chatKey || 'group:10002002' }));
    if (state.sessionMode === 'turns') renderTurnSessionList();
  } catch (e) { state.turns = []; }
}

async function loadStream() {
  if (!state.chatKey) state.chatKey = 'group:10002002';
  try {
    const payload = await api('/api/mind/messages?chat_key=' + encodeURIComponent(state.chatKey) + '&limit=150');
    await loadTurns();
    renderStream(payload);
  } catch (e) { toast('消息加载失败：' + e.message, true); }
}

function renderStream(payload, opts) {
  const force = Boolean(opts && opts.force);
  $('stream-title').textContent = '消息流 · ' + payload.chat_key;
  const host = $('stream');
  const msgs = payload.messages || [];
  const lastId = msgs.length ? msgs[msgs.length - 1].id : 0;
  const streamFp = payload.chat_key + '|' + msgs.length + '|' + lastId + '|' + (state.turns || []).length;
  if (!force && state.lastStreamFp === streamFp) {
    return;
  }
  const wasFirst = !state.lastStreamFp;
  const wasAtBottom = host.scrollHeight - host.scrollTop - host.clientHeight < 48;
  const keepScroll = host.scrollTop;
  state.lastStreamFp = streamFp;

  const turnMap = assignTurns(msgs);
  host.innerHTML = msgs.map((m, i) => {
    const self = m.is_self ? ' self' : '';
    const initial = (m.sender_name || '?').trim().charAt(0) || '?';
    const turn = turnMap.get(i);
    const traceKey = payload.chat_key + '::' + m.id;
    const isOpen = state.openStreamTraces.has(traceKey);
    const hint = turn
      ? '<span class="trace-hint' + (isOpen ? ' open' : '') + '" data-turn="' + i + '" data-trace-key="' + esc(traceKey) + '">🧠 ' + (turn.steps || []).length + ' 步处理过程</span>'
      : '';
    return '<div class="msg' + self + '"><div class="av">' + esc(initial) + '</div><div class="body">' +
      '<div class="who">' + esc(m.is_self ? '回音' : m.sender_name) + '<span>' + fmtTime(m.ts) + '</span></div>' +
      '<div class="text">' + esc(m.text) + '</div>' + hint +
      '<div class="trace-slot" id="trace-slot-' + i + '">' + (turn && isOpen ? tracePanel(turn) : '') + '</div></div></div>';
  }).join('');

  host.querySelectorAll('.trace-hint').forEach((el) => {
    el.addEventListener('click', () => {
      const idx = Number(el.dataset.turn);
      const tKey = el.dataset.traceKey;
      const turn = turnMap.get(idx);
      const slot = document.getElementById('trace-slot-' + idx);
      if (!turn || !slot) return;
      const open = el.classList.toggle('open');
      if (open) state.openStreamTraces.add(tKey);
      else state.openStreamTraces.delete(tKey);
      slot.innerHTML = open ? tracePanel(turn) : '';
    });
  });
  if (wasFirst || wasAtBottom) host.scrollTop = host.scrollHeight;
  else host.scrollTop = keepScroll;
}

function renderMemory(s) {
  const facts = s.facts || [];
  $('memory-facts').innerHTML = facts.length ? '<table><tr><th>主题</th><th>内容</th><th>状态</th><th></th></tr>' +
    facts.map((f) => '<tr><td>' + esc(f.subject) + '</td><td>' + esc(f.fact_text) + '</td><td>' +
      (f.is_locked ? '<span class="badge ok">锁定</span>' : '<span class="badge warn">' + Math.round(f.confidence * 100) + '%</span>') +
      '</td><td><button class="btn sm danger" data-del-fact="' + f.fact_id + '">删除</button></td></tr>').join('') + '</table>' : '<div class="empty">暂无</div>';

  $('memory-facts').querySelectorAll('[data-del-fact]').forEach((b) => {
    b.addEventListener('click', async () => {
      if (!confirm('确定删除这条语义事实？')) return;
      await api('/api/mind/facts/' + b.dataset.delFact, { method: 'DELETE' });
      toast('已删除事实 #' + b.dataset.delFact);
      refresh();
    });
  });

  const rules = s.rules || [];
  if ($('memory-rules')) {
    $('memory-rules').innerHTML = rules.length ? '<table><tr><th>触发词</th><th>限定QQ</th><th>条件反射指令</th><th></th></tr>' +
      rules.map((r) => '<tr><td><span class="badge accent">' + esc(r.trigger_keyword) + '</span></td><td>' +
        esc(r.trigger_user_id || '全员') + '</td><td>' + esc(r.action_instruction) +
        '</td><td><button class="btn sm danger" data-del-rule="' + r.rule_id + '">删除</button></td></tr>').join('') + '</table>'
      : '<div class="empty">暂无条件反射规则</div>';
    $('memory-rules').querySelectorAll('[data-del-rule]').forEach((b) => {
      b.addEventListener('click', async () => {
        if (!confirm('确定删除这条条件反射规则？')) return;
        await api('/api/mind/rules/' + b.dataset.delRule, { method: 'DELETE' });
        toast('已删除规则 #' + b.dataset.delRule);
        refresh();
      });
    });
  }

  const cards = s.episodic || [];
  $('memory-episodic').innerHTML = cards.length ? cards.map((c) => {
    const cls = c.clarity === 'clear' ? 'ok' : (c.clarity === 'fuzzy' ? 'warn' : 'danger');
    return '<div style="padding:8px 0;border-bottom:1px dashed #1e2532">' +
      '<div class="row" style="border:none;padding:0 0 4px"><span class="lbl">' + esc(c.summary) + '</span>' +
      '<span style="display:flex;gap:6px;align-items:center"><span class="badge ' + cls + '">' + c.clarity + ' ' + c.retention_pct + '%</span>' +
      (c.pinned ? '<span class="badge accent">置顶</span>' : '') +
      '<button class="btn sm danger" data-del="' + c.card_id + '">删除</button></span></div>' +
      '<div class="bar ' + cls + '"><i style="width:' + c.retention_pct + '%"></i></div>' +
      (c.key_detail ? '<div class="lbl" style="margin-top:4px;font-size:11px">↳ ' + esc(c.key_detail) + '</div>' : '') +
      '</div>';
  }).join('') : '<div class="empty">暂无情景记忆</div>';

  $('memory-episodic').querySelectorAll('[data-del]').forEach((b) => {
    b.addEventListener('click', async () => {
      if (!confirm('确定删除这张记忆卡？')) return;
      await api('/api/mind/episodic/' + b.dataset.del, { method: 'DELETE' });
      toast('已删除记忆卡 ' + b.dataset.del);
      refresh();
    });
  });
}

const LEVEL_TITLES = { 1: '陌生', 2: '眼熟', 3: '熟人', 4: '老友', 5: '挚友' };
const LEVEL_NEXT = { 1: 50, 2: 100, 3: 200, 4: 500, 5: null };

async function saveBondScore(uid, score, name, isRival, trustScore) {
  try {
    const body = { affinity_score: Number(score), user_name: name || '' };
    if (typeof isRival === 'boolean') body.is_rival = isRival;
    if (typeof trustScore === 'number' && !Number.isNaN(trustScore)) body.trust_score = trustScore;
    const d = await api('/api/mind/bonds/' + encodeURIComponent(uid), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const b = d.bond || {};
    toast('已更新 ' + (b.user_name || uid) + '：好感 ' + b.affinity_score + ' / 可信度 ' + Math.round((b.trust_score || 0.8) * 100) + '%');
    refresh();
  } catch (e) { toast('修改关系档案失败：' + e.message, true); }
}

function renderSocial(s) {
  const activeEl = document.activeElement;
  if (activeEl && activeEl.dataset && activeEl.dataset.bondInput) return;
  const bonds = (s.bonds || []).slice().sort((x, y) => y.affinity_score - x.affinity_score);
  $('social-count').textContent = bonds.length + ' 人 · 好感度与元认知可信度均随对话动态演化，也支持手动微调';
  $('social-table').innerHTML = bonds.length ? '<table><tr><th>#</th><th>群友</th><th>身份</th><th>好感度 / 升级进度</th><th>等级</th><th>可信度（防忽悠校准）</th><th>标记</th><th>手动调整好感度</th></tr>' +
    bonds.map((b, i) => {
      const next = LEVEL_NEXT[b.affinity_level];
      const prog = next ? (b.affinity_score.toFixed(1) + ' / ' + next) : (b.affinity_score.toFixed(0) + '（满级）');
      const title = LEVEL_TITLES[b.affinity_level] || '';
      const tCls = b.trust_score >= 0.75 ? 'ok' : (b.trust_score >= 0.60 ? 'warn' : 'danger');
      const tPct = Math.round(b.trust_score * 100) + '%';
      return '<tr><td>' + (i + 1) + '</td><td>' + esc(b.user_name) + '<span class="lbl" style="font-size:10.5px"> · ' + esc(b.user_id) + '</span></td>' +
        '<td>' + (b.group_role === 'owner' ? '<span class="badge pink">群主</span>' : b.group_role === 'admin' ? '<span class="badge accent">管理</span>' : '<span class="badge muted">成员</span>') + '</td>' +
        '<td><b>' + prog + '</b></td><td><span class="badge ok">Lv.' + b.affinity_level + ' ' + esc(title) + '</span></td>' +
        '<td><div style="display:flex;gap:5px;align-items:center">' +
        '<button class="btn sm" data-trust-uid="' + esc(b.user_id) + '" data-trust-val="' + Math.max(0.1, b.trust_score - 0.05).toFixed(2) + '" data-trust-score="' + b.affinity_score + '" data-trust-name="' + esc(b.user_name) + '" title="下调可信度 -5%">-</button>' +
        '<span class="badge ' + tCls + '" style="min-width:48px;text-align:center">' + tPct + '</span>' +
        '<button class="btn sm" data-trust-uid="' + esc(b.user_id) + '" data-trust-val="' + Math.min(1.0, b.trust_score + 0.05).toFixed(2) + '" data-trust-score="' + b.affinity_score + '" data-trust-name="' + esc(b.user_name) + '" title="上调可信度 +5%">+</button>' +
        '</div></td>' +
        '<td><button class="btn sm ' + (b.is_rival ? 'danger' : '') + '" data-rival-uid="' + esc(b.user_id) + '" data-rival-val="' + (b.is_rival ? '1' : '0') + '" data-rival-score="' + b.affinity_score + '" data-rival-name="' + esc(b.user_name) + '">' + (b.is_rival ? '情敌 ✕' : '设为情敌') + '</button></td>' +
        '<td><div style="display:flex;gap:5px;align-items:center">' +
        '<button class="btn sm" data-step-uid="' + esc(b.user_id) + '" data-step-val="' + (b.affinity_score - 10) + '" data-step-name="' + esc(b.user_name) + '">-10</button>' +
        '<input type="number" step="1" data-bond-input="' + esc(b.user_id) + '" value="' + b.affinity_score.toFixed(1) + '" style="width:86px;padding:4px 7px;background:var(--panel-2);color:var(--text);border:1px solid var(--border-2);border-radius:6px;font-family:var(--mono);font-size:12px" />' +
        '<button class="btn sm" data-step-uid="' + esc(b.user_id) + '" data-step-val="' + (b.affinity_score + 10) + '" data-step-name="' + esc(b.user_name) + '">+10</button>' +
        '<button class="btn primary sm" data-save-bond="' + esc(b.user_id) + '" data-bond-name="' + esc(b.user_name) + '">保存</button>' +
        '</div></td></tr>';
    }).join('') + '</table>'
    : '<div class="empty">暂无社交关系</div>';

  const tbl = $('social-table');
  tbl.querySelectorAll('[data-step-uid]').forEach((btn) => {
    btn.addEventListener('click', () => saveBondScore(btn.dataset.stepUid, btn.dataset.stepVal, btn.dataset.stepName));
  });
  tbl.querySelectorAll('[data-trust-uid]').forEach((btn) => {
    btn.addEventListener('click', () => saveBondScore(btn.dataset.trustUid, btn.dataset.trustScore, btn.dataset.trustName, undefined, Number(btn.dataset.trustVal)));
  });
  tbl.querySelectorAll('[data-save-bond]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const uid = btn.dataset.saveBond;
      const inp = tbl.querySelector('[data-bond-input="' + uid + '"]');
      if (inp) saveBondScore(uid, inp.value, btn.dataset.bondName);
    });
  });
  tbl.querySelectorAll('[data-rival-uid]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const isR = btn.dataset.rivalVal === '1';
      saveBondScore(btn.dataset.rivalUid, btn.dataset.rivalScore, btn.dataset.rivalName, !isR);
    });
  });
}

function renderPlastic(s) {
  const dirEl = $('live-persona-directive');
  if (dirEl) dirEl.textContent = s.persona_directive || '（暂无合成指令）';
  const params = s.plastic_params || {};
  const keys = Object.keys(params).sort();
  $('plastic-list').innerHTML = keys.map((k) => {
    const p = params[k];
    const pct = ((p.value - p.min_bound) / (p.max_bound - p.min_bound || 1)) * 100;
    return '<div style="padding:6px 0;border-bottom:1px dashed #1e2532">' +
      '<div class="row" style="border:none;padding:0 0 4px"><span class="lbl" title="' + esc(p.description) + '">' + esc(k) + '</span>' +
      '<span style="display:flex;gap:5px;align-items:center"><span class="val">' + p.value.toFixed(2) + '</span>' +
      '<button class="btn sm" data-tune="' + k + '" data-delta="-2">-2</button>' +
      '<button class="btn sm" data-tune="' + k + '" data-delta="2">+2</button></span></div>' +
      '<div class="bar"><i style="width:' + Math.max(0, Math.min(100, pct)) + '%"></i></div>' +
      '<div class="lbl" style="font-size:10.5px;margin-top:3px">' + p.min_bound + ' ~ ' + p.max_bound + ' · ' + esc(p.description) + '</div></div>';
  }).join('');

  $('plastic-list').querySelectorAll('[data-tune]').forEach((b) => {
    b.addEventListener('click', async () => {
      await api('/api/mind/plastic/tune', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: b.dataset.tune, delta: Number(b.dataset.delta), reason: '控制台手动调校' }),
      });
      toast(b.dataset.tune + ' 已调整 ' + b.dataset.delta);
      refresh();
    });
  });

  const logs = s.plastic_logs || [];
  $('plastic-logs').innerHTML = logs.length ? '<table><tr><th>时间</th><th>参数</th><th>变化</th><th>奖励</th><th>原因</th></tr>' +
    logs.map((l) => '<tr><td style="white-space:nowrap">' + fmtTime(l.ts) + '</td><td>' + esc(l.param_key) + '</td>' +
      '<td>' + l.old_val.toFixed(2) + ' → <b>' + l.new_val.toFixed(2) + '</b></td>' +
      '<td>' + (l.reward >= 0 ? '<span class="badge ok">' : '<span class="badge danger">') + l.reward.toFixed(2) + '</span></td>' +
      '<td>' + esc(l.reason) + '</td></tr>').join('') + '</table>' : '<div class="empty">暂无演化记录</div>';
}


function renderVoiceHealth(v) {
  const host = $('voice-health');
  if (!host) return;
  if (!v || v.ok !== true) { host.innerHTML = '<div class="empty">语音服务探测失败</div>'; return; }
  const badge = v.online
    ? '<span class="badge ok">在线</span>'
    : '<span class="badge danger">离线</span>';
  if (!v.online) {
    host.innerHTML = badge + ' <span class="lbl" style="margin-left:8px">' + esc(v.reason || '') + '</span>';
    return;
  }
  const rows = (v.voices || []).map((x) =>
    '<div class="row"><span class="lbl">' + esc(x.voice) + ' · ' + esc(x.engine) + '</span>' +
    '<span class="val">' + (x.available ? '<span class="badge ok">可用</span>' : '<span class="badge muted">不可用</span>') +
    ' 风格：<b>' + esc((x.styles || []).join(' / ') || '-') + '</b></span></div>').join('');
  host.innerHTML = badge + ' <span class="lbl" style="margin-left:8px">' +
    esc(v.voices && v.voices.length ? v.voices[0].package : '') + '</span>' + (rows || '<div class="empty">无可用音色</div>');
}

const SKILL_LABELS = {
  meme_wiki: '梗百科词典',
  web_search: '联网实时搜索',
  bili_search: 'B站视频搜索',
  bili_video: 'B站视频详情',
  bili_popular: 'B站热门榜单',
  look_at_image: '多模态看图识别',
  watch_video: '视频多帧抽帧识别',
  read_voice: '群语音转文字（QQ原生）',
  read_forward: '展开合并转发聊天记录（支持多层套娃嵌套）',
  send_message: '发送文字回复',
  send_sticker: '发送情绪表情包',
  send_poke: 'QQ 拍一拍互动',
  get_group_members: '查询群成员与权限名单',
  feiyu_say: '飞鱼语音合成发送（亲口说话）',
  feiyu_cover: '飞鱼全曲 AI 翻唱（带伴奏唱歌）',
  memory_append: '记录群友身份与长期印象',
  recall_memory: '深度翻找长期记忆与往事档案',
  qzone_publish: '发布 QQ 空间说说动态（含空间心情橱窗定时配置）',
  profile_signature: '修改 QQ 个性签名（含空间心情橱窗定时配置）',
};

function formatTargetTagLabel(raw) {
  const s = String(raw || '').trim();
  if (s.startsWith('group:') && s.includes('@')) {
    const [g, u] = s.slice(6).split('@');
    return '🎯 群 ' + g + ' @ ' + u;
  }
  if (s.startsWith('group:')) return '💬 群聊 ' + s.slice(6);
  if (s.startsWith('private:')) return '💌 私聊 ' + s.slice(8);
  return '🎯 ' + s;
}

function renderProactiveTargetChips(rowName, rawVal) {
  const items = String(rawVal || '').split(/[,，;；\s\n]+/).map((x) => x.trim()).filter(Boolean);
  if (!items.length) return '<span class="lbl" style="font-size:11.5px">暂未添加目标（下方可添加多个群聊或个人）</span>';
  return items.map((it) =>
    '<span class="tag"><b>' + esc(formatTargetTagLabel(it)) + '</b> <code style="font-size:11px;color:var(--muted)">' + esc(it) + '</code>' +
    '<button type="button" data-rm-target="' + esc(it) + '" data-rm-row="' + esc(rowName) + '" title="移除该目标">✕</button></span>'
  ).join('');
}

function renderProactiveTargetBuilder(rowName, skill, f, val) {
  const curVal = val || f.default || 'private:10001001, group:10002002';
  const bonds = (state.snapshot && state.snapshot.bonds) || [];
  const userOpts = bonds.map((b) => '<option value="' + esc(b.user_id) + '">' + esc(b.user_name + ' (' + b.user_id + ')') + '</option>').join('');
  return '<div class="card" style="background:var(--panel);padding:10px 12px;margin-bottom:10px">' +
    '<div style="font-size:12px;font-weight:600;margin-bottom:6px">' + esc(f.label) +
    ' <span class="lbl" style="font-weight:400">（可同时配置多个群聊、多个私聊个人、或在群内指定@某人）</span></div>' +
    '<div class="tag-list" id="pt-chips-' + esc(rowName) + '" style="margin-bottom:8px">' +
    renderProactiveTargetChips(rowName, curVal) + '</div>' +
    '<div class="form-row" style="margin-bottom:6px;flex-wrap:wrap">' +
    '<select id="pt-kind-' + esc(rowName) + '" data-pt-kind="' + esc(rowName) + '" style="max-width:190px">' +
    '<option value="private">💌 私聊某人 (private:QQ)</option>' +
    '<option value="group">💬 群聊冒泡 (group:群号)</option>' +
    '<option value="group_at">🎯 群内@某人 (group:群号@QQ)</option>' +
    '</select>' +
    '<input id="pt-id-' + esc(rowName) + '" list="pt-users-' + esc(rowName) + '" placeholder="输入QQ号或群号（如 10001001 或 10002002）" style="max-width:240px" />' +
    '<input id="pt-at-' + esc(rowName) + '" list="pt-users-' + esc(rowName) + '" placeholder="要@的群友QQ号" style="max-width:170px;display:none" />' +
    '<datalist id="pt-users-' + esc(rowName) + '">' + userOpts + '<option value="10002002">群 10002002</option></datalist>' +
    '<button type="button" class="btn sm primary" data-pt-add="' + esc(rowName) + '">➕ 添加目标</button>' +
    '</div>' +
    '<div class="form-row" style="margin-bottom:0"><label style="font-size:11px">原始列表</label>' +
    '<input id="pt-input-' + esc(rowName) + '" data-cfg-row="' + esc(rowName) + '" data-cfg-skill="' + esc(skill) + '" data-key="' + esc(f.key) +
    '" type="text" placeholder="' + esc(f.placeholder || '') + '" value="' + esc(curVal) + '" /></div>' +
    '</div>';
}

function renderSkillDrawer(tool, cfg) {
  if (!cfg) return '';
  const skill = cfg.skill;
  const open = state.openSkillCfgs.has(tool.name);
  const inputs = (cfg.fields || []).map((f) => {
    const val = (cfg.values || {})[f.key] || '';
    if (f.key === 'proactive_target') {
      return renderProactiveTargetBuilder(tool.name, skill, f, val);
    }
    const type = f.kind === 'password' ? 'password' : (f.kind === 'number' ? 'number' : 'text');
    const ph = f.secret
      ? (val ? ('已保存：' + val + '（留空不修改）') : (f.placeholder || '未设置'))
      : (f.placeholder || '未设置');
    const help = f.help ? '<div class="lbl" style="font-size:11px;margin:2px 0 8px">' + esc(f.help) + '</div>' : '';
    return '<div class="form-row" style="margin-bottom:8px"><label>' + esc(f.label) + '</label>' +
      '<input data-cfg-row="' + esc(tool.name) + '" data-cfg-skill="' + esc(skill) + '" data-key="' + esc(f.key) +
      '" type="' + type + '" placeholder="' + esc(ph) + '" value="' + (f.secret ? '' : esc(val || f.default || '')) + '" />' +
      '</div>' + help;
  }).join('');
  return '<div class="skill-cfg-drawer" id="drawer-' + esc(tool.name) + '" style="display:' + (open ? 'block' : 'none') + '">' +
    inputs +
    '<div style="display:flex;gap:8px;align-items:center;margin-top:8px">' +
    '<button class="btn primary sm" data-save-row="' + esc(tool.name) + '" data-save-skill="' + esc(skill) + '">💾 保存配置</button>' +
    '<span class="lbl" style="font-size:11px">配置组：' + esc(skill) + '（保存后即时生效）</span>' +
    '</div></div>';
}

async function saveSkillRowConfig(rowName, skill) {
  const values = {};
  document.querySelectorAll('[data-cfg-row="' + rowName + '"]').forEach((el) => {
    if (el.type === 'password' && !el.value.trim()) return;
    values[el.dataset.key] = el.value.trim();
  });
  try {
    const d = await api('/api/mind/skills/configs/' + encodeURIComponent(skill), {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ values }),
    });
    toast(d.ok ? '已保存 ' + skill + ' 设置' : '保存失败');
    loadSkills();
  } catch (e) { toast('保存失败：' + e.message, true); }
}

async function toggleSkillRow(name) {
  try {
    const d = await api('/api/mind/skills/' + encodeURIComponent(name) + '/toggle', { method: 'POST' });
    toast(name + (d.enabled ? ' 已启用' : ' 已禁用'));
    loadSkills();
  } catch (e) { toast('切换失败：' + e.message, true); }
}

async function deleteSkillRow(name) {
  try {
    await api('/api/mind/skills/' + encodeURIComponent(name), { method: 'DELETE' });
    state.openSkillCfgs.delete(name);
    toast('已删除技能 ' + name);
    loadSkills();
  } catch (e) { toast('删除失败：' + e.message, true); }
}

async function restoreDeletedSkills() {
  try {
    const d = await api('/api/mind/skills/restore', { method: 'POST' });
    toast('已恢复 ' + (d.restored || []).length + ' 个技能');
    loadSkills();
  } catch (e) { toast('恢复失败：' + e.message, true); }
}

async function loadSkills() {
  try {
    const [d, v, c] = await Promise.all([
      api('/api/mind/skills'),
      api('/api/mind/voice').catch(() => null),
      api('/api/mind/skills/configs').catch(() => ({ configs: [] })),
    ]);
    const cfgMap = {};
    (c.configs || []).forEach((x) => { cfgMap[x.skill] = x; });
    renderVoiceHealth(v);

    const headActs = $('skill-head-actions');
    if (headActs) {
      headActs.innerHTML = d.deleted_count > 0
        ? '<button class="btn sm" id="btn-restore-skills">↺ 恢复已删除技能 (' + d.deleted_count + ')</button>'
        : '';
      const rBtn = $('btn-restore-skills');
      if (rBtn) rBtn.addEventListener('click', restoreDeletedSkills);
    }

    const host = $('skill-groups');
    if (!host) return;
    host.innerHTML = (d.groups || []).map((g) => {
      const rows = g.tools.map((tool) => {
        const cfg = cfgMap[tool.config_key];
        const configured = cfg && Object.values(cfg.values || {}).some((val) => val);
        const en = tool.enabled !== false;
        const stateBadge = en
          ? '<span class="badge ok">已启用</span>'
          : '<span class="badge muted">已禁用</span>';
        const cfgBadge = configured
          ? '<span class="badge accent">已配置</span>'
          : '';
        const cnTitle = SKILL_LABELS[tool.name] || tool.name;
        return '<div class="skill-row-wrap ' + (en ? 'on' : 'off') + '" data-skill-wrap="' + esc(tool.name) + '">' +
          '<div class="skill-row" data-toggle-skill="' + esc(tool.name) + '" title="单击切换启用/禁用">' +
          '<div class="skill-row-main">' +
          '<div class="skill-row-top">' +
          stateBadge +
          '<span class="skill-row-name">' + esc(cnTitle) + '</span>' +
          '<code class="badge muted" style="font-family:var(--mono)">' + esc(tool.name) + '</code>' +
          cfgBadge +
          '</div>' +
          '<div class="skill-row-desc">' + esc(tool.description) + '</div>' +
          '</div>' +
          '<div class="skill-row-acts">' +
          '<button class="btn sm" data-open-cfg="' + esc(tool.name) + '" title="展开或收起该技能设置">⚙ 设置</button>' +
          '<button class="btn sm danger" data-del-skill="' + esc(tool.name) + '" title="删除该技能">🗑 删除</button>' +
          '</div></div>' +
          renderSkillDrawer(tool, cfg) +
          '</div>';
      }).join('');
      return '<div class="skill-cat-title"><span>' + esc(g.category) + '</span>' +
        '<span class="badge accent">' + g.tools.length + ' 项</span></div>' +
        '<div class="skill-list">' + rows + '</div>';
    }).join('') || '<div class="empty">暂无技能（可点击右上角恢复已删除技能）</div>';

    host.querySelectorAll('[data-toggle-skill]').forEach((rowEl) => {
      rowEl.addEventListener('click', (ev) => {
        if (ev.target.closest('.skill-row-acts')) return;
        toggleSkillRow(rowEl.dataset.toggleSkill);
      });
    });
    host.querySelectorAll('[data-open-cfg]').forEach((btn) => {
      btn.addEventListener('click', (ev) => {
        ev.stopPropagation();
        const name = btn.dataset.openCfg;
        const drawer = document.getElementById('drawer-' + name);
        if (!drawer) return;
        const willOpen = drawer.style.display === 'none';
        drawer.style.display = willOpen ? 'block' : 'none';
        if (willOpen) state.openSkillCfgs.add(name);
        else state.openSkillCfgs.delete(name);
      });
    });
    host.querySelectorAll('[data-save-row]').forEach((btn) => {
      btn.addEventListener('click', (ev) => {
        ev.stopPropagation();
        saveSkillRowConfig(btn.dataset.saveRow, btn.dataset.saveSkill);
      });
    });
    host.querySelectorAll('[data-del-skill]').forEach((btn) => {
      btn.addEventListener('click', (ev) => {
        ev.stopPropagation();
        deleteSkillRow(btn.dataset.delSkill);
      });
    });
    bindProactiveTargetEvents(host);
  } catch (e) { /* 静默 */ }
}

function bindProactiveTargetEvents(host) {
  const refreshChips = (row) => {
    const inp = $('pt-input-' + row);
    const chips = $('pt-chips-' + row);
    if (!inp || !chips) return;
    chips.innerHTML = renderProactiveTargetChips(row, inp.value);
    chips.querySelectorAll('[data-rm-target]').forEach((b) => {
      b.addEventListener('click', (ev) => {
        ev.stopPropagation();
        const rm = b.dataset.rmTarget;
        const list = inp.value.split(/[,，;；\s\n]+/).map((x) => x.trim()).filter((x) => x && x !== rm);
        inp.value = list.join(', ');
        refreshChips(row);
      });
    });
  };
  host.querySelectorAll('[data-pt-kind]').forEach((sel) => {
    const row = sel.dataset.ptKind;
    refreshChips(row);
    const inp = $('pt-input-' + row);
    if (inp) inp.addEventListener('input', () => refreshChips(row));
    sel.addEventListener('change', () => {
      const atInp = $('pt-at-' + row);
      const idInp = $('pt-id-' + row);
      if (atInp) atInp.style.display = sel.value === 'group_at' ? 'inline-block' : 'none';
      if (idInp) {
        idInp.placeholder = sel.value === 'private' ? '输入私聊对象的 QQ 号' : '输入 QQ 群号（如 10002002）';
      }
    });
  });
  host.querySelectorAll('[data-pt-add]').forEach((btn) => {
    btn.addEventListener('click', (ev) => {
      ev.stopPropagation();
      const row = btn.dataset.ptAdd;
      const kind = ($('pt-kind-' + row) && $('pt-kind-' + row).value) || 'private';
      const idVal = ($('pt-id-' + row) && $('pt-id-' + row).value.trim().replace(/^(group|private|g|p):/i, '')) || '';
      const atVal = ($('pt-at-' + row) && $('pt-at-' + row).value.trim()) || '';
      if (!/^\d+$/.test(idVal)) { toast('请输入纯数字的群号或 QQ 号', true); return; }
      let spec = '';
      if (kind === 'private') spec = 'private:' + idVal;
      else if (kind === 'group') spec = 'group:' + idVal;
      else {
        if (!/^\d+$/.test(atVal)) { toast('请输入要在群内艾特的纯数字 QQ 号', true); return; }
        spec = 'group:' + idVal + '@' + atVal;
      }
      const inp = $('pt-input-' + row);
      if (!inp) return;
      const list = inp.value.split(/[,，;；\s\n]+/).map((x) => x.trim()).filter(Boolean);
      if (!list.includes(spec)) list.push(spec);
      inp.value = list.join(', ');
      if ($('pt-id-' + row)) $('pt-id-' + row).value = '';
      if ($('pt-at-' + row)) $('pt-at-' + row).value = '';
      refreshChips(row);
      toast('已添加目标 ' + spec + '（点击下方「💾 保存配置」生效）');
    });
  });
}

function providerNameOf(pid) {
  const p = (state.llmProviders || []).find((x) => x.id === pid);
  return p ? (p.display_name || p.id) : (pid || '自定义网关');
}

function populateProviderSelects(activePid) {
  const provs = state.llmProviders || [];
  const opts = '<option value="">（自定义直连地址）</option>' +
    provs.map((p) => '<option value="' + esc(p.id) + '">' + esc(p.display_name || p.id) + ' (' + (p.models || []).length + ' 模型)</option>').join('');
  const selPrimary = $('llm-primary-provider');
  const selFb = $('llm-fb-add-provider');
  if (selPrimary) {
    selPrimary.innerHTML = opts;
    selPrimary.value = activePid || '';
    updateModelDatalist(selPrimary.value, 'llm-primary-models');
  }
  if (selFb) {
    selFb.innerHTML = opts;
    if (provs.length && !selFb.value) selFb.value = provs[0].id;
    updateModelDatalist(selFb.value, 'llm-fb-models');
  }
}

function updateModelDatalist(pid, listId) {
  const dl = $(listId);
  if (!dl) return;
  const p = (state.llmProviders || []).find((x) => x.id === pid);
  const models = p ? (p.models || []) : [];
  dl.innerHTML = models.map((m) => '<option value="' + esc(m) + '"></option>').join('');
}

function renderFallbackChain() {
  const host = $('llm-fallback-chain');
  if (!host) return;
  const fbs = state.llmFallbacks || [];
  if (!fbs.length) {
    host.innerHTML = '<div class="empty" style="padding:14px 0">暂未配置备用模型（下方可添加任意多个顺位备用模型）</div>';
    return;
  }
  host.innerHTML = fbs.map((fb, idx) =>
    '<div class="row" style="padding:6px 8px;background:var(--panel-2);border:1px solid var(--border);border-radius:8px;margin-bottom:6px">' +
    '<span><span class="badge warn">备用 #' + (idx + 1) + '</span> ' +
    '<span class="badge muted">' + esc(providerNameOf(fb.provider)) + '</span> ' +
    '<b style="font-family:var(--mono)">' + esc(fb.model) + '</b></span>' +
    '<span style="display:flex;gap:4px">' +
    '<button class="btn sm" data-fb-up="' + idx + '" ' + (idx === 0 ? 'disabled' : '') + ' title="上移顺位">↑</button>' +
    '<button class="btn sm" data-fb-dn="' + idx + '" ' + (idx + 1 >= fbs.length ? 'disabled' : '') + ' title="下移顺位">↓</button>' +
    '<button class="btn sm danger" data-fb-rm="' + idx + '" title="移除">✕</button>' +
    '</span></div>'
  ).join('');

  host.querySelectorAll('[data-fb-up]').forEach((b) => {
    b.addEventListener('click', () => {
      const i = Number(b.dataset.fbUp);
      if (i > 0) {
        const tmp = state.llmFallbacks[i - 1];
        state.llmFallbacks[i - 1] = state.llmFallbacks[i];
        state.llmFallbacks[i] = tmp;
        renderFallbackChain();
      }
    });
  });
  host.querySelectorAll('[data-fb-dn]').forEach((b) => {
    b.addEventListener('click', () => {
      const i = Number(b.dataset.fbDn);
      if (i + 1 < state.llmFallbacks.length) {
        const tmp = state.llmFallbacks[i + 1];
        state.llmFallbacks[i + 1] = state.llmFallbacks[i];
        state.llmFallbacks[i] = tmp;
        renderFallbackChain();
      }
    });
  });
  host.querySelectorAll('[data-fb-rm]').forEach((b) => {
    b.addEventListener('click', () => {
      state.llmFallbacks.splice(Number(b.dataset.fbRm), 1);
      renderFallbackChain();
    });
  });
}

function renderProvidersList() {
  const host = $('llm-providers-list');
  if (!host) return;
  const provs = state.llmProviders || [];
  if (!provs.length) {
    host.innerHTML = '<div class="empty">暂无已注册服务商，点击右上角「➕ 新增服务商」添加</div>';
    return;
  }
  host.innerHTML = '<div class="grid g2">' + provs.map((p, idx) =>
    '<div class="card" style="background:var(--panel-2);padding:12px" data-prov-card="' + idx + '">' +
    '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">' +
    '<span><span class="badge accent">' + esc(p.id) + '</span> <b>' + esc(p.display_name || p.id) + '</b></span>' +
    '<button class="btn sm danger" data-prov-del="' + idx + '">删除服务商</button></div>' +
    '<div class="form-row"><label>显示名称</label><input data-prov-field="display_name" data-prov-idx="' + idx + '" value="' + esc(p.display_name || p.id) + '" /></div>' +
    '<div class="form-row"><label>Base URL</label><input data-prov-field="base_url" data-prov-idx="' + idx + '" value="' + esc(p.base_url || '') + '" placeholder="https://api.deepseek.com/v1" /></div>' +
    '<div class="form-row"><label>API Key</label><input type="password" data-prov-field="api_key" data-prov-idx="' + idx + '" placeholder="' + esc(p.api_key_masked ? ('已存：' + p.api_key_masked + '（留空不改）') : '输入 API Key') + '" /></div>' +
    '<div class="form-row" style="margin-bottom:0"><label>模型列表</label><input data-prov-field="models" data-prov-idx="' + idx + '" value="' + esc((p.models || []).join(', ')) + '" placeholder="逗号分隔，如 deepseek-v4.1-flash, glm-5.3" /></div>' +
    '</div>'
  ).join('') + '</div>';

  host.querySelectorAll('[data-prov-field]').forEach((inp) => {
    inp.addEventListener('input', () => {
      const idx = Number(inp.dataset.provIdx);
      const field = inp.dataset.provField;
      const target = state.llmProviders[idx];
      if (!target) return;
      if (field === 'models') {
        target.models = inp.value.split(/[,，\n]/).map((s) => s.trim()).filter(Boolean);
      } else {
        target[field] = inp.value.trim();
      }
    });
  });
  host.querySelectorAll('[data-prov-del]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const idx = Number(btn.dataset.provDel);
      state.llmProviders.splice(idx, 1);
      renderProvidersList();
      populateProviderSelects($('llm-primary-provider') ? $('llm-primary-provider').value : '');
    });
  });
}

async function loadLlmConfig() {
  const d = await api('/api/mind/llm');
  state.llmProviders = (d.providers || []).map((p) => ({ ...p, models: (p.models || []).slice() }));
  state.llmFallbacks = (d.fallback_models || []).map((x) => ({ ...x }));
  if (!state.llmFallbacks.length && d.fallback && d.fallback.model) {
    state.llmFallbacks.push({ provider: '', model: d.fallback.model });
  }
  populateProviderSelects(d.active_provider || (d.primary && d.primary.provider) || '');
  $('llm-base').value = d.primary.base_url;
  $('llm-model').value = d.primary.model;
  $('llm-timeout').value = d.primary.timeout_ms;
  $('llm-key').placeholder = d.primary.api_key_masked || '留空则不修改';
  $('llm-fb-base').value = d.fallback.base_url;
  $('llm-fb-model').value = d.fallback.model;
  $('llm-fb-key').placeholder = d.fallback.api_key_masked || '留空则不修改';
  $('llm-temp').value = d.temperature;
  $('llm-path').textContent = d.config_path;
  renderFallbackChain();
  renderProvidersList();
}

async function saveLlmConfig() {
  const activePid = ($('llm-primary-provider') && $('llm-primary-provider').value) || '';
  const payload = {
    provider: activePid,
    base_url: $('llm-base').value.trim(),
    model: $('llm-model').value.trim(),
    timeout_ms: Number($('llm-timeout').value) || 90000,
    temperature: Number($('llm-temp').value) || 0.8,
    providers: state.llmProviders,
    fallback_models: state.llmFallbacks,
  };
  if (state.llmFallbacks.length) {
    payload.fallback_model = state.llmFallbacks[0].model;
  }
  const key = $('llm-key').value.trim();
  if (key) payload.api_key = key;
  try {
    const d = await api('/api/mind/llm', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    $('llm-key').value = '';
    $('llm-status').textContent = d.applied
      ? ('已热切换主模型与 ' + (state.llmFallbacks.length || 1) + ' 级备用故障转移链')
      : '已写入配置文件（重启后生效）';
    toast('多服务商与备用模型链已保存并热生效');
    loadLlmConfig();
    loadTraces();
  } catch (e) { toast('保存失败：' + e.message, true); }
}

function renderTraces(list) {
  state.traces = list;
  state.traceByChat = {};
  list.forEach((t) => { if (t.chat_key && !state.traceByChat[t.chat_key]) state.traceByChat[t.chat_key] = t.model; });
  const host = $('llm-traces');
  if (!host) return;
  host.innerHTML = list.length ? '<table><tr><th>时间</th><th>会话</th><th>模型</th><th>网关</th><th>耗时</th><th>Token</th><th></th></tr>' +
    list.map((t) => '<tr><td style="white-space:nowrap">' + fmtTime(t.ts) + '</td>' +
      '<td>' + esc((t.chat_key || '-').replace('group:', '群 ')) + '</td>' +
      '<td><b>' + esc(t.model) + '</b></td>' +
      '<td>' + esc(t.gateway) + '</td>' +
      '<td>' + t.elapsed_ms + ' ms</td>' +
      '<td title="提示 ' + t.prompt + ' / 缓存 ' + t.cached + '">' + t.prompt + '→' + t.completion + '</td>' +
      '<td>' + (t.failover ? '<span class="badge warn">降级</span>' : '<span class="badge ok">主</span>') + '</td></tr>').join('') +
    '</table>' : '<div class="empty">暂无请求记录</div>';
}

async function loadTraces() {
  try { renderTraces((await api('/api/mind/llm/traces?limit=60')).traces); } catch (e) { /* 静默 */ }
}

async function loadPersonaCard(force) {
  try {
    const rtEl = $('persona-role-text');
    if (!force && state.personaLoaded && document.activeElement === rtEl) return;
    const d = await api('/api/mind/persona-card');
    if ($('persona-bot-name')) $('persona-bot-name').value = d.bot_name || '回音';
    if (rtEl) rtEl.value = d.role_text || '';
    state.personaLoaded = true;
  } catch (e) { /* 静默 */ }
}

async function savePersonaCard() {
  const bot_name = ($('persona-bot-name') && $('persona-bot-name').value.trim()) || '回音';
  const role_text = ($('persona-role-text') && $('persona-role-text').value.trim()) || '';
  try {
    const d = await api('/api/mind/persona-card', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bot_name, role_text }),
    });
    if ($('persona-card-status')) {
      $('persona-card-status').textContent = d.applied ? '已保存并热更新至运行实例' : '已写入 config.json';
    }
    toast('最初基础人设已保存并热生效');
  } catch (e) { toast('保存人设失败：' + e.message, true); }
}

async function reconcilePersonaMemory() {
  const btn = $('btn-reconcile-persona');
  const st = $('persona-card-status');
  if (btn) btn.disabled = true;
  if (st) st.textContent = '🧠 正在以当前基础人设审计五维记忆库中的冲突与复读项…';
  try {
    await savePersonaCard();
    const d = await api('/api/mind/persona-card/reconcile', { method: 'POST' });
    if (!d.ok) throw new Error(d.reason || '校准失败');
    const msg = '已清理冲突词条 ' + d.pruned_traits + ' 条、规则 ' + d.pruned_rules +
      ' 条、事实 ' + d.pruned_facts + ' 条、记忆卡 ' + d.pruned_cards +
      ' 张（冲突特征词：' + ((d.contradiction_keywords || []).join('、') || '无') + '）';
    if (st) st.textContent = msg;
    toast(msg);
    await refresh();
    await loadTraits();
  } catch (e) {
    if (st) st.textContent = '校准失败：' + e.message;
    toast('人设冲突校准失败：' + e.message, true);
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function loadBans() {
  const d = await api('/api/mind/bans');
  $('ban-list').innerHTML = d.bans.length ? d.bans.map((b) =>
    '<span class="tag">' + esc(b.phrase) + '<button data-unban="' + esc(b.phrase) + '" title="' + esc(b.reason) + '">×</button></span>').join('')
    : '<span class="empty">暂无禁令</span>';
  $('ban-list').querySelectorAll('[data-unban]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      await api('/api/mind/bans/' + encodeURIComponent(btn.dataset.unban), { method: 'DELETE' });
      toast('已解除：' + btn.dataset.unban);
      loadBans();
    });
  });
}

async function loadTraits() {
  const d = await api('/api/mind/traits');
  $('trait-list').innerHTML = d.traits.length ? d.traits.map((t) =>
    '<div class="row"><span class="lbl">' + (t.category === 'taboo' ? '<span class="badge danger">雷点</span>' : t.category === 'habit' ? '<span class="badge accent">习惯</span>' : '<span class="badge muted">性情</span>') +
    ' ' + esc(t.text) + '</span><span style="display:flex;gap:6px;align-items:center"><span class="val">' + t.strength + '/10</span>' +
    '<button class="btn sm danger" data-deltrait="' + t.id + '">×</button></span></div>').join('') : '<div class="empty">暂无</div>';
  $('trait-list').querySelectorAll('[data-deltrait]').forEach((b) => {
    b.addEventListener('click', async () => {
      await api('/api/mind/traits/' + b.dataset.deltrait, { method: 'DELETE' });
      toast('已移除词条');
      loadTraits();
    });
  });
}

async function loadLogs() {
  const d = await api('/api/mind/logs?lines=200');
  const host = $('log-output');
  host.innerHTML = d.lines.length ? d.lines.map((l) => {
    const cls = /Traceback|Error|error|异常/.test(l) ? 'err' : /WARN|警告/.test(l) ? 'warn' : /EchoMind/.test(l) ? 'hit' : '';
    return '<div class="log-line ' + cls + '">' + esc(l) + '</div>';
  }).join('') : '<div class="empty">暂无日志</div>';
  host.scrollTop = host.scrollHeight;
}

async function loadUsage() {
  try {
    const d = await api('/api/mind/usage');
    const u = d.usage;
    $('chip-calls').textContent = u.calls;
    $('chip-cached').textContent = u.cached + ' tok';
  } catch (e) { /* 静默 */ }
}

async function refresh() {
  try {
    const snap = await api('/api/mind/snapshot');
    state.snapshot = snap;
    if ((!state.chatKey || state.chatKey === 'group:10002002') && snap.chat_key) {
      state.chatKey = snap.chat_key;
    }
    $('chip-group').textContent = (snap.chat_key || '').replace('group:', '');
    renderOverview(snap);
    renderMemory(snap);
    renderSocial(snap);
    renderPlastic(snap);
  } catch (e) { toast('快照加载失败：' + e.message, true); }
}

async function refreshSessions() {
  try {
    const d = await api('/api/mind/sessions');
    renderSessions(d.sessions);
  } catch (e) { /* 静默 */ }
}

function switchView(view) {
  state.view = view;
  if (location.hash.slice(1) !== view) history.replaceState(null, '', '#' + view);
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.view === view));
  document.querySelectorAll('.view').forEach((v) => v.classList.toggle('active', v.id === 'view-' + view));
  if (view === 'sessions') loadStream();
  if (view === 'logs') loadLogs();
  if (view === 'persona') { loadPersonaCard(false); loadBans(); loadTraits(); }
  if (view === 'model') { loadLlmConfig(); loadTraces(); }
  if (view === 'skills') loadSkills();
}

function bindEvents() {
  document.querySelectorAll('.tab').forEach((t) => t.addEventListener('click', () => switchView(t.dataset.view)));
  if ($('btn-theme')) {
    $('btn-theme').addEventListener('click', () => {
      const next = state.theme === 'light' ? 'dark' : 'light';
      applyTheme(next);
      toast(next === 'light' ? '已切换至☀️白天模式' : '已切换至🌙夜间模式');
    });
  }
  $('btn-refresh').addEventListener('click', () => { refresh(); refreshSessions(); toast('已刷新'); });
  $('btn-stream-refresh').addEventListener('click', () => { state.lastTurnDetailFp = ''; state.lastStreamFp = ''; loadStream(); });
  if ($('btn-mode-turns')) $('btn-mode-turns').addEventListener('click', () => setSessionViewMode('turns'));
  if ($('btn-mode-archive')) $('btn-mode-archive').addEventListener('click', () => setSessionViewMode('archive'));
  if ($('btn-save-persona-card')) $('btn-save-persona-card').addEventListener('click', savePersonaCard);
  if ($('btn-reconcile-persona')) $('btn-reconcile-persona').addEventListener('click', reconcilePersonaMemory);
  if ($('btn-trigger-surf')) {
    $('btn-trigger-surf').addEventListener('click', async () => {
      const st = $('surf-status');
      if (st) st.textContent = '正在去B站/梗百科冲浪…';
      try {
        await api('/api/mind/plastic/tune', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key: 'curiosity_rate', delta: 1.0, reason: '手动激发好奇冲浪' }),
        });
        const d = await api('/api/mind/tick', { method: 'POST' });
        if (d.triggered && d.proposal) {
          toast('已完成冲浪：' + (d.proposal.topic_hint || d.proposal.drive_kind));
          if (st) st.textContent = '已完成：' + (d.proposal.topic_hint || d.proposal.drive_kind);
        } else {
          toast('刚活跃过，无需额外冲浪');
          if (st) st.textContent = '刚活跃过（距离上次说话不足5分钟）';
        }
        await refresh();
      } catch (e) { toast('触发冲浪失败：' + e.message, true); }
    });
  }
  if ($('btn-bond-add')) {
    $('btn-bond-add').addEventListener('click', () => {
      const uid = ($('bond-new-uid') && $('bond-new-uid').value.trim()) || '';
      const name = ($('bond-new-name') && $('bond-new-name').value.trim()) || '';
      const sc = ($('bond-new-score') && $('bond-new-score').value.trim()) || '';
      if (!uid || sc === '') { toast('请填写 QQ 号与好感度分数', true); return; }
      saveBondScore(uid, Number(sc), name);
    });
  }
  $('btn-log-refresh').addEventListener('click', loadLogs);
  $('btn-save-llm').addEventListener('click', saveLlmConfig);
  $('btn-reload-llm').addEventListener('click', loadLlmConfig);
  if ($('llm-primary-provider')) {
    $('llm-primary-provider').addEventListener('change', (ev) => {
      const pid = ev.target.value;
      updateModelDatalist(pid, 'llm-primary-models');
      const p = (state.llmProviders || []).find((x) => x.id === pid);
      if (p) {
        if (p.base_url) $('llm-base').value = p.base_url;
        if (p.models && p.models.length && !$('llm-model').value.trim()) $('llm-model').value = p.models[0];
      }
    });
  }
  if ($('llm-fb-add-provider')) {
    $('llm-fb-add-provider').addEventListener('change', (ev) => {
      updateModelDatalist(ev.target.value, 'llm-fb-models');
    });
  }
  if ($('btn-add-fallback')) {
    $('btn-add-fallback').addEventListener('click', () => {
      const pid = ($('llm-fb-add-provider') && $('llm-fb-add-provider').value) || '';
      const model = ($('llm-fb-add-model') && $('llm-fb-add-model').value.trim()) || '';
      if (!model) { toast('请先选择或输入备用模型名称', true); return; }
      state.llmFallbacks.push({ provider: pid, model });
      $('llm-fb-add-model').value = '';
      renderFallbackChain();
      toast('已加入第 ' + state.llmFallbacks.length + ' 顺位备用模型（点击下方保存生效）');
    });
  }
  if ($('btn-add-provider')) {
    $('btn-add-provider').addEventListener('click', () => {
      const id = 'provider_' + Math.random().toString(36).slice(2, 8);
      state.llmProviders.push({
        id,
        display_name: '新模型服务商',
        base_url: 'https://api.openai.com/v1',
        api_key_masked: '',
        models: ['gpt-4o-mini'],
      });
      renderProvidersList();
      populateProviderSelects($('llm-primary-provider') ? $('llm-primary-provider').value : '');
      toast('已添加服务商卡片，请填写地址、密钥与模型后点击保存');
    });
  }

  $('btn-add-fact').addEventListener('click', async () => {
    const subject = $('fact-subject').value.trim();
    const text = $('fact-text').value.trim();
    if (!subject || !text) return toast('主题和内容都要填', true);
    await api('/api/mind/facts', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subject, fact_text: text, is_locked: true }),
    });
    $('fact-subject').value = ''; $('fact-text').value = '';
    toast('已锁定权威事实');
    refresh();
  });

  $('btn-add-ban').addEventListener('click', async () => {
    const phrase = $('ban-input').value.trim();
    if (!phrase) return;
    await api('/api/mind/bans', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phrase, reason: '控制台手动添加' }),
    });
    $('ban-input').value = '';
    toast('已添加禁令：' + phrase);
    loadBans();
  });

  $('btn-probe').addEventListener('click', async () => {
    const text = $('probe-text').value.trim();
    if (!text) return toast('请输入消息', true);
    $('probe-output').textContent = '运行中…';
    try {
      const d = await api('/api/mind/probe', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, sender_id: $('probe-sender').value.trim(), sender_name: '探针' }),
      });
      $('probe-output').textContent = d.rendered_mind_block;
      $('probe-meta').innerHTML =
        '<div class="row"><span class="lbl">唤醒判定</span><span class="val">' + (d.attention.should_wake ? '<span class="badge ok">会回复</span>' : '<span class="badge muted">静默</span>') + ' ' + esc(d.attention.reason) + '</span></div>' +
        '<div class="row"><span class="lbl">Tier</span><span class="val">' + d.attention.tier + '</span></div>' +
        '<div class="row"><span class="lbl">显著性</span><span class="val">' + d.attention.salience_score + '</span></div>' +
        '<div class="row"><span class="lbl">禁用词</span><span class="val">' + (d.banned_phrases.length ? esc(d.banned_phrases.join('、')) : '无') + '</span></div>';
    } catch (e) {
      $('probe-output').textContent = '探针失败：' + e.message;
      toast('探针失败', true);
    }
  });
}

async function checkConnection() {
  try {
    const rt = await api('/api/mind/runtime');
    const online = rt.qq_online !== false;
    $('dot-ws').className = online ? 'dot ok' : 'dot bad';
    const wakeBadge = (rt.wake_state && rt.wake_state.badge) ? (' · ' + rt.wake_state.badge) : '';
    $('ws-label').textContent = (rt.qq_status || (online ? 'QQ在线' : 'QQ已掉线')) + wakeBadge;
    $('chip-model').textContent = rt.model || '-';
  } catch (e) {
    $('dot-ws').className = 'dot bad';
    $('ws-label').textContent = '控制台连接中断';
  }
}

async function boot() {
  initTheme();
  bindEvents();
  const initial = location.hash.slice(1);
  if (initial && document.getElementById('view-' + initial)) switchView(initial);
  await checkConnection();
  await refresh();
  await refreshSessions();
  await loadUsage();
  await loadTraces();
  if (state.chatKey) await loadStream();
  if (state.view !== 'overview') switchView(state.view);
  state.timer = setInterval(async () => {
    await checkConnection();
    await refresh();
    if (state.view === 'sessions') { await refreshSessions(); await loadStream(); }
    if (state.view === 'logs') await loadLogs();
    if (state.view === 'persona') { await loadBans(); await loadTraits(); }
    if (state.view === 'model') await loadTraces();
    await loadTraces();
    await loadUsage();
  }, 3000);
}

boot();
