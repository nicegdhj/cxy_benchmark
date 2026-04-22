import { useAuthStore } from '../store/authStore';

export function SettingsPage() {
  const { token, setToken } = useAuthStore();

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-6">设置</h2>
      <div className="card max-w-lg">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-base font-semibold">认证配置</h3>
        </div>
        <div className="px-6 py-4 space-y-4">
          <div>
            <label className="label">Auth Token</label>
            <input
              type="password"
              className="input"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="输入 Bearer Token（若后端配置了鉴权）"
            />
            <p className="mt-1 text-xs text-gray-500">
              若后端未配置 EVAL_BACKEND_AUTH_TOKEN，可留空
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
