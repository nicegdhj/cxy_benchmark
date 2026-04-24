import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Card, CardBody } from '../../components/ui/Card';
import { Modal } from '../../components/ui/Modal';
import { Plus, Pencil, Trash2, Scale } from 'lucide-react';

const DEFAULT_FORM = {
  name: '', judge_config_key: 'local_judge', model_name: '',
  host: '', port: '', url: '', api_key: '',
  score_model_type: 'maas', concurrency: '5', extra_env_json: {},
};

const CONFIG_KEY_OPTIONS = [
  { value: 'local_judge', label: 'local_judge', desc: '本地 vLLM 打分服务（无需 API Key）' },
  { value: 'api_judge',   label: 'api_judge',   desc: 'API 打分服务（云端，需要 API Key）' },
];

const SCORE_MODEL_TYPE_OPTIONS = [
  { value: 'maas',    label: 'maas',    desc: 'MaaS API' },
  { value: 'bailian', label: 'bailian', desc: '百炼 API（BailianAPI）' },
];

const CONFIG_FIELDS = {
  local_judge: [
    { key: 'model_name', label: '模型名',  required: true, placeholder: 'qwen3-14b' },
    { key: 'host',       label: 'Host IP', required: true, placeholder: '192.168.x.x' },
    { key: 'port',       label: '端口',    required: true, placeholder: '8000' },
    { key: 'concurrency',label: '并发数',  placeholder: '5' },
  ],
  api_judge: [
    { key: 'model_name', label: '模型名',  required: true, placeholder: 'gpt-4o / qwen-plus' },
    { key: 'api_key',    label: 'API Key', required: true, placeholder: 'sk-...' },
    { key: 'url',        label: 'API URL', required: true, placeholder: 'https://..../v1/chat/completions' },
    { key: 'concurrency',label: '并发数',  placeholder: '5' },
  ],
};

const CONFIG_BADGE = {
  local_judge: 'bg-teal-900/30 text-teal-400',
  api_judge:   'bg-indigo-900/30 text-indigo-400',
};

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
  function openEdit(j) {
    setEditing(j);
    setForm({
      ...DEFAULT_FORM, ...j,
      port: String(j.port ?? ''),
      concurrency: String(j.concurrency ?? '5'),
      extra_env_json: j.extra_env_json || {},
    });
    setModalOpen(true);
  }

  function handleSubmit(e) {
    e.preventDefault();
    const payload = {
      ...form,
      port: form.port ? Number(form.port) : null,
      concurrency: Number(form.concurrency) || 5,
    };
    if (editing) updateMut.mutate({ id: editing.id, data: payload });
    else createMut.mutate(payload);
  }

  const activeFields = CONFIG_FIELDS[form.judge_config_key] ?? CONFIG_FIELDS.local_judge;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-zinc-100">打分模型</h2>
        <button className="btn-primary flex items-center gap-2" onClick={openCreate}>
          <Plus size={18} /> 新增 Judge
        </button>
      </div>

      {isLoading ? (
        <div className="text-zinc-400">加载中...</div>
      ) : judges?.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 text-zinc-600">
          <Scale size={40} className="mb-3" />
          <p>暂无打分模型，点击右上角新增</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {judges?.map(j => {
            const badgeCls = CONFIG_BADGE[j.judge_config_key] ?? 'bg-zinc-800 text-zinc-400';
            const rows = j.judge_config_key === 'local_judge'
              ? [
                  { label: '模型名',    val: j.model_name },
                  { label: 'Host:Port', val: j.host && j.port ? `${j.host}:${j.port}` : j.host },
                  { label: '并发数',    val: j.concurrency },
                ]
              : [
                  { label: '模型名',          val: j.model_name },
                  { label: 'URL',              val: j.url },
                  { label: 'SCORE_MODEL_TYPE', val: j.score_model_type },
                  { label: '并发数',           val: j.concurrency },
                ];
            return (
              <Card key={j.id}>
                <CardBody>
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium mb-1 ${badgeCls}`}>
                        {j.judge_config_key}
                      </span>
                      <h3 className="text-base font-semibold text-zinc-100">{j.name}</h3>
                    </div>
                    <div className="flex gap-2 ml-2 flex-shrink-0">
                      <button onClick={() => openEdit(j)} className="text-zinc-400 hover:text-primary-400 transition-colors"><Pencil size={15} /></button>
                      <button onClick={() => deleteMut.mutate(j.id)} className="text-zinc-500 hover:text-red-400 transition-colors"><Trash2 size={15} /></button>
                    </div>
                  </div>
                  <dl className="space-y-1">
                    {rows.filter(r => r.val != null && r.val !== '').map(r => (
                      <div key={r.label} className="flex gap-2 text-sm">
                        <dt className="text-zinc-500 w-32 flex-shrink-0">{r.label}</dt>
                        <dd className="text-zinc-300 truncate font-mono text-xs leading-5">{String(r.val)}</dd>
                      </div>
                    ))}
                  </dl>
                </CardBody>
              </Card>
            );
          })}
        </div>
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? '编辑 Judge' : '新增 Judge'}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Config_Key <span className="text-red-400">*</span></label>
            <select className="input" value={form.judge_config_key} onChange={e => setForm({ ...form, judge_config_key: e.target.value })}>
              {CONFIG_KEY_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <p className="mt-1 text-xs text-zinc-500">
              {CONFIG_KEY_OPTIONS.find(o => o.value === form.judge_config_key)?.desc}
            </p>
          </div>
          <div>
            <label className="label">名称 <span className="text-red-400">*</span></label>
            <input className="input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required placeholder="自定义展示名称" />
          </div>
          {activeFields.map(f => (
            <div key={f.key}>
              <label className="label">{f.label}{f.required && <span className="text-red-400">*</span>}</label>
              <input
                className="input"
                value={form[f.key]}
                placeholder={f.placeholder || ''}
                onChange={e => setForm({ ...form, [f.key]: e.target.value })}
                required={f.required}
              />
            </div>
          ))}
          {form.judge_config_key === 'api_judge' && (
            <div>
              <label className="label">SCORE_MODEL_TYPE</label>
              <select className="input" value={form.score_model_type} onChange={e => setForm({ ...form, score_model_type: e.target.value })}>
                {SCORE_MODEL_TYPE_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label} — {o.desc}</option>
                ))}
              </select>
            </div>
          )}
          {(createMut.isError || updateMut.isError) && (
            <p className="text-sm text-red-400">{createMut.error?.message || updateMut.error?.message}</p>
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
