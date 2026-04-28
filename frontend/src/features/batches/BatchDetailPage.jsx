import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, transformReportToMatrix } from '../../lib/api';
import { Card, CardHeader, CardBody } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { Modal } from '../../components/ui/Modal';
import { ArrowLeft, BarChart3, GitBranch, RotateCcw, Table, User } from 'lucide-react';
import { userDisplay } from '../../lib/userDisplay';
import { useNavigate } from 'react-router-dom';
import { AccuracyBarChart } from './components/AccuracyBarChart';
import { DurationBarChart } from './components/DurationBarChart';
import { ModelTaskRadarChart } from './components/ModelTaskRadarChart';

const TABS = [
  { id: 'matrix', label: '战报矩阵', icon: Table },
  { id: 'charts', label: '图表分析', icon: BarChart3 },
  { id: 'revisions', label: '历史版本', icon: GitBranch },
  { id: 'rerun', label: '局部重跑', icon: RotateCcw },
];

export function BatchDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState('matrix');
  const [selectedRev, setSelectedRev] = useState(null);

  const { data: batch } = useQuery({ queryKey: ['batches', id], queryFn: () => api.batches.get(Number(id)) });
  const { data: report } = useQuery({
    queryKey: ['batches', id, 'report', selectedRev],
    queryFn: () => api.batches.report(Number(id), selectedRev),
  });
  const { data: revisions } = useQuery({ queryKey: ['batches', id, 'revisions'], queryFn: () => api.batches.revisions(Number(id)) });

  const matrixData = report?.rows ? transformReportToMatrix(report.rows) : null;

  return (
    <div>
      <button onClick={() => navigate('/batches')} className="flex items-center gap-1 text-sm text-gray-400 hover:text-gray-600 mb-4 transition-colors">
        <ArrowLeft size={15} /> 返回批次列表
      </button>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{batch?.name || '批次详情'}</h2>
          <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
            <span className="font-mono text-gray-400">#{batch?.id}</span>
            <span className={`px-1.5 py-0.5 rounded-md text-xs font-medium ${
              batch?.mode === 'all' ? 'bg-purple-100 text-purple-700' :
              batch?.mode === 'infer' ? 'bg-primary-100 text-primary-700' : 'bg-amber-100 text-amber-700'
            }`}>{batch?.mode}</span>
            <span className="text-gray-400">{batch?.default_eval_version}</span>
            <span className="text-gray-400">{batch?.created_at ? new Date(batch.created_at).toLocaleString() : '-'}</span>
            {batch?.created_by && (
              <span className="flex items-center gap-1 text-gray-400">
                <User size={13} />
                {userDisplay(batch.created_by)}
              </span>
            )}
            {batch?.last_modified_by && (
              <span className="flex items-center gap-1 text-gray-400">
                最后修改: {userDisplay(batch.last_modified_by)}
              </span>
            )}
          </div>
        </div>
        {revisions?.length > 0 && (
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-500">版本:</label>
            <select className="input py-1 text-sm" value={selectedRev || ''} onChange={e => setSelectedRev(e.target.value ? Number(e.target.value) : null)}>
              <option value="">当前</option>
              {revisions.map(r => <option key={r.id} value={r.rev_num}>Rev {r.rev_num} ({r.change_type})</option>)}
            </select>
          </div>
        )}
      </div>

      <div className="flex gap-1 mb-6 border-b border-gray-100">
        {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-[13px] font-medium border-b-2 transition-colors -mb-px ${
                activeTab === tab.id
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <tab.icon size={15} />
              {tab.label}
            </button>
          ))}
      </div>

      {activeTab === 'matrix' && <MatrixTab data={matrixData} />}
      {activeTab === 'charts' && <ChartsTab rows={report?.rows} />}
      {activeTab === 'revisions' && <RevisionsTab revisions={revisions} />}
      {activeTab === 'rerun' && <RerunTab batchId={Number(id)} />}
    </div>
  );
}

