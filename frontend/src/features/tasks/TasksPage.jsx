import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Card, CardBody } from '../../components/ui/Card';
import { Modal } from '../../components/ui/Modal';
import { Upload, Database, Check } from 'lucide-react';

const CATEGORY_COLORS = {
  '知识类':       'bg-sky-900/30 text-sky-400',
  '推理类':       'bg-orange-900/30 text-orange-400',
  '生成类':       'bg-emerald-900/30 text-emerald-400',
  '数学与代码类': 'bg-violet-900/30 text-violet-400',
  '知识问答':     'bg-teal-900/30 text-teal-400',
};

function CategoryBadge({ category }) {
  const key = Object.keys(CATEGORY_COLORS).find(k => category.startsWith(k));
  const cls = CATEGORY_COLORS[key] ?? 'bg-zinc-800 text-zinc-400';
  return <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${cls}`}>{category}</span>;
}

export function TasksPage() {
  const qc = useQueryClient();
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
      <h2 className="text-2xl font-bold text-zinc-100 mb-6">任务与数据</h2>
      <div className="flex gap-6">
        {/* 左侧任务列表 */}
        <div className="w-96 flex-shrink-0">
          <Card>
            <CardBody className="p-0">
              <div className="px-4 py-3 border-b border-zinc-800 font-medium text-sm text-zinc-300">任务列表</div>
              {isLoading ? (
                <div className="px-4 py-4 text-sm text-zinc-500">加载中...</div>
              ) : tasks?.map(t => (
                <button
                  key={t.id}
                  onClick={() => setSelectedTask(t)}
                  className={`w-full text-left px-4 py-3 border-b border-zinc-800 hover:bg-zinc-800/60 transition-colors relative ${
                    selectedTask?.id === t.id ? 'bg-primary-900/20 border-l-4 border-l-primary-500' : 'border-l-4 border-l-transparent'
                  }`}
                >
                  {t.dataset_count > 0 && (
                    <span className="absolute top-2 right-3 flex items-center gap-1 text-xs text-emerald-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
                      {t.dataset_count} 个版本
                    </span>
                  )}
                  <div className="text-sm font-semibold text-zinc-100 leading-snug pr-16">
                    {t.alias || t.key}
                  </div>
                  {t.alias && (
                    <div className="text-xs text-zinc-500 font-mono mt-0.5">{t.key}</div>
                  )}
                  <div className="mt-1 flex items-center flex-wrap gap-1">
                    {t.category && <CategoryBadge category={t.category} />}
                    <span className={`px-1.5 py-0.5 rounded text-xs ${t.type === 'custom' ? 'bg-primary-900/30 text-primary-400' : 'bg-purple-900/30 text-purple-400'}`}>{t.type}</span>
                    {t.is_llm_judge && <span className="px-1.5 py-0.5 rounded text-xs bg-amber-900/30 text-amber-400">LLM Judge</span>}
                  </div>
                </button>
              ))}
            </CardBody>
          </Card>
        </div>

        {/* 右侧数据集 */}
        <div className="flex-1 min-w-0">
          {selectedTask ? (
            <div>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-zinc-100">{selectedTask.alias || selectedTask.key}</h3>
                  {selectedTask.alias && (
                    <p className="text-xs text-zinc-500 font-mono mt-0.5">{selectedTask.key}</p>
                  )}
                  {selectedTask.category && (
                    <div className="mt-1"><CategoryBadge category={selectedTask.category} /></div>
                  )}
                </div>
                <button className="btn-primary flex items-center gap-2" onClick={() => setUploadOpen(true)}>
                  <Upload size={16} /> 上传数据集
                </button>
              </div>
              <Card>
                <CardBody className="p-0">
                  <table className="min-w-full divide-y divide-zinc-800">
                    <thead className="bg-zinc-800/50">
                      <tr>
                        {['Tag', '默认', 'Hash', '上传时间', '备注'].map(h => (
                          <th key={h} className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800">
                      {datasets?.length === 0 ? (
                        <tr><td colSpan={5} className="px-4 py-4 text-sm text-zinc-500">暂无数据集版本</td></tr>
                      ) : datasets?.map(d => (
                        <tr key={d.id} className="hover:bg-zinc-800/40 transition-colors">
                          <td className="px-4 py-3 text-sm font-medium text-zinc-100">{d.tag}</td>
                          <td className="px-4 py-3 text-sm">{d.is_default ? <Check size={16} className="text-emerald-400" /> : '-'}</td>
                          <td className="px-4 py-3 text-xs text-zinc-500 font-mono truncate max-w-[120px]">{d.content_hash?.slice(0, 12)}...</td>
                          <td className="px-4 py-3 text-sm text-zinc-400">{new Date(d.uploaded_at).toLocaleString()}</td>
                          <td className="px-4 py-3 text-sm text-zinc-400">{d.note || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardBody>
              </Card>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-zinc-600">
              <Database size={48} className="mb-4" />
              <p>选择一个任务查看数据集</p>
            </div>
          )}
        </div>
      </div>

      <Modal open={uploadOpen} onClose={() => setUploadOpen(false)} title="上传数据集">
        <form onSubmit={handleUpload} className="space-y-4">
          <div>
            <label className="label">版本标签 <span className="text-red-400">*</span></label>
            <input className="input" value={uploadForm.tag} onChange={e => setUploadForm({ ...uploadForm, tag: e.target.value })} required />
          </div>
          <div>
            <label className="label">JSONL 文件 <span className="text-red-400">*</span></label>
            <input type="file" accept=".jsonl" className="input py-1.5" onChange={e => setUploadForm({ ...uploadForm, file: e.target.files[0] })} required />
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" id="is_default" checked={uploadForm.is_default} onChange={e => setUploadForm({ ...uploadForm, is_default: e.target.checked })} />
            <label htmlFor="is_default" className="text-sm text-zinc-300">设为默认版本</label>
          </div>
          <div>
            <label className="label">备注</label>
            <input className="input" value={uploadForm.note} onChange={e => setUploadForm({ ...uploadForm, note: e.target.value })} />
          </div>
          {uploadMut.isError && <p className="text-sm text-red-400">{uploadMut.error.message}</p>}
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
