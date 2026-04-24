import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Cpu, Gavel, ListChecks, FolderKanban,
  Activity, Settings, Users, LogOut
} from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../lib/api';
import { userDisplay } from '../../lib/userDisplay';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: '仪表盘' },
  { to: '/models', icon: Cpu, label: '评测模型' },
  { to: '/judges', icon: Gavel, label: '打分模型' },
  { to: '/tasks', icon: ListChecks, label: '任务与数据' },
  { to: '/batches', icon: FolderKanban, label: '测评管理' },
  { to: '/jobs', icon: Activity, label: '执行记录' },
  { to: '/settings', icon: Settings, label: '设置' },
];

const navLinkClass = ({ isActive }) =>
  `flex items-center gap-2.5 px-3 py-2.5 text-[13px] font-medium transition-all rounded-lg w-full ${
    isActive ? 'nav-active' : 'nav-inactive'
  }`;

const navLinkStyle = ({ isActive }) =>
  isActive
    ? { background: '#eff6ff', color: '#0C5CAB', borderLeft: '2px solid #0C5CAB', paddingLeft: '10px', borderRadius: '8px' }
    : { color: '#5a7291', borderLeft: '2px solid transparent', paddingLeft: '10px' };

export function Sidebar() {
  const { user, isAdmin, clearSession } = useAuthStore();

  async function handleLogout() {
    try { await api.auth.logout(); } catch {}
    clearSession();
    window.location.href = '/login';
  }

  return (
    <aside className="w-[220px] flex-shrink-0 h-screen sticky top-0 flex flex-col bg-white" style={{ borderRight: '1px solid #e8edf3' }}>
      {/* Brand */}
      <div className="px-5 pt-5 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: 'linear-gradient(135deg,#1a6fd4 0%,#0C5CAB 100%)', boxShadow: '0 2px 8px rgba(12,92,171,.3)' }}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <circle cx="7" cy="7" r="2.5" fill="white"/>
              <path d="M7 1v2M7 11v2M1 7h2M11 7h2M2.93 2.93l1.41 1.41M9.66 9.66l1.41 1.41M2.93 11.07l1.41-1.41M9.66 4.34l1.41-1.41" stroke="white" strokeWidth="1.2" strokeLinecap="round"/>
            </svg>
          </div>
          <div>
            <div className="text-[13px] font-bold leading-none" style={{ color: '#0f1a2e' }}>Eval Backend</div>
            <div className="text-[10px] mt-0.5" style={{ color: '#8fa3bc' }}>垂类大模型评测系统</div>
          </div>
        </div>
      </div>

      <div className="mx-4 mb-3" style={{ height: 1, background: '#eef1f6' }} />

      {/* Nav */}
      <nav className="flex-1 px-2.5 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === '/'} className={navLinkClass} style={navLinkStyle}>
            <item.icon size={15} />
            {item.label}
          </NavLink>
        ))}

        {isAdmin() && (
          <NavLink to="/users" className={navLinkClass} style={navLinkStyle}>
            <Users size={15} />
            用户管理
          </NavLink>
        )}
      </nav>

      {/* Bottom */}
      <div className="px-2.5 pb-4 mt-2">
        <div className="mx-1 mb-3" style={{ height: 1, background: '#eef1f6' }} />
        {user && (
          <div className="px-3 mb-2">
            <p className="text-[12px] font-semibold truncate" style={{ color: '#0f1a2e' }}>{userDisplay(user)}</p>
            <p className="text-[11px]" style={{ color: '#8fa3bc' }}>
              {user.role === 'admin' ? '管理员' : user.role === 'operator' ? '操作员' : '访客'}
            </p>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-[12px] font-medium transition-all"
          style={{ color: '#5a7291' }}
          onMouseEnter={e => { e.currentTarget.style.background = '#fff0f0'; e.currentTarget.style.color = '#d93025'; }}
          onMouseLeave={e => { e.currentTarget.style.background = ''; e.currentTarget.style.color = '#5a7291'; }}
        >
          <LogOut size={14} />
          退出登录
        </button>
      </div>
    </aside>
  );
}
