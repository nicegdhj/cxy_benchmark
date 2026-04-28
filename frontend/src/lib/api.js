import { useAuthStore } from '../store/authStore';

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1';

function getToken() {
  return localStorage.getItem('eval_auth_token') || '';
}

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    ...options.headers,
  };

  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    useAuthStore.getState().clearSession();
    window.location.href = '/login';
    return;
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  health: () => request('/health'),

  auth: {
    login: (data) => request('/auth/login', { method: 'POST', body: JSON.stringify(data) }),
    logout: () => request('/auth/logout', { method: 'POST' }),
    me: () => request('/auth/me'),
    changePassword: (data) => request('/auth/change-password', { method: 'POST', body: JSON.stringify(data) }),
  },

  users: {
    list: () => request('/users'),
    get: (id) => request(`/users/${id}`),
    create: (data) => request('/users', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => request(`/users/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    del: (id) => request(`/users/${id}`, { method: 'DELETE' }),
    resetPassword: (id, data) => request(`/users/${id}/reset-password`, { method: 'POST', body: JSON.stringify(data) }),
  },

  models: {
    list: () => request('/models'),
    get: (id) => request(`/models/${id}`),
    create: (data) => request('/models', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => request(`/models/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    del: (id) => request(`/models/${id}`, { method: 'DELETE' }),
  },

  judges: {
    list: () => request('/judges'),
    get: (id) => request(`/judges/${id}`),
    create: (data) => request('/judges', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => request(`/judges/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    del: (id) => request(`/judges/${id}`, { method: 'DELETE' }),
  },

  tasks: {
    list: () => request('/tasks'),
    get: (id) => request(`/tasks/${id}`),
    datasets: (taskId) => request(`/tasks/${taskId}/datasets`),
    uploadDataset: (taskId, formData) => request(`/tasks/${taskId}/datasets`, {
      method: 'POST',
      body: formData,
      headers: {}, // fetch will set Content-Type with boundary for FormData
    }),
  },

  batches: {
    list: () => request('/batches'),
    get: (id) => request(`/batches/${id}`),
    create: (data) => request('/batches', { method: 'POST', body: JSON.stringify(data) }),
    report: (id, rev) => request(`/batches/${id}/report${rev ? `?rev=${rev}` : ''}`),
    revisions: (id) => request(`/batches/${id}/revisions`),
    rerun: (id, data) => request(`/batches/${id}/rerun`, { method: 'POST', body: JSON.stringify(data) }),
    clone: (id, data = {}) => request(`/batches/${id}/clone`, { method: 'POST', body: JSON.stringify(data) }),
  },

  jobs: {
    list: (params = {}) => {
      const qs = new URLSearchParams(params).toString();
      return request(`/jobs${qs ? `?${qs}` : ''}`);
    },
    get: (id) => request(`/jobs/${id}`),
    log: (id) => request(`/jobs/${id}/log`),
    cancel: (id) => request(`/jobs/${id}/cancel`, { method: 'POST' }),
  },

  predictions: {
    get: (id) => request(`/predictions/${id}`),
  },

  evaluations: {
    get: (id) => request(`/evaluations/${id}`),
  },
};

// Transform helper: flatten BatchReport rows into matrix
export function transformReportToMatrix(rows) {
  const models = [];
  const tasks = [];
  const modelMap = new Map();
  const taskMap = new Map();

  for (const row of rows) {
    if (!modelMap.has(row.model_id)) {
      modelMap.set(row.model_id, models.length);
      models.push({ id: row.model_id, name: row.model_name });
    }
    if (!taskMap.has(row.task_id)) {
      taskMap.set(row.task_id, tasks.length);
      tasks.push({ id: row.task_id, key: row.task_key });
    }
  }

  const matrix = Array(models.length).fill(null).map(() => Array(tasks.length).fill(null));

  for (const row of rows) {
    const mi = modelMap.get(row.model_id);
    const ti = taskMap.get(row.task_id);
    matrix[mi][ti] = row;
  }

  return { models, tasks, matrix };
}
