import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Card, CardBody } from '../../components/ui/Card';
import { Modal } from '../../components/ui/Modal';
import { Upload, Database, Check } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';

const CATEGORY_COLORS = {
  '知识类':       'bg-sky-100 text-sky-700',
  '推理类':       'bg-orange-100 text-orange-700',
  '生成类':       'bg-emerald-100 text-emerald-700',
  '数学与代码类': 'bg-violet-100 text-violet-700',
  '知识问答':     'bg-teal-100 text-teal-700',
};

function CategoryBadge({ category }) {
  const key = Object.keys(CATEGORY_COLORS).find(k => category.startsWith(k));
  const cls = CATEGORY_COLORS[key] ?? 'bg-gray-100 text-gray-600';
  return <span className={`px-1.5 py-0.5 rounded-md text-xs font-medium ${cls}`}>{category}</span>;
}

export function TasksPage() {
  const qc = useQueryClient();
  const { canWrite } = useAuthStore();
  const [selectedTask, setSelectedTask] = useState(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadForm, setUploadForm] = useState({ tag: '', is_default: false, note: '', file: null });

  const { data: tasks, isLoading } = useQuery({ queryKey: ['tasks'], queryFn: api.tasks.list });

  useEffect(() => {
    if (selectedTask) {
      document.querySelector('main')?.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [selectedTask?.id]);

  const { data: datasets } = useQuery({
    queryKey: ['tasks', selectedTask?.id, 'datasets'],
    queryFn: () => api.tasks.datasets(selectedTask.id),
    enabled: !!selectedTask,
  });

  const uploadMut = useMutation({
    mutationFn: ({ taskId, formData }) => api.tasks.uploadDataset(taskId, formData),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] });
      qc.invalidateQueries({ queryKey: ['tasks', selectedTask?.id, 'datasets'] });
      setUploadOpen(false);
      setUploadForm({ tag: '', is_default: false, note: '', file: null });
    },
  });

  function handleUpload(e) {
    e.preventDefault();
    const fd = new FormData();
    fd.append('tag', uploadForm.tag);
    fd.append('is_default', uploadForm.is_default);
    if (uploadForm.note) fd.append('note', uploadForm.note);
    fd.append('file', uploadForm.file);
    uploadMut.mutate({ taskId: selectedTask.id, formData: fd });
  }

  return (
    <div>
      <div className="flex items-start justify-between mb-7">
        <div>
          <h1 className="text-[22px] font-bold text-gray-900 leading-tight">任务与数据</h1>
          <p className="text-sm text-gray-500 mt-0.5">管理评测任务及数据集版本</p>
        </div>
      </div>
      <div className="flex gap-6">
        <div className="w-96 flex-shrink-0">
          <Card>
            <CardBody className="p-0">
              <div className="px-4 py-3 border-b border-gray-100 font-semibold text-sm text-gray-700">任务列表</div>
              {isLoading ? (
                <div className="px-4 py-4 text-sm text-gray-400">加载中...</div>
              ) : tasks?.map(t => (
                <button
                  key={t.id}
                  onClick={() => setSelectedTask(t)}
                  className="w-full text-left px-4 py-3 border-b border-gray-50 transition-colors relative"
                  style={selectedTask?.id === t.id
                    ? { background: '#eff6ff', borderLeft: '3px solid #0C5CAB' }
                    : { borderLeft: '3px solid transparent' }
                  }
                >
                  {t.dataset_count > 0 && (
                    <span className="absolute top-2 right-3 flex items-center gap-1 text-xs text-emerald-600">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
                      {t.dataset_count} 个版本
                    </span>
                  )}
                  <div className="text-sm font-semibold text-gray-900 leading-snug pr-16">
                    {t.alias || t.key}
                  </div>
                  {t.alias && (
                    <div className="text-xs text-gray-400 font-mono mt-0.5">{t.key}</div>
                  )}
                  <div className="mt-1 flex items-center flex-wrap gap-1">
                    {t.category && <CategoryBadge category={t.category} />}
                    <span className={`px-1.5 py-0.5 rounded-md text-xs font-medium ${t.type === 'custom' ? 'bg-primary-100 text-primary-700' : 'bg-purple-100 text-purple-700'}`}>{t.type}</span>
                    {t.is_llm_judge && <span className="px-1.5 py-0.5 rounded-md text-xs font-medium bg-amber-100 text-amber-700">LLM Judge</span>}
                  </div>
                </button>
              ))}
            </CardBody>
          </Card>
        </div>

        <div className="flex-1 min-w-0">
          {selectedTask ? (
            <div>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">{selectedTask.alias || selectedTask.key}</h3>
                  {selectedTask.alias && (
                    <p className="text-xs text-gray-400 font-mono mt-0.5">{selectedTask.key}</p>
                  )}
                  {selectedTask.category && (
                    <div className="mt-1"><CategoryBadge category={selectedTask.category} /></div>
                  )}
                </div>
                <button className="btn-primary flex items-center gap-2" onClick={() => setUploadOpen(true)} disabled={!canWrite()} title={!canWrite() ? '需要操作员或管理员权限' : undefined}>
                  <Upload size={15} /> 上传数据集
                </button>
              </div>
              <Card>
                <CardBody className="p-0">
                  <table className="min-w-full">
                    <thead>
                      <tr className="border-b border-gray-100">
                        {['Tag', '默认', 'Hash', '上传时间', '备注'].map(h => (
                          <th key={h} className="px-4 py-3 text-center text-[11px] font-semibold text-gray-400 uppercase tracking-wider">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {datasets?.length === 0 ? (
                        <tr><td colSpan={5} className="px-4 py-4 text-sm text-gray-400">暂无数据集版本</td></tr>
                      ) : datasets?.map(d => (
                        <tr key={d.id} className="hover:bg-gray-50 transition-colors">
                          <td className="px-4 py-3 text-sm font-semibold text-gray-900">{d.tag}</td>
                          <td className="px-4 py-3 text-sm">{d.is_default ? <Check size={15} className="text-emerald-500" /> : <span className="text-gray-300">—</span>}</td>
                          <td className="px-4 py-3 text-xs text-gray-400 font-mono truncate max-w-[120px]">{d.content_hash?.slice(0, 12)}…</td>
                          <td className="px-4 py-3 text-sm text-gray-500">{new Date(d.uploaded_at).toLocaleString()}</td>
                          <td className="px-4 py-3 text-sm text-gray-500">{d.note || <span className="text-gray-300">—</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardBody>
              </Card>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-gray-300">
              <Database size={48} className="mb-4" />
              <p className="text-gray-400">选择一个任务查看数据集</p>
            </div>
          )}
        </div>
      </div>

      <Modal open={uploadOpen} onClose={() => setUploadOpen(false)} title="上传数据集">
        <form onSubmit={handleUpload} className="space-y-4">
          <div>
            <label className="label">版本标签 <span className="text-red-500">*</span></label>
            <input className="input" value={uploadForm.tag} onChange={e => setUploadForm({ ...uploadForm, tag: e.target.value })} required />
          </div>
          <div>
            <label className="label">JSONL 文件 <span className="text-red-500">*</span></label>
            <input type="file" accept=".jsonl" className="input py-1.5" onChange={e => setUploadForm({ ...uploadForm, file: e.target.files[0] })} required />
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" id="is_default" checked={uploadForm.is_default} onChange={e => setUploadForm({ ...uploadForm, is_default: e.target.checked })} />
            <label htmlFor="is_default" className="text-sm text-gray-700">设为默认版本</label>
          </div>
          <div>
            <label className="label">备注</label>
            <input className="input" value={uploadForm.note} onChange={e => setUploadForm({ ...uploadForm, note: e.target.value })} />
          </div>
          {uploadMut.isError && <p className="text-sm text-red-600">{uploadMut.error.message}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" className="btn-secondary" onClick={() => setUploadOpen(false)}>取消</button>
            <button type="submit" className="btn-primary" disabled={uploadMut.isPending}>
              {uploadMut.isPending ? '上传中...' : '上传'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
