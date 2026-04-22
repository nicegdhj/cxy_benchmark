import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Cpu, Gavel, ListChecks, FolderKanban,
  Activity, Settings
} from 'lucide-react';

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
      </nav>
      <div className="px-4 py-3 border-t border-gray-200 text-xs text-gray-400">
        v0.1.0
      </div>
    </aside>
  );
}
