import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/api';
import { Card, CardBody } from '../../components/ui/Card';
import { Modal } from '../../components/ui/Modal';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { Plus, ArrowRight } from 'lucide-react';
import { RoleButton } from '../../components/ui/RoleButton';

export function BatchesPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState({
    name: '', mode: 'all', model_ids: [], task_ids: [], default_eval_version: 'eval_init', default_judge_id: '', notes: ''
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
    const payload = {
      ...form,
      model_ids: form.model_ids.map(Number),
      task_ids: form.task_ids.map(Number),
      default_judge_id: form.default_judge_id ? Number(form.default_judge_id) : null,
    };
    createMut.mutate(payload);
  }

  function toggleSelection(arr, val) {
    const v = Number(val);
    return arr.includes(v) ? arr.filter(x => x !== v) : [...arr, v];
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">批次评测</h2>
        <RoleButton variant="primary" onClick={() => setModalOpen(true)}>
          <Plus size={18} /> 创建批次
        </RoleButton>
      </div>

      <Card>
        <CardBody className="p-0">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {['ID', '名称', '模式', 'Eval Version', '创建时间', '操作'].map(h => (
                  <th key={h} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {isLoading ? (
                <tr><td colSpan={6} className="px-6 py-4 text-gray-500">加载中...</td></tr>
              ) : batches?.length === 0 ? (
                <tr><td colSpan={6} className="px-6 py-4 text-gray-500">暂无批次</td></tr>
              ) : batches?.map(b => (
                <tr key={b.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => navigate(`/batches/${b.id}`)}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{b.id}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{b.name}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      b.mode === 'all' ? 'bg-purple-100 text-purple-700' :
                      b.mode === 'infer' ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700'
                    }`}>{b.mode}</span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{b.default_eval_version}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{new Date(b.created_at).toLocaleString()}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <ArrowRight size={16} className="text-gray-400" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="创建批次" size="lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">批次名称 <span className="text-red-500">*</span></label>
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
            <label className="label">选择模型 <span className="text-red-500">*</span></label>
            <div className="border rounded-md p-3 space-y-2 max-h-40 overflow-y-auto">
              {models?.map(m => (
                <label key={m.id} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={form.model_ids.includes(m.id)} onChange={() => setForm({ ...form, model_ids: toggleSelection(form.model_ids, m.id) })} />
                  <span>{m.name} ({m.model_name})</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="label">选择任务 <span className="text-red-500">*</span></label>
            <div className="border rounded-md p-3 space-y-2 max-h-40 overflow-y-auto">
              {tasks?.map(t => (
                <label key={t.id} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={form.task_ids.includes(t.id)} onChange={() => setForm({ ...form, task_ids: toggleSelection(form.task_ids, t.id) })} />
                  <span>{t.key}</span>
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
              <label className="label">Judge</label>
              <select className="input" value={form.default_judge_id} onChange={e => setForm({ ...form, default_judge_id: e.target.value })}>
                <option value="">默认</option>
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

          {createMut.isError && <p className="text-sm text-red-600">{createMut.error.message}</p>}
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
