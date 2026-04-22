import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Card, CardHeader, CardBody } from '../../components/ui/Card';
import { Modal } from '../../components/ui/Modal';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { Plus, Pencil, Trash2, Server } from 'lucide-react';

const DEFAULT_FORM = {
  name: '', host: '', port: 9092, model_name: '', concurrency: 20, model_config_key: 'local_qwen', gen_kwargs_json: {},
};

export function ModelsPage() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(DEFAULT_FORM);

  const { data: models, isLoading } = useQuery({ queryKey: ['models'], queryFn: api.models.list });

  const createMut = useMutation({
    mutationFn: api.models.create,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['models'] }); setModalOpen(false); setForm(DEFAULT_FORM); },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => api.models.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['models'] }); setModalOpen(false); setEditing(null); setForm(DEFAULT_FORM); },
  });

  const deleteMut = useMutation({
    mutationFn: api.models.del,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['models'] }),
  });

  function openCreate() { setEditing(null); setForm(DEFAULT_FORM); setModalOpen(true); }
  function openEdit(m) { setEditing(m); setForm({ ...m, gen_kwargs_json: m.gen_kwargs_json || {} }); setModalOpen(true); }

  function handleSubmit(e) {
    e.preventDefault();
    const payload = { ...form, port: Number(form.port), concurrency: Number(form.concurrency) };
    if (editing) updateMut.mutate({ id: editing.id, data: payload });
    else createMut.mutate(payload);
  }

  const fields = [
    { key: 'name', label: '名称', required: true },
    { key: 'host', label: 'Host', required: true },
    { key: 'port', label: '端口', type: 'number', required: true },
    { key: 'model_name', label: '模型名', required: true },
    { key: 'concurrency', label: '并发数', type: 'number' },
    { key: 'model_config_key', label: 'Config Key' },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">模型管理</h2>
        <button className="btn-primary flex items-center gap-2" onClick={openCreate}>
          <Plus size={18} /> 新增模型
        </button>
      </div>

      <Card>
        <CardBody className="p-0">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {['ID', '名称', 'Host:Port', '模型名', '并发', 'Config', '操作'].map(h => (
                  <th key={h} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {isLoading ? (
                <tr><td colSpan={7} className="px-6 py-4 text-gray-500">加载中...</td></tr>
              ) : models?.length === 0 ? (
                <tr><td colSpan={7} className="px-6 py-4 text-gray-500">暂无模型</td></tr>
              ) : models?.map(m => (
                <tr key={m.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{m.id}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{m.name}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{m.host}:{m.port}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{m.model_name}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{m.concurrency}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{m.model_config_key}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm flex gap-2">
                    <button onClick={() => openEdit(m)} className="text-blue-600 hover:text-blue-800"><Pencil size={16} /></button>
                    <button onClick={() => deleteMut.mutate(m.id)} className="text-red-600 hover:text-red-800"><Trash2 size={16} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? '编辑模型' : '新增模型'}>
        <form onSubmit={handleSubmit} className="space-y-4">
          {fields.map(f => (
            <div key={f.key}>
              <label className="label">{f.label}{f.required && <span className="text-red-500">*</span>}</label>
              <input
                type={f.type || 'text'}
                className="input"
                value={form[f.key]}
                onChange={e => setForm({ ...form, [f.key]: f.type === 'number' ? Number(e.target.value) : e.target.value })}
                required={f.required}
              />
            </div>
          ))}
          {(createMut.isError || updateMut.isError) && (
            <p className="text-sm text-red-600">{createMut.error?.message || updateMut.error?.message}</p>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" className="btn-secondary" onClick={() => setModalOpen(false)}>取消</button>
            <button type="submit" className="btn-primary" disabled={createMut.isPending || updateMut.isPending}>
              {createMut.isPending || updateMut.isPending ? '保存中...' : '保存'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
