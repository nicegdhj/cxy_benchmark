import { create } from 'zustand';

export const useAuthStore = create((set, get) => ({
  token: localStorage.getItem('eval_auth_token') || '',
  setToken: (token) => {
    localStorage.setItem('eval_auth_token', token);
    set({ token });
  },
  clearToken: () => {
    localStorage.removeItem('eval_auth_token');
    set({ token: '' });
  },
}));
