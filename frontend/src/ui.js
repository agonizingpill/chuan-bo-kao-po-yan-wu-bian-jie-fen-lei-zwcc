const entities = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'};
export const esc = (value = '') => String(value ?? '').replace(/[&<>"']/g, char => entities[char]);
export const clock = value => value ? value.slice(11, 16) : '—';
export const portDate = value => value ? `${value.slice(0, 10)} ${clock(value)}` : '—';
export const interval = (start, end) => `${portDate(start)} – ${start?.slice(0, 10) === end?.slice(0, 10) ? clock(end) : portDate(end)}`;
export const timeInput = value => value?.slice(0, 16);
export const selected = (a, b) => a === b ? 'selected' : '';

export function pill(state, labels) {
  return `<span class="pill ${esc(state)}"><i></i>${esc(labels[state] || state)}</span>`;
}

export function field(label, name, type = 'text', value = '', args = '') {
  return `<label>${esc(label)}<input required type="${esc(type)}" name="${esc(name)}" value="${esc(value)}" ${args}></label>`;
}

export function selectField(label, name, choices, value = '') {
  return `<label>${esc(label)}<select required name="${esc(name)}"><option value="">请选择</option>${choices.map(([key, caption]) =>
    `<option ${selected(key, value)} value="${esc(key)}">${esc(caption)}</option>`).join('')}</select></label>`;
}

export function notes(label, name, hint) {
  return `<label>${esc(label)}<textarea required name="${name}" rows="2" minlength="5" maxlength="300" placeholder="${esc(hint)}"></textarea></label>`;
}

export function form(action, code, body, label, kind = '') {
  return `<form data-action="${action}" data-code="${esc(code)}" class="operation ${kind}">${body}<div class="form-end"><button class="primary" type="submit">${label}</button><span class="form-error" role="alert"></span></div></form>`;
}

export const blank = (caption, help) => `<div class="empty"><strong>${esc(caption)}</strong><p>${esc(help)}</p></div>`;
export const title = (label, hint, aside = '') => `<header class="page-heading"><div><h1>${label}</h1><p>${hint}</p></div>${aside}</header>`;

export const eventNames = {
  REQUEST_FILED: '登记申请', SCHEDULE_REVISED: '调整引航计划', TUG_RESERVED: '预约拖轮', BERTH_CONFIRMED: '确认靠泊',
  INSUFFICIENT_TIDE: '潮窗核验不通过', TUG_CONFLICT: '拖轮冲突', BERTH_CONFLICT: '泊位作业冲突', TUG_REQUIRED: '缺拖轮预约',
  INCIDENT_QUEUED: '登记现场延误', INCIDENT_REQUEUED: '重试模型', MODEL_FAILED: '模型计算失败', MODEL_CLASSIFIED: '模型分类',
  MARGIN_REVIEWED: '主管签署分类', MARGIN_REVIEW_REQUIRED: '间隔带未复核', ACTION_ISSUED: '发布调度指令', REVIEW_CLOSED: '完成复盘',
  PRIORITY_ACTION_REQUIRED: '处置级别不符', ALL_FAST_TIME: '复盘时间不符',
};

export function journal(events) {
  if (!events.length) return blank('暂无交接记录', '本次申请的确认、拒绝和改期会显示在这里。');
  return `<ol class="journal">${events.map(e => `<li><time>${esc(portDate(e.port_time))}</time><div><strong>${esc(eventNames[e.event] || e.event)}</strong> <span>${esc(e.actor)}</span><p>${esc(e.note)}</p></div></li>`).join('')}</ol>`;
}
