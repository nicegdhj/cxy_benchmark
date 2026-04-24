import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { FolderKanban, Activity, CheckCircle, XCircle } from 'lucide-react';

const STATS = [
  { key: 'totalBatches', label: '总批次',  icon: FolderKanban, color: 'text-primary-600', bg: 'bg-primary-50' },
  { key: 'runningJobs',  label: '运行中',  icon: Activity,     color: 'text-amber-600',   bg: 'bg-amber-50'   },
  { key: 'successJobs',  label: '成功',    icon: CheckCircle,  color: 'text-emerald-600', bg: 'bg-emerald-50' },
  { key: 'failedJobs',   label: '失败',    icon: XCircle,      color: 'text-red-600',     bg: 'bg-red-50'     },
];

function roundedTopRect(x, y, w, h, r) {
  if (h <= 0) return '';
  const rr = Math.min(r, h, w / 2);
  return `M${x + rr},${y} h${w - 2 * rr} a${rr},${rr} 0 0 1 ${rr},${rr} v${h - rr} h${-w} v${-(h - rr)} a${rr},${rr} 0 0 1 ${rr},${-rr}z`;
}

function DailyJobsChart({ jobs }) {
  const [tooltip, setTooltip] = useState(null);

  const days = useMemo(() => {
    return Array.from({ length: 14 }, (_, i) => {
      const d = new Date();
      d.setHours(0, 0, 0, 0);
      d.setDate(d.getDate() - (13 - i));
      const next = new Date(d);
      next.setDate(next.getDate() + 1);

      const dayJobs = (jobs || []).filter(j => {
        const t = new Date(j.created_at);
        return t >= d && t < next;
      });

      return {
        date: d,
        success: dayJobs.filter(j => j.status === 'success').length,
        failed:  dayJobs.filter(j => j.status === 'failed').length,
        running: dayJobs.filter(j => j.status === 'running').length,
      };
    });
  }, [jobs]);

  const maxVal = Math.max(...days.map(d => d.success + d.failed + d.running), 1);

  const chartH = 130, barW = 10, gap = 14, paddingL = 32, paddingB = 24, r = 3;
  const svgW = paddingL + days.length * (barW + gap) - gap + 12;
  const svgH = chartH + paddingB + 8;
  const baseY = 8 + chartH;
  const yTicks = [0, Math.round(maxVal / 2), maxVal];

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
      <div className="px-5 py-4 border-b border-gray-50 flex items-center justify-between">
        <div>
          <h3 className="text-[13px] font-semibold text-gray-800">每日任务量</h3>
          <p className="text-[11px] text-gray-400 mt-0.5">最近 14 天</p>
        </div>
        <div className="flex items-center gap-4 text-[11px] text-gray-500">
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full inline-block bg-[#4ade80]" />成功</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full inline-block bg-[#f87171]" />失败</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full inline-block bg-[#60a5fa]" />运行中</span>
        </div>
      </div>
      <div className="px-4 py-5">
        <svg width="100%" viewBox={`0 0 ${svgW} ${svgH}`} style={{ overflow: 'visible' }}>
          {yTicks.map(v => {
            const y = baseY - (v / maxVal) * chartH;
            return (
              <g key={v}>
                <line x1={paddingL} y1={y} x2={svgW - 4} y2={y} stroke="#e8edf3" strokeWidth="1" strokeDasharray={v === 0 ? '' : '3 3'} />
                <text x={paddingL - 6} y={y + 4} textAnchor="end" fontSize="9.5" fill="#b0bec5">{v}</text>
              </g>
            );
          })}

          {days.map((d, i) => {
            const x = paddingL + i * (barW + gap);
            const isToday = i === 13;
            const sH = (d.success / maxVal) * chartH;
            const fH = (d.failed  / maxVal) * chartH;
            const rH = (d.running / maxVal) * chartH;

            const sY = baseY - sH;
            const fY = sY - fH;
            const rY = fY - rH;

            const segs = [];
            if (d.success > 0) segs.push({ y: sY, h: sH, fill: '#4ade80', top: d.failed === 0 && d.running === 0 });
            if (d.failed  > 0) segs.push({ y: fY, h: fH, fill: '#f87171', top: d.running === 0 });
            if (d.running > 0) segs.push({ y: rY, h: rH, fill: '#60a5fa', top: true });

            return (
              <g key={i}
                onMouseEnter={() => setTooltip({ i, d, x: x + barW / 2 })}
                onMouseLeave={() => setTooltip(null)}
                style={{ cursor: 'pointer' }}
              >
                <path d={roundedTopRect(x, baseY - chartH, barW, chartH, r)} fill="#f1f5f9" />
                {segs.map((seg, si) => (
                  <path key={si}
                    d={seg.top ? roundedTopRect(x, seg.y, barW, seg.h, r) : `M${x},${seg.y} h${barW} v${seg.h} h${-barW}z`}
                    fill={seg.fill}
                  />
                ))}
                <text x={x + barW / 2} y={baseY + 15} textAnchor="middle" fontSize="9.5"
                  fill={isToday ? '#0C5CAB' : '#b0bec5'}
                  fontWeight={isToday ? '700' : '400'}>
                  {isToday ? '今天' : `${d.date.getMonth() + 1}/${d.date.getDate()}`}
                </text>
              </g>
            );
          })}

          {tooltip && (() => {
            const rawX = tooltip.x;
            const boxW = 82;
            const tx = Math.max(boxW / 2, Math.min(rawX, svgW - boxW / 2));
            return (
              <g pointerEvents="none">
                <rect x={tx - boxW / 2} y={4} width={boxW} height={60} rx="6" fill="#1e293b" opacity="0.9" />
                <text x={tx} y={18} textAnchor="middle" fontSize="10" fill="#94a3b8">
                  {tooltip.d.date.getMonth() + 1}/{tooltip.d.date.getDate()}
                </text>
                <text x={tx} y={33} textAnchor="middle" fontSize="11" fill="#4ade80">成功 {tooltip.d.success}</text>
                <text x={tx} y={48} textAnchor="middle" fontSize="11" fill="#f87171">失败 {tooltip.d.failed}</text>
                <text x={tx} y={63} textAnchor="middle" fontSize="11" fill="#60a5fa">运行 {tooltip.d.running}</text>
              </g>
            );
          })()}
        </svg>
      </div>
    </div>
  );
}

export function DashboardPage() {
  const { data: batches } = useQuery({ queryKey: ['batches'], queryFn: api.batches.list });
  const { data: jobs } = useQuery({ queryKey: ['jobs'], queryFn: api.jobs.list });

  const values = {
    totalBatches: batches?.length || 0,
    runningJobs:  jobs?.filter(j => j.status === 'running').length || 0,
    successJobs:  jobs?.filter(j => j.status === 'success').length || 0,
    failedJobs:   jobs?.filter(j => j.status === 'failed').length || 0,
  };

  return (
    <div>
      <div className="flex items-start justify-between mb-7">
        <div>
          <h1 className="text-[22px] font-bold text-gray-900 leading-tight">仪表盘</h1>
          <p className="text-sm text-gray-500 mt-0.5">系统评测运行概览</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {STATS.map(s => (
          <div key={s.label} className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 flex items-center gap-4">
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${s.bg}`}>
              <s.icon size={22} className={s.color} />
            </div>
            <div>
              <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">{s.label}</p>
              <p className="text-3xl font-bold text-gray-900 mt-0.5 leading-none">{values[s.key]}</p>
            </div>
          </div>
        ))}
      </div>

      <DailyJobsChart jobs={jobs} />
    </div>
  );
}
