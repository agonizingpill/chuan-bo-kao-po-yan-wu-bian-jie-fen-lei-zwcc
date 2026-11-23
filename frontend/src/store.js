export const roles = {operator: '值班调度员', supervisor: '调度主管', viewer: '只读观察员'};
export const requestStates = {requested: '待核验', tug_reserved: '已预约拖轮', confirmed: '已确认', completed: '已完成'};
export const incidentStates = {queued: '待计算', failed: '计算失败', margin_review: '待人工复核', ready: '待发布指令', actioned: '待复盘', closed: '已结案'};
export const decisions = {routine: '常规跟踪', priority: '优先处置'};
export const actions = {monitor: '继续跟踪', standby: '拖轮待命', retime: '通知改期'};

function restoreSession() {
  try { return JSON.parse(sessionStorage.getItem('berth-session')); }
  catch { return null; }
}

export const store = {session: restoreSession(), data: null, history: [], error: '', busy: false};
export const supervisor = () => store.session?.role === 'supervisor';
export const canWrite = () => store.session && store.session.role !== 'viewer';

export function setSession(session) {
  store.session = session;
  store.data = null;
  if (session) sessionStorage.setItem('berth-session', JSON.stringify(session));
  else sessionStorage.removeItem('berth-session');
}
