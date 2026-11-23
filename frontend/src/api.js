import {setSession, store} from './store.js';

async function request(path, method = 'GET', data) {
  const headers = {'Content-Type': 'application/json'};
  if (store.session) headers.Authorization = `Bearer ${store.session.access_token}`;
  let response;
  try {
    response = await fetch(`/api${path}`, {method, headers, body: data && JSON.stringify(data)});
  } catch {
    throw new Error('暂时连不上调度接口，请检查连接后重试。');
  }
  const content = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && store.session) setSession(null);
    const detail = content.detail;
    const message = Array.isArray(detail) ? `请核对字段 ${detail[0]?.loc.at(-1) ?? ''} 的格式或取值。` : detail;
    throw new Error(message || '服务暂时不可用，请稍后重试。');
  }
  return content;
}

export const api = {
  signIn: data => request('/auth/login', 'POST', data),
  watch: () => request('/watch'),
  history: reference => request(`/history/${encodeURIComponent(reference)}`),
  register: data => request('/berth-requests', 'POST', data),
  publish: data => request('/tide-windows', 'POST', data),
  revise: (code, data) => request(`/berth-requests/${encodeURIComponent(code)}/schedule`, 'PUT', data),
  assign: (code, data) => request(`/berth-requests/${encodeURIComponent(code)}/tug`, 'PUT', data),
  confirm: code => request(`/berth-requests/${encodeURIComponent(code)}/confirm`, 'POST'),
  report: data => request('/delay-incidents', 'POST', data),
  verify: (code, data) => request(`/delay-incidents/${encodeURIComponent(code)}/margin-review`, 'POST', data),
  dispatch: (code, data) => request(`/delay-incidents/${encodeURIComponent(code)}/dispatch`, 'POST', data),
  close: (code, data) => request(`/delay-incidents/${encodeURIComponent(code)}/close`, 'POST', data),
  retry: code => request(`/delay-incidents/${encodeURIComponent(code)}/retry`, 'POST'),
};
