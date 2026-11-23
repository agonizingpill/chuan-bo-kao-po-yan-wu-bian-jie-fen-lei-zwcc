import {canWrite, requestStates, store, supervisor} from './store.js';
import {blank, clock, esc, field, form, interval, journal, pill, portDate, selectField, timeInput, title} from './ui.js';

const windowsFor = berth => store.data.windows.filter(w => !berth || w.berth_code === berth)
  .map(w => [w.code, `${w.code} · ${w.berth_code} · ${clock(w.starts_at)}–${clock(w.ends_at)}`]);
const berthChoices = () => store.data.berths.map(b => [b.code, `${b.code} · ${b.label}`]);

function timeline() {
  const requests = store.data.requests;
  const windows = store.data.windows;
  if (!windows.length) return blank('暂无潮窗', '主管可以在潮汐与拖轮页登记水文通告。');
  const hour = 3600000;
  const stamp = time => Date.parse(`${time}Z`);
  const start = Math.floor(Math.min(...windows.map(w => stamp(w.starts_at)), ...requests.map(r => stamp(r.eta))) / hour) * hour;
  const end = Math.ceil(Math.max(...windows.map(w => stamp(w.ends_at)), ...requests.map(r => stamp(r.ends_at))) / hour) * hour;
  const total = end - start;
  const ticks = Math.min(7, Math.ceil(total / hour) + 1);
  const range = (a, b) => `--left:${(stamp(a) - start) * 100 / total}%;--width:${(stamp(b) - stamp(a)) * 100 / total}%`;
  const marks = Array.from({length: ticks}, (_, index) => {
    const progress = index / (ticks - 1);
    const time = clock(new Date(start + progress * total).toISOString());
    return `<span style="left:${progress * 100}%">${time}</span>`;
  }).join('');
  return `<div class="plot"><div class="plot-ruler"><span>泊位</span><div>${marks}</div></div>${store.data.berths.map(b =>
      `<div class="plot-row"><strong>${esc(b.code)}</strong><div class="lane">${windows.filter(w => w.berth_code === b.code).map(w =>
          `<a class="tide-bar" href="#resources/${esc(w.code)}" style="${range(w.starts_at, w.ends_at)}" title="${esc(w.code)} ${esc(interval(w.starts_at, w.ends_at))}">${esc(w.code)}</a>`).join('')}
        ${requests.filter(r => r.berth_code === b.code).map(r => `<a href="#schedule/${esc(r.code)}" class="ship-bar ${r.tide_warning ? 'blocked' : ''} ${esc(r.state)}" style="${range(r.eta, r.ends_at)}" title="${esc(r.vessel)} ${esc(r.code)}">${esc(r.code)}</a>`).join('')}</div></div>`).join('')}
    <div class="legend"><span class="legend-tide">水文通告潮窗</span><span class="legend-ship">操纵时段</span><span class="legend-block">潮窗待调整</span></div></div>`;
}

function newRequest() {
  if (!canWrite()) return '';
  return `<details class="paper-fold"><summary>登记靠泊申请</summary>${form('register', '', `
    <div class="form-grid">${field('申请编号', 'code', 'text', '', 'maxlength="32" placeholder="BR-414"')}${field('船名', 'vessel')}
    ${selectField('泊位', 'berth_code', berthChoices())}${selectField('通告潮窗', 'window_code', windowsFor())}
    ${field('计划引航', 'eta', 'datetime-local')}${field('满载吃水 / m', 'draft_m', 'number', '', 'step="0.1" min="0.1" max="25"')}
    ${field('操纵时长 / 分钟', 'maneuver_minutes', 'number', 45, 'min="15" max="180"')}</div>`, '提交靠泊申请')}</details>`;
}

function requestDetail(request) {
  if (!request) return blank('选择一条靠泊申请', '在潮窗图或班次清单点击申请编号，核对吃水、操纵时段和拖轮。');
  const editable = canWrite() && ['requested', 'tug_reserved'].includes(request.state);
  const win = store.data.windows.find(w => w.code === request.window_code);
  return `<header class="subhead"><div><div class="mono reference">${esc(request.code)} / ${esc(request.berth_code)}</div><h2>${esc(request.vessel)}</h2></div>${pill(request.state, requestStates)}</header>
  <dl class="measurements"><div><dt>操纵时段</dt><dd>${clock(request.eta)}–${clock(request.ends_at)}</dd></div><div><dt>吃水 / 上限</dt><dd>${request.draft_m} / ${win.max_draft_m} m</dd></div><div><dt>拖轮预约</dt><dd>${esc(request.tug_code || '待分配')}</dd></div></dl>
  <p class="${request.tide_warning ? 'warning' : 'clearance'}">${esc(request.tide_warning || `潮窗 ${win.code} 覆盖作业，结束后余量 ${request.tide_reserve_min} 分钟。`)}</p>
  ${editable ? `<h3>修订引航计划</h3>${form('revise', request.code, `<div class="form-grid">
    ${selectField('泊位潮窗', 'window_code', windowsFor(request.berth_code), request.window_code)}${field('计划引航', 'eta', 'datetime-local', timeInput(request.eta))}
    ${field('操纵时长 / 分钟', 'maneuver_minutes', 'number', request.maneuver_minutes, 'min="15" max="180"')}</div>`, '保存改期')}
    <h3>拖轮预约</h3>${form('assign', request.code, selectField('选择拖轮', 'tug_code', store.data.tugs.map(t => [t.code, `${t.code} · ${t.label}`]), request.tug_code), '预约拖轮')}
    ${supervisor() ? form('confirm', request.code, '', '核验并确认靠泊', 'confirm') : '<p class="muted">调度主管负责最终确认。</p>'}` : ''}
  <h3>作业交接</h3>${journal(store.history)}`;
}

