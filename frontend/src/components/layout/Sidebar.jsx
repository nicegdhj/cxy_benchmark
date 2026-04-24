import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Cpu, Gavel, ListChecks, FolderKanban,
  Activity, Settings, Users, LogOut, Shield
} from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../lib/api';
import { userDisplay } from '../../lib/userDisplay';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: '仪表盘' },
  { to: '/models', icon: Cpu, label: '模型管理' },
  { to: '/judges', icon: Gavel, label: '打分模型' },
  { to: '/tasks', icon: ListChecks, label: '任务与数据' },
  { to: '/batches', icon: FolderKanban, label: '批次评测' },
  { to: '/jobs', icon: Activity, label: '执行记录' },
  { to: '/settings', icon: Settings, label: '设置' },
];

export function Sidebar() {
  const { user, isAdmin, clearSession } = useAuthStore();

  async function handleLogout() {
    try { await api.auth.logout(); } catch {}
    clearSession();
    window.location.href = '/login';
  }

  return (
    <aside className="w-56 bg-white border-r border-gray-200 flex flex-col h-screen sticky top-0">
      <div className="px-6 py-4 border-b border-gray-200">
        <h1 className="text-lg font-bold text-gray-900">Eval Backend</h1>
        <p className="text-xs text-gray-500 mt-0.5">评测管理系统</p>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-700 hover:bg-gray-50'
              }`
            }
          >
            <item.icon size={18} />
            {item.label}
          </NavLink>
        ))}

        {isAdmin() && (
          <NavLink
            to="/users"
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-700 hover:bg-gray-50'
              }`
            }
          >
            <Users size={18} />
            用户管理
          </NavLink>
        )}
      </nav>

      <div className="px-4 py-3 border-t border-gray-200">
        {user && (
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
              <Shield size={14} className="text-primary-600" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">{userDisplay(user)}</p>
              <p className="text-xs text-gray-500">{user.role === 'admin' ? '管理员' : user.role === 'operator' ? '操作员' : '访客'}</p>
            </div>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
        >
          <LogOut size={16} />
          退出登录
        </button>
      </div>
    </aside>
  );
}
