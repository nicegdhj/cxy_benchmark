import { useState, useMemo } from 'react';
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer, Tooltip, Legend } from 'recharts';

const CHART_COLORS = {
  grid: '#27272a',
  tick: '#71717a',
  tooltip: { bg: '#18181b', border: '#3f3f46', text: '#f4f4f5' },
};

const colors = ['#0C5CAB', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4'];

export function ModelTaskRadarChart({ rows }) {
  const [selectedModels, setSelectedModels] = useState([]);

  const models = useMemo(() =>
    [...new Map(rows.filter(r => r.accuracy != null).map(r => [r.model_id, { id: r.model_id, name: r.model_name }])).values()],
    [rows]
  );
  const tasks = useMemo(() =>
    [...new Map(rows.filter(r => r.accuracy != null).map(r => [r.task_id, { id: r.task_id, key: r.task_key }])).values()],
    [rows]
  );

  const chartData = useMemo(() => {
    return tasks.map(t => {
      const point = { task: t.key };
      for (const m of models) {
        const row = rows.find(r => r.model_id === m.id && r.task_id === t.id);
        point[m.name] = row?.accuracy ?? 0;
      }
      return point;
    });
  }, [rows, models, tasks]);

  function toggleModel(id) {
    setSelectedModels(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  }

  const activeModels = selectedModels.length > 0
    ? models.filter(m => selectedModels.includes(m.id))
    : models.slice(0, 3);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm text-zinc-400">对比模型:</span>
        {models.map(m => (
          <button
            key={m.id}
            onClick={() => toggleModel(m.id)}
            className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
              (selectedModels.length === 0 ? models.indexOf(m) < 3 : selectedModels.includes(m.id))
                ? 'bg-primary-600/30 text-primary-300 ring-1 ring-primary-600/50'
                : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-300'
            }`}
          >
            {m.name}
          </button>
        ))}
        <span className="text-xs text-zinc-600 ml-2">点击切换显示</span>
      </div>

      <div className="h-96">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={chartData} margin={{ top: 20, right: 80, bottom: 20, left: 80 }}>
            <PolarGrid stroke={CHART_COLORS.grid} />
            <PolarAngleAxis dataKey="task" tick={{ fontSize: 11, fill: CHART_COLORS.tick }} />
            <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 10, fill: CHART_COLORS.tick }} />
            {activeModels.map((m, i) => (
              <Radar
                key={m.id}
                name={m.name}
                dataKey={m.name}
                stroke={colors[i % colors.length]}
                fill={colors[i % colors.length]}
                fillOpacity={0.15}
                strokeWidth={2}
              />
            ))}
            <Tooltip
              formatter={(value, name) => [`${value.toFixed(1)}%`, name]}
              contentStyle={{ borderRadius: 8, border: `1px solid ${CHART_COLORS.tooltip.border}`, backgroundColor: CHART_COLORS.tooltip.bg, color: CHART_COLORS.tooltip.text }}
            />
            <Legend wrapperStyle={{ color: CHART_COLORS.tick, fontSize: 12 }} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
