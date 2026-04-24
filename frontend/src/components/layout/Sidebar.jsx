import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Cpu, Gavel, ListChecks, FolderKanban,
  Activity, Settings
} from 'lucide-react';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: '仪表盘' },
  { to: '/models', icon: Cpu, label: '评测模型' },
  { to: '/judges', icon: Gavel, label: '打分模型' },
  { to: '/tasks', icon: ListChecks, label: '任务与数据' },
  { to: '/batches', icon: FolderKanban, label: '测评管理' },
  { to: '/jobs', icon: Activity, label: '执行记录' },
  { to: '/settings', icon: Settings, label: '设置' },
];

export function Sidebar() {
  return (
    <aside className="w-56 bg-zinc-900 border-r border-zinc-800 flex flex-col h-screen sticky top-0">
      <div className="px-6 py-4 border-b border-zinc-800">
        <h1 className="text-lg font-bold text-zinc-100">Eval Backend</h1>
        <p className="text-xs text-zinc-500 mt-0.5">评测管理系统</p>
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
                  ? 'bg-primary-600/20 text-primary-400'
                  : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
              }`
            }
          >
            <item.icon size={18} />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="px-4 py-3 border-t border-zinc-800 text-xs text-zinc-600">
        v0.1.0
      </div>
    </aside>
  );
}
