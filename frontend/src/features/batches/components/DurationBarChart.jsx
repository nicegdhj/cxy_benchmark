import { useState, useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export function DurationBarChart({ rows }) {
  const [mode, setMode] = useState('byModel'); // byModel = 多模型 × 多任务(堆叠), byTask = 按任务, singleModel = 单模型
  const [selectedModel, setSelectedModel] = useState(null);

  const models = useMemo(() =>
    [...new Map(rows.filter(r => r.accuracy != null).map(r => [r.model_id, { id: r.model_id, name: r.model_name }])).values()],
    [rows]
  );
  const tasks = useMemo(() =>
    [...new Map(rows.filter(r => r.accuracy != null).map(r => [r.task_id, { id: r.task_id, key: r.task_key }])).values()],
    [rows]
  );

  const chartData = useMemo(() => {
    if (mode === 'byModel') {
      // 每个模型在多个任务上的总耗时
      return models.map(m => {
        const modelRows = rows.filter(r => r.model_id === m.id);
        const totalDuration = modelRows.reduce((sum, r) => sum + (r.duration_sec || 0), 0);
        return { name: m.name, duration: Math.round(totalDuration), count: modelRows.length };
      }).filter(d => d.duration > 0).sort((a, b) => b.duration - a.duration);
    }
    if (mode === 'byTask') {
      // 每个任务的总耗时
      return tasks.map(t => {
        const taskRows = rows.filter(r => r.task_id === t.id);
        const totalDuration = taskRows.reduce((sum, r) => sum + (r.duration_sec || 0), 0);
        return { name: t.key, duration: Math.round(totalDuration), count: taskRows.length };
      }).filter(d => d.duration > 0).sort((a, b) => b.duration - a.duration);
    }
    if (mode === 'singleModel' && selectedModel) {
      // 单模型在各任务上的耗时
      return tasks.map(t => {
        const row = rows.find(r => r.model_id === selectedModel && r.task_id === t.id);
        return { name: t.key, duration: Math.round(row?.duration_sec || 0) };
      }).filter(d => d.duration > 0);
    }
    return [];
  }, [mode, selectedModel, rows, models, tasks]);

  function formatDuration(seconds) {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">分析维度:</span>
          <select className="input py-1 text-sm" value={mode} onChange={e => setMode(e.target.value)}>
            <option value="byModel">多模型总耗时</option>
            <option value="byTask">多任务总耗时</option>
            <option value="singleModel">单模型 × 多任务</option>
          </select>
        </div>
        {mode === 'singleModel' && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">选择模型:</span>
            <select className="input py-1 text-sm" value={selectedModel || ''} onChange={e => setSelectedModel(Number(e.target.value))}>
              <option value="">请选择</option>
              {models.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
          </div>
        )}
      </div>

      {chartData.length > 0 ? (
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} label={{ value: '秒', angle: -90, position: 'insideLeft', style: { fontSize: 12 } }} />
              <Tooltip
                formatter={(value) => [formatDuration(value), '耗时']}
                contentStyle={{ borderRadius: 8, border: '1px solid #e5e7eb' }}
              />
              <Bar dataKey="duration" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="h-80 flex items-center justify-center text-gray-400 bg-gray-50 rounded-lg">
          <p>请选择维度以查看耗时图表</p>
        </div>
      )}
    </div>
  );
}