export function schedule(code) {
  const request = store.data.requests.find(r => r.code === code);
  return `${title('靠泊申请', '核对潮汐通告和拖轮占用，确认本班次引航计划。', '<a class="quiet" href="#resources">查看潮窗与拖轮</a>')}
  <div class="planning-grid"><div><section class="panel schedule-plot"><div class="section-head"><h2>泊位时刻图</h2><span>港区时间 UTC+08</span></div>${timeline()}</section>
  <section class="panel"><div class="section-head"><h2>班次清单</h2><span>${store.data.requests.length} 条申请</span></div>
    <div class="table-wrap"><table><thead><tr><th>申请 / 船名</th><th>泊位</th><th>计划引航</th><th>拖轮</th><th>进度</th></tr></thead><tbody>${store.data.requests.map(r =>
      `<tr class="${r.code === code ? 'active-row' : ''}"><td><a href="#schedule/${esc(r.code)}">${esc(r.code)}</a><small>${esc(r.vessel)}</small></td><td>${esc(r.berth_code)}</td><td>${esc(portDate(r.eta))}</td><td>${esc(r.tug_code || '—')}</td><td>${pill(r.state, requestStates)}</td></tr>`).join('')}</tbody></table></div>${newRequest()}</section></div>
  <aside class="panel inspector">${requestDetail(request)}</aside></div>`;
}

export function resources(code) {
  const available = store.data.windows;
  const tugRows = store.data.tugs.map(tug => {
    const calendar = store.data.assignments.filter(a => a.tug_code === tug.code);
    return `<article class="tug-line"><div><div class="reference mono">${esc(tug.code)} / ${tug.bollard_pull_t} t</div><h3>${esc(tug.label)}</h3></div><ul>${calendar.length ? calendar.map(a =>
      `<li class="${a.released_at ? 'released' : ''}"><a href="#schedule/${esc(a.request_code)}">${esc(a.request_code)}</a> <time>${esc(interval(a.starts_at, a.ends_at))}</time>${a.released_at ? ' · 已释放' : ' · 已占用'}</li>`).join('') : '<li>暂无预约</li>'}</ul></article>`;
  }).join('');
  return `${title('潮汐与拖轮', '以水文来源发布潮窗，按拖轮追踪各泊位的操纵占用。')}
  <div class="planning-grid"><section class="panel"><div class="section-head"><h2>水文通告</h2><span>港区时间 UTC+08</span></div>
    ${available.length ? `<div class="tide-ledger">${available.map(w => `<article class="tide-entry ${code === w.code ? 'selected-entry' : ''}"><strong class="mono">${esc(w.code)}</strong><div><b>${esc(w.berth_code)} · ${esc(interval(w.starts_at, w.ends_at))}</b><small>${esc(w.bulletin)}</small></div><div class="depth mono">${w.max_draft_m} m<small>吃水上限</small></div></article>`).join('')}</div>` : blank('暂无水文通告', '登记泊位、时间区间及最大吃水。')}
    ${supervisor() ? `<details class="paper-fold"><summary>发布补充潮窗</summary>${form('publish', '', `<div class="form-grid">
      ${field('潮窗编号', 'code')}${selectField('泊位', 'berth_code', berthChoices())}${field('开始', 'starts_at', 'datetime-local')}${field('结束', 'ends_at', 'datetime-local')}
      ${field('吃水上限 / m', 'max_draft_m', 'number', '', 'step="0.1" min="0.1" max="25"')}${field('水文通告来源', 'bulletin')}</div>`, '发布潮窗')}</details>` : ''}</section>
  <section class="panel inspector"><div class="section-head"><h2>拖轮占用簿</h2><span>各泊位共用</span></div>${tugRows}</section></div>`;
}