function MatrixTab({ data }) {
  if (!data) return <div className="text-gray-400">加载中...</div>;
  const { models, tasks, matrix } = data;

  function cellColor(acc) {
    if (acc == null) return 'bg-gray-50 text-gray-300';
    if (acc >= 90) return 'bg-emerald-50 text-emerald-700';
    if (acc >= 75) return 'bg-teal-50 text-teal-700';
    if (acc >= 60) return 'bg-amber-50 text-amber-700';
    return 'bg-red-50 text-red-600';
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border border-gray-200 rounded-xl overflow-hidden">
        <thead>
          <tr>
            <th className="px-3 py-2.5 text-xs font-semibold text-gray-500 bg-gray-50 border-b border-r border-gray-200 sticky left-0">模型 \ 任务</th>
            {tasks.map(t => (
              <th key={t.id} className="px-3 py-2.5 text-xs font-semibold text-gray-500 bg-gray-50 border-b border-gray-200 min-w-[100px] text-center">{t.key}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {models.map((m, mi) => (
            <tr key={m.id}>
              <td className="px-3 py-2.5 text-sm font-medium text-gray-800 bg-gray-50 border-r border-gray-200 sticky left-0">{m.name}</td>
              {tasks.map((t, ti) => {
                const cell = matrix[mi][ti];
                return (
                  <td key={t.id} className={`px-3 py-2.5 text-sm text-center border-b border-gray-100 ${cellColor(cell?.accuracy)}`}>
                    {cell ? (
                      <div className="space-y-0.5">
                        <div className="font-bold">{cell.accuracy != null ? `${cell.accuracy.toFixed(1)}%` : '—'}</div>
                        <div className="text-xs opacity-60">{cell.num_samples != null ? `${cell.num_samples}条` : '—'}</div>
                        <div><StatusBadge status={cell.status} /></div>
                      </div>
                    ) : <span className="text-gray-300">—</span>}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChartsTab({ rows }) {
  if (!rows) return <div className="text-gray-400">加载中...</div>;
  return (
    <div className="space-y-8">
      <section>
        <h3 className="text-base font-semibold text-gray-800 mb-4">准确率分析</h3>
        <AccuracyBarChart rows={rows} />
      </section>
      <section>
        <h3 className="text-base font-semibold text-gray-800 mb-4">耗时分析</h3>
        <DurationBarChart rows={rows} />
      </section>
      <section>
        <h3 className="text-base font-semibold text-gray-800 mb-4">模型能力雷达图</h3>
        <ModelTaskRadarChart rows={rows} />
      </section>
    </div>
  );
}

function RevisionsTab({ revisions }) {
  if (!revisions?.length) return <div className="text-gray-400">暂无历史版本</div>;
  return (
    <Card>
      <CardBody className="p-0">
        <table className="min-w-full divide-y divide-gray-100">
          <thead className="bg-gray-50">
            <tr>
              {['Rev', '类型', '变更说明', '创建时间'].map(h => (
                <th key={h} className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {revisions.map(r => (
              <tr key={r.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4 text-sm font-semibold text-gray-900">{r.rev_num}</td>
                <td className="px-6 py-4 text-sm">
                  <span className={`px-2 py-0.5 rounded-md text-xs font-medium ${
                    r.change_type === 'create' ? 'bg-primary-100 text-primary-700' :
                    r.change_type === 'rerun' ? 'bg-amber-100 text-amber-700' :
                    'bg-gray-100 text-gray-600'
                  }`}>{r.change_type}</span>
                </td>
                <td className="px-6 py-4 text-sm text-gray-500">{r.change_summary || '—'}</td>
                <td className="px-6 py-4 text-sm text-gray-500">{new Date(r.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}

function RerunTab({ batchId }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ model_ids: [], task_ids: [], what: 'both', dataset_version_id: '' });

  const { data: report } = useQuery({ queryKey: ['batches', batchId, 'report'], queryFn: () => api.batches.report(batchId) });

  const rerunMut = useMutation({
    mutationFn: (data) => api.batches.rerun(batchId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] });
      setForm({ model_ids: [], task_ids: [], what: 'both', dataset_version_id: '' });
      alert('重跑任务已创建');
    },
  });

  const models = report?.rows ? [...new Map(report.rows.map(r => [r.model_id, { id: r.model_id, name: r.model_name }])).values()] : [];
  const tasks  = report?.rows ? [...new Map(report.rows.map(r => [r.task_id,  { id: r.task_id,  key: r.task_key  }])).values()] : [];

  function toggle(arr, val) {
    const v = Number(val);
    return arr.includes(v) ? arr.filter(x => x !== v) : [...arr, v];
  }

  function handleSubmit(e) {
    e.preventDefault();
    rerunMut.mutate({ ...form, dataset_version_id: form.dataset_version_id ? Number(form.dataset_version_id) : null });
  }

  return (
    <Card className="max-w-2xl">
      <CardBody>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">重跑类型</label>
            <div className="flex gap-4">
              {[{ value: 'both', label: '推理 + 评测' }, { value: 'infer', label: '仅推理' }, { value: 'eval', label: '仅评测' }].map(opt => (
                <label key={opt.value} className="flex items-center gap-2 text-sm cursor-pointer text-gray-700">
                  <input type="radio" name="what" value={opt.value} checked={form.what === opt.value} onChange={e => setForm({ ...form, what: e.target.value })} />
                  {opt.label}
                </label>
              ))}
            </div>
          </div>
          <div>
            <label className="label">选择模型 <span className="text-red-500">*</span></label>
            <div className="border border-gray-200 rounded-lg p-3 space-y-2 max-h-40 overflow-y-auto bg-gray-50">
              {models.map(m => (
                <label key={m.id} className="flex items-center gap-2 text-sm cursor-pointer text-gray-700">
                  <input type="checkbox" checked={form.model_ids.includes(m.id)} onChange={() => setForm({ ...form, model_ids: toggle(form.model_ids, m.id) })} />
                  {m.name}
                </label>
              ))}
            </div>
          </div>
          <div>
            <label className="label">选择任务 <span className="text-red-500">*</span></label>
            <div className="border border-gray-200 rounded-lg p-3 space-y-2 max-h-40 overflow-y-auto bg-gray-50">
              {tasks.map(t => (
                <label key={t.id} className="flex items-center gap-2 text-sm cursor-pointer text-gray-700">
                  <input type="checkbox" checked={form.task_ids.includes(t.id)} onChange={() => setForm({ ...form, task_ids: toggle(form.task_ids, t.id) })} />
                  {t.key}
                </label>
              ))}
            </div>
          </div>
          <div>
            <label className="label">数据集版本 ID（可选）</label>
            <input className="input" type="number" value={form.dataset_version_id} onChange={e => setForm({ ...form, dataset_version_id: e.target.value })} placeholder="留空则不切换数据集" />
          </div>
          {rerunMut.isError && <p className="text-sm text-red-600">{rerunMut.error.message}</p>}
          {rerunMut.isSuccess && <p className="text-sm text-emerald-600">已创建 {rerunMut.data.jobs_created} 个任务</p>}
          <div className="flex justify-end">
            <button type="submit" className="btn-primary" disabled={rerunMut.isPending}>
              {rerunMut.isPending ? '提交中...' : '执行重跑'}
            </button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}
