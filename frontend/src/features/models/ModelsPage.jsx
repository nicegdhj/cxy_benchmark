import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Card, CardBody } from '../../components/ui/Card';
import { Modal } from '../../components/ui/Modal';
import { Plus, Pencil, Trash2, Server } from 'lucide-react';

const DEFAULT_FORM = {
  name: '', model_config_key: 'local_qwen', model_name: '',
  host: '', port: '', url: '', api_key: '', concurrency: '20', gen_kwargs_json: {},
};

const CONFIG_KEY_OPTIONS = [
  { value: 'local_qwen',   label: 'local_qwen',   desc: '垂类模型配置（本地 vLLM 服务）' },
  { value: 'maas_gateway', label: 'maas_gateway', desc: 'MaaS 服务（带网关鉴权）' },
  { value: 'bailian',      label: 'bailian',      desc: '外部大模型服务（百炼 API）' },
];

const CONFIG_FIELDS = {
  local_qwen: [
    { key: 'model_name', label: '模型名',  required: true,  placeholder: 'qwen3-14b' },
    { key: 'host',       label: 'Host IP', required: true,  placeholder: '192.168.x.x' },
    { key: 'port',       label: '端口',    required: true,  placeholder: '8000' },
    { key: 'concurrency',label: '并发数',  placeholder: '20' },
  ],
  maas_gateway: [
    { key: 'model_name', label: '模型名',   required: true,  placeholder: 'deepseekv3.1-w8a8' },
    { key: 'api_key',    label: 'API Key',  required: true,  placeholder: 'Authorization-Gateway Token' },
    { key: 'host',       label: 'Host IP',  required: true,  placeholder: '188.x.x.x' },
    { key: 'port',       label: '端口',     required: true,  placeholder: '30175' },
    { key: 'url',        label: '完整 URL', required: true,  placeholder: 'http://host:port/gateway/api/.../v1/chat/completions' },
    { key: 'concurrency',label: '并发数',   placeholder: '20' },
  ],
  bailian: [
    { key: 'model_name', label: '模型名',  required: true, placeholder: 'qwen-plus' },
    { key: 'api_key',    label: 'API Key', required: true, placeholder: 'sk-...' },
    { key: 'url',        label: 'API URL', required: true, placeholder: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions' },
    { key: 'concurrency',label: '并发数',  placeholder: '20' },
  ],
};

const CARD_FIELDS = {
  local_qwen:   ['model_name', 'host', 'port', 'concurrency'],
  maas_gateway: ['model_name', 'host', 'port', 'url', 'concurrency'],
  bailian:      ['model_name', 'url', 'concurrency'],
};

const FIELD_LABELS = {
  model_name: '模型名', host: 'Host', port: '端口',
  url: 'URL', api_key: 'API Key', concurrency: '并发数',
};

const CONFIG_BADGE = {
  local_qwen:   'bg-primary-900/30 text-primary-400',
  maas_gateway: 'bg-orange-900/30 text-orange-400',
  bailian:      'bg-purple-900/30 text-purple-400',
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
  function openEdit(m) {
    setEditing(m);
    setForm({
      ...DEFAULT_FORM, ...m,
      port: String(m.port ?? ''),
      concurrency: String(m.concurrency ?? '20'),
      gen_kwargs_json: m.gen_kwargs_json || {},
    });
    setModalOpen(true);
  }

  function handleSubmit(e) {
    e.preventDefault();
    const payload = {
      ...form,
      port: form.port ? Number(form.port) : null,
      concurrency: Number(form.concurrency) || 20,
    };
    if (editing) updateMut.mutate({ id: editing.id, data: payload });
    else createMut.mutate(payload);
  }

  const activeFields = CONFIG_FIELDS[form.model_config_key] ?? CONFIG_FIELDS.local_qwen;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-zinc-100">评测模型</h2>
        <button className="btn-primary flex items-center gap-2" onClick={openCreate}>
          <Plus size={18} /> 新增模型
        </button>
      </div>

      {isLoading ? (
        <div className="text-zinc-400">加载中...</div>
      ) : models?.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 text-zinc-600">
          <Server size={40} className="mb-3" />
          <p>暂无模型，点击右上角新增</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {models?.map(m => {
            const cardFields = CARD_FIELDS[m.model_config_key] ?? CARD_FIELDS.local_qwen;
            const badgeCls = CONFIG_BADGE[m.model_config_key] ?? 'bg-zinc-800 text-zinc-400';
            return (
              <Card key={m.id}>
                <CardBody>
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium mb-1 ${badgeCls}`}>
                        {m.model_config_key}
                      </span>
                      <h3 className="text-base font-semibold text-zinc-100">{m.name}</h3>
                    </div>
                    <div className="flex gap-2 ml-2 flex-shrink-0">
                      <button onClick={() => openEdit(m)} className="text-zinc-400 hover:text-primary-400 transition-colors"><Pencil size={15} /></button>
                      <button onClick={() => deleteMut.mutate(m.id)} className="text-zinc-500 hover:text-red-400 transition-colors"><Trash2 size={15} /></button>
                    </div>
                  </div>
                  <dl className="space-y-1">
                    {cardFields.map(fk => {
                      const val = fk === 'port' && m.host ? `${m.host}:${m.port}` : m[fk];
                      const label = fk === 'port' ? 'Host:Port' : FIELD_LABELS[fk] ?? fk;
                      if (fk === 'host') return null;
                      return val ? (
                        <div key={fk} className="flex gap-2 text-sm">
                          <dt className="text-zinc-500 w-20 flex-shrink-0">{label}</dt>
                          <dd className="text-zinc-300 truncate font-mono text-xs leading-5">{val}</dd>
                        </div>
                      ) : null;
                    })}
                  </dl>
                </CardBody>
              </Card>
            );
          })}
        </div>
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? '编辑模型' : '新增模型'}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Config_Key <span className="text-red-400">*</span></label>
            <select className="input" value={form.model_config_key} onChange={e => setForm({ ...form, model_config_key: e.target.value })}>
              {CONFIG_KEY_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <p className="mt-1 text-xs text-zinc-500">
              {CONFIG_KEY_OPTIONS.find(o => o.value === form.model_config_key)?.desc}
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
