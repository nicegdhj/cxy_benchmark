import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Card, CardBody } from '../../components/ui/Card';
import { Modal } from '../../components/ui/Modal';
import { Plus, Pencil, Trash2 } from 'lucide-react';
import { RoleButton } from '../../components/ui/RoleButton';

const DEFAULT_FORM = { name: '', host: '', port: 443, model_name: '', auth_ref: '', extra_env_json: {} };

export function JudgesPage() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(DEFAULT_FORM);

  const { data: judges, isLoading } = useQuery({ queryKey: ['judges'], queryFn: api.judges.list });

  const createMut = useMutation({
    mutationFn: api.judges.create,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['judges'] }); setModalOpen(false); setForm(DEFAULT_FORM); },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => api.judges.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['judges'] }); setModalOpen(false); setEditing(null); setForm(DEFAULT_FORM); },
  });

  const deleteMut = useMutation({
    mutationFn: api.judges.del,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['judges'] }),
  });

  function openCreate() { setEditing(null); setForm(DEFAULT_FORM); setModalOpen(true); }
  function openEdit(j) { setEditing(j); setForm({ ...j, extra_env_json: j.extra_env_json || {} }); setModalOpen(true); }

  function handleSubmit(e) {
    e.preventDefault();
    const payload = { ...form, port: Number(form.port) };
    if (editing) updateMut.mutate({ id: editing.id, data: payload });
    else createMut.mutate(payload);
  }

  const fields = [
    { key: 'name', label: '名称', required: true },
    { key: 'host', label: 'Host', required: true },
    { key: 'port', label: '端口', type: 'number', required: true },
    { key: 'model_name', label: '模型名', required: true },
    { key: 'auth_ref', label: 'Auth Ref' },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">打分模型</h2>
        <RoleButton variant="primary" onClick={openCreate}>
          <Plus size={18} /> 新增 Judge
        </RoleButton>
      </div>

      <Card>
        <CardBody className="p-0">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {['ID', '名称', 'Host:Port', '模型名', 'Auth Ref', '操作'].map(h => (
                  <th key={h} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {isLoading ? (
                <tr><td colSpan={6} className="px-6 py-4 text-gray-500">加载中...</td></tr>
              ) : judges?.length === 0 ? (
                <tr><td colSpan={6} className="px-6 py-4 text-gray-500">暂无 Judge</td></tr>
              ) : judges?.map(j => (
                <tr key={j.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{j.id}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{j.name}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{j.host}:{j.port}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{j.model_name}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{j.auth_ref || '-'}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm flex gap-2">
                    <RoleButton variant="ghost" onClick={() => openEdit(j)} requireWrite>
                      <Pencil size={16} />
                    </RoleButton>
                    <RoleButton variant="ghost" onClick={() => deleteMut.mutate(j.id)} requireWrite>
                      <Trash2 size={16} />
                    </RoleButton>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? '编辑 Judge' : '新增 Judge'}>
        <form onSubmit={handleSubmit} className="space-y-4">
          {fields.map(f => (
            <div key={f.key}>
              <label className="label">{f.label}{f.required && <span className="text-red-500">*</span>}</label>
              <input type={f.type || 'text'} className="input" value={form[f.key]} onChange={e => setForm({ ...form, [f.key]: f.type === 'number' ? Number(e.target.value) : e.target.value })} required={f.required} />
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
