import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate, Link } from 'react-router-dom';
import { api } from '../../lib/api';
import { Card, CardBody } from '../../components/ui/Card';
import { Modal } from '../../components/ui/Modal';
import { Plus, ArrowRight, Activity, Info } from 'lucide-react';

const STATUS_CONFIG = {
  pending:  { label: '待执行', cls: 'bg-zinc-800 text-zinc-400' },
  running:  { label: '执行中', cls: 'bg-primary-900/40 text-primary-400' },
  success:  { label: '已完成', cls: 'bg-emerald-900/40 text-emerald-400' },
  failed:   { label: '有失败', cls: 'bg-red-900/40 text-red-400' },
};

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${cfg.cls}`}>
      {status === 'running' && (
        <span className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-pulse inline-block" />
      )}
      {cfg.label}
    </span>
  );
}

export function BatchesPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState({
    name: '', mode: 'all', model_ids: [], task_ids: [],
    default_eval_version: 'eval_init', default_judge_id: '', notes: '',
  });

  const { data: batches, isLoading } = useQuery({ queryKey: ['batches'], queryFn: api.batches.list });
  const { data: models } = useQuery({ queryKey: ['models'], queryFn: api.models.list });
  const { data: tasks } = useQuery({ queryKey: ['tasks'], queryFn: api.tasks.list });
  const { data: judges } = useQuery({ queryKey: ['judges'], queryFn: api.judges.list });

  const createMut = useMutation({
    mutationFn: api.batches.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['batches'] });
      setModalOpen(false);
      setForm({ name: '', mode: 'all', model_ids: [], task_ids: [], default_eval_version: 'eval_init', default_judge_id: '', notes: '' });
    },
  });

  function handleSubmit(e) {
    e.preventDefault();
    createMut.mutate({
      ...form,
      model_ids: form.model_ids.map(Number),
      task_ids: form.task_ids.map(Number),
      default_judge_id: form.default_judge_id ? Number(form.default_judge_id) : null,
    });
  }

  function toggleSelection(arr, val) {
    const v = Number(val);
    return arr.includes(v) ? arr.filter(x => x !== v) : [...arr, v];
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold text-zinc-100">测评管理</h2>
        <button className="btn-primary flex items-center gap-2" onClick={() => setModalOpen(true)}>
          <Plus size={18} /> 创建任务
        </button>
      </div>

      <div className="flex items-center gap-2 mb-5 px-4 py-3 bg-primary-900/20 border border-primary-800/50 rounded-lg text-sm text-primary-300">
        <Info size={16} className="flex-shrink-0" />
        <span>任务创建后将自动调度执行，</span>
        <Link to="/jobs" className="font-medium underline underline-offset-2 hover:text-primary-200 flex items-center gap-1">
          前往执行记录 <Activity size={13} />
        </Link>
        <span>查看实时状态与日志。</span>
      </div>

      <Card>
        <CardBody className="p-0">
          <table className="min-w-full divide-y divide-zinc-800">
            <thead className="bg-zinc-800/50">
              <tr>
                {['ID', '名称', '模式', 'Eval Version', '创建时间', '状态', '操作'].map(h => (
                  <th key={h} className="px-6 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {isLoading ? (
                <tr><td colSpan={7} className="px-6 py-4 text-zinc-400">加载中...</td></tr>
              ) : batches?.length === 0 ? (
                <tr><td colSpan={7} className="px-6 py-4 text-zinc-400">暂无评测任务</td></tr>
              ) : batches?.map(b => (
                <tr key={b.id} className="hover:bg-zinc-800/40 cursor-pointer transition-colors" onClick={() => navigate(`/batches/${b.id}`)}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-zinc-500">{b.id}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-zinc-100">{b.name}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      b.mode === 'all' ? 'bg-purple-900/30 text-purple-400' :
                      b.mode === 'infer' ? 'bg-primary-900/30 text-primary-400' : 'bg-amber-900/30 text-amber-400'
                    }`}>{b.mode}</span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-zinc-400">{b.default_eval_version}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-zinc-400">{new Date(b.created_at).toLocaleString()}</td>
                  <td className="px-6 py-4 whitespace-nowrap" onClick={e => e.stopPropagation()}>
                    <StatusBadge status={b.status} />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <ArrowRight size={16} className="text-zinc-600" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="创建任务" size="lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">任务名称 <span className="text-red-400">*</span></label>
            <input className="input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
          </div>
          <div>
            <label className="label">模式</label>
            <select className="input" value={form.mode} onChange={e => setForm({ ...form, mode: e.target.value })}>
              <option value="all">推理 + 评测 (all)</option>
              <option value="infer">仅推理 (infer)</option>
              <option value="eval">仅评测 (eval)</option>
            </select>
          </div>
          <div>
            <label className="label">选择评测模型 <span className="text-red-400">*</span></label>
            <div className="border border-zinc-700 rounded-md p-3 space-y-2 max-h-40 overflow-y-auto bg-zinc-800/30">
              {models?.length === 0 ? (
                <p className="text-sm text-zinc-500">暂无模型，请先在「评测模型」中新增</p>
              ) : models?.map(m => (
                <label key={m.id} className="flex items-center gap-2 text-sm cursor-pointer text-zinc-300">
                  <input type="checkbox" checked={form.model_ids.includes(m.id)} onChange={() => setForm({ ...form, model_ids: toggleSelection(form.model_ids, m.id) })} />
                  <span>{m.name} <span className="text-zinc-500">({m.model_name})</span></span>
                </label>
              ))}
            </div>
          </div>
          <div>
            <label className="label">选择评测任务 <span className="text-red-400">*</span></label>
            <div className="border border-zinc-700 rounded-md p-3 space-y-2 max-h-40 overflow-y-auto bg-zinc-800/30">
              {tasks?.map(t => (
                <label key={t.id} className="flex items-center gap-2 text-sm cursor-pointer text-zinc-300">
                  <input type="checkbox" checked={form.task_ids.includes(t.id)} onChange={() => setForm({ ...form, task_ids: toggleSelection(form.task_ids, t.id) })} />
                  <span>{t.alias || t.key} <span className="text-zinc-500 font-mono text-xs">{t.alias ? `(${t.key})` : ''}</span></span>
                </label>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">评测版本</label>
              <input className="input" value={form.default_eval_version} onChange={e => setForm({ ...form, default_eval_version: e.target.value })} />
            </div>
            <div>
              <label className="label">打分模型</label>
              <select className="input" value={form.default_judge_id} onChange={e => setForm({ ...form, default_judge_id: e.target.value })}>
                <option value="">不使用</option>
                {judges?.map(j => (
                  <option key={j.id} value={j.id}>{j.name}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="label">备注</label>
            <input className="input" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
          </div>
          {createMut.isError && <p className="text-sm text-red-400">{createMut.error.message}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" className="btn-secondary" onClick={() => setModalOpen(false)}>取消</button>
            <button type="submit" className="btn-primary" disabled={createMut.isPending}>
              {createMut.isPending ? '创建中...' : '创建'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
