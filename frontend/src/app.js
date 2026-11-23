import {api} from './api.js';
import {incidents, reviews} from './incidents.js';
import {resources, schedule} from './planning.js';
import {roles, setSession, store} from './store.js';
import {blank, esc, field} from './ui.js';

const root = document.querySelector('#root');
const notice = document.querySelector('#notice');
const sections = {schedule: ['靠泊申请', schedule], resources: ['潮汐与拖轮', resources], incidents: ['延误边界', incidents], reviews: ['调度复盘', reviews]};
const feedback = {register: '申请已登记', publish: '潮窗已发布', revise: '改期已保存', assign: '拖轮已预约', confirm: '靠泊已确认', report: '现场事件已入队', verify: '人工分类已签署', dispatch: '值班指令已发布', close: '复盘已结案', retry: '计算已重新入队'};
let noticeTimer;
let revision = 0;

function route() {
  const [section, reference] = location.hash.slice(1).split('/');
  return [Object.hasOwn(sections, section) ? section : 'schedule', reference || ''];
}

function login() {
  return `<main class="entry"><section class="entry-chart"><div class="chart-grid" aria-hidden="true"><i></i><i></i><i></i><b></b></div>
    <div class="entry-copy"><p class="mono reference">EAST CAPE / BERTH CONTROL</p><h1>东岬港<br>靠泊调度</h1><p>潮窗核验 · 拖轮排班 · 延误处置</p></div></section>
    <section class="credential"><p class="reference mono">港区时间 UTC+08</p><h2>值班登录</h2>
    <form data-action="login" class="operation">${field('岗位账号', 'username', 'text', '', 'autocomplete="username"')}${field('口令', 'password', 'password', '', 'autocomplete="current-password"')}
    <button type="submit" class="primary">进入调度台</button><p class="form-error" role="alert">${esc(store.error)}</p></form>
    <div class="entry-help"><b>演示账号</b><p>operator / supervisor / viewer</p><p>统一口令 <code>Harbor1074!</code></p></div></section></main>`;
}

function render() {
  if (!store.session) { root.innerHTML = login(); return; }
  const [section, code] = route();
  const data = store.data;
  root.innerHTML = `<header class="top"><a href="#schedule" class="brand"><span aria-hidden="true">◒</span><b>东岬港调度台<small>EAST CAPE / PORT OPERATIONS</small></b></a>
    <nav aria-label="业务导航">${Object.entries(sections).map(([key, [label]]) => `<a href="#${key}" ${key === section ? 'aria-current="page"' : ''}>${label}</a>`).join('')}</nav>
    <div class="watch-user"><span>${esc(roles[store.session.role])}<small>${esc(store.session.username)}</small></span><button type="button" class="text-button" data-click="logout">退出</button></div></header>
    <main class="workspace">${data ? sections[section][1](code) : blank('正在读取交班数据', '等待调度接口返回。')}
    ${store.error ? `<p class="warning" role="alert">${esc(store.error)} <button class="text-button" data-click="refresh">重新读取</button></p>` : ''}</main>
    <footer class="watch-foot"><span>东岬港 · 引航协调组</span><span>演示班次 / UTC+08</span></footer>`;
}

async function refresh() {
  const current = ++revision;
  if (!store.session) { render(); return; }
  try {
    const [section, code] = route();
    const data = await api.watch();
    const wantsHistory = code && ['schedule', 'reviews'].includes(section);
    const history = wantsHistory ? await api.history(code) : [];
    if (current !== revision) return;
    Object.assign(store, {data, history, error: ''});
  } catch (error) {
    if (current !== revision) return;
    store.error = error.message;
  }
  render();
}

function toast(message) {
  notice.textContent = message;
  notice.classList.add('visible');
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => notice.classList.remove('visible'), 3500);
}

root.addEventListener('submit', async event => {
  const form = event.target;
  const {action, code} = form.dataset;
  if (!action) return;
  event.preventDefault();
  if (store.busy) return;
  store.busy = true;
  const button = form.querySelector('button[type="submit"]');
  const error = form.querySelector('.form-error');
  button.disabled = true;
  error.textContent = '';
  const payload = Object.fromEntries(new FormData(form));
  try {
    if (action === 'login') {
      setSession(await api.signIn(payload));
      history.replaceState(null, '', '#schedule');
    } else {
      await (['register', 'publish', 'report'].includes(action) ? api[action](payload) : api[action](code, payload));
      const target = {register: 'schedule', publish: 'resources', report: 'incidents'}[action];
      if (target) history.replaceState(null, '', `#${target}/${encodeURIComponent(payload.code)}`);
      toast(feedback[action]);
    }
    await refresh();
  } catch (failure) {
    if (!store.session && action !== 'login') { store.error = failure.message; render(); }
    else error.textContent = failure.message;
  } finally {
    store.busy = false;
    button.disabled = false;
  }
});

root.addEventListener('click', event => {
  const action = event.target.closest('[data-click]')?.dataset.click;
  if (action === 'logout' && !store.busy) {
    setSession(null);
    Object.assign(store, {history: [], error: ''});
    clearTimeout(noticeTimer);
    notice.classList.remove('visible');
    refresh();
  }
  if (action === 'refresh') refresh();
});

root.addEventListener('change', event => {
  if (!event.target.matches('form[data-action="register"] select[name="berth_code"]')) return;
  const windowSelect = event.target.form.elements.window_code;
  windowSelect.value = '';
  const allowed = new Set(store.data.windows.filter(w => w.berth_code === event.target.value).map(w => w.code));
  for (const option of windowSelect.options) option.hidden = option.value && !allowed.has(option.value);
});

window.addEventListener('hashchange', refresh);
setInterval(() => {
  const [section, code] = route();
  const incident = store.data?.incidents.find(item => item.code === code);
  if (section === 'incidents' && incident?.state === 'queued' && !store.busy) refresh();
}, 1500);
render();
refresh();
