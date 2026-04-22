import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Card, CardBody } from '../../components/ui/Card';
import { Modal } from '../../components/ui/Modal';
import { Upload, Database, FileJson, Check } from 'lucide-react';

export function TasksPage() {
  const qc = useQueryClient();
  const [selectedTask, setSelectedTask] = useState(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadForm, setUploadForm] = useState({ tag: '', is_default: false, note: '', file: null });

  const { data: tasks, isLoading } = useQuery({ queryKey: ['tasks'], queryFn: api.tasks.list });
  const { data: datasets } = useQuery({
    queryKey: ['tasks', selectedTask?.id, 'datasets'],
    queryFn: () => api.tasks.datasets(selectedTask.id),
    enabled: !!selectedTask,
  });

  const uploadMut = useMutation({
    mutationFn: ({ taskId, formData }) => api.tasks.uploadDataset(taskId, formData),
    onSuccess: () => {
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
      <h2 className="text-2xl font-bold text-gray-900 mb-6">任务与数据</h2>
      <div className="flex gap-6">
        {/* 左侧任务列表 */}
        <div className="w-80 flex-shrink-0">
          <Card>
            <CardBody className="p-0">
              <div className="px-4 py-3 border-b border-gray-200 font-medium text-sm">任务列表</div>
              {isLoading ? (
                <div className="px-4 py-4 text-sm text-gray-500">加载中...</div>
              ) : tasks?.map(t => (
                <button
                  key={t.id}
                  onClick={() => setSelectedTask(t)}
                  className={`w-full text-left px-4 py-3 border-b border-gray-100 hover:bg-gray-50 transition-colors ${
                    selectedTask?.id === t.id ? 'bg-primary-50 border-l-4 border-l-primary-500' : 'border-l-4 border-l-transparent'
                  }`}
                >
                  <div className="text-sm font-medium text-gray-900">{t.key}</div>
                  <div className="text-xs text-gray-500 mt-0.5 flex items-center gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-xs ${t.type === 'custom' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>{t.type}</span>
                    {t.is_llm_judge && <span className="px-1.5 py-0.5 rounded text-xs bg-amber-100 text-amber-700">LLM Judge</span>}
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
                  <h3 className="text-lg font-semibold text-gray-900">{selectedTask.key}</h3>
                  <p className="text-sm text-gray-500">{selectedTask.suite_name}</p>
                </div>
                <button className="btn-primary flex items-center gap-2" onClick={() => setUploadOpen(true)}>
                  <Upload size={16} /> 上传数据集
                </button>
              </div>
              <Card>
                <CardBody className="p-0">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        {['Tag', '默认', 'Hash', '上传时间', '备注'].map(h => (
                          <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {datasets?.length === 0 ? (
                        <tr><td colSpan={5} className="px-4 py-4 text-sm text-gray-500">暂无数据集版本</td></tr>
                      ) : datasets?.map(d => (
                        <tr key={d.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">{d.tag}</td>
                          <td className="px-4 py-3 text-sm">{d.is_default ? <Check size={16} className="text-green-600" /> : '-'}</td>
                          <td className="px-4 py-3 text-xs text-gray-500 font-mono truncate max-w-[120px]">{d.content_hash?.slice(0, 12)}...</td>
                          <td className="px-4 py-3 text-sm text-gray-500">{new Date(d.uploaded_at).toLocaleString()}</td>
                          <td className="px-4 py-3 text-sm text-gray-500">{d.note || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardBody>
              </Card>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-gray-400">
              <Database size={48} className="mb-4" />
              <p>选择一个任务查看数据集</p>
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
            <input
              type="file" accept=".jsonl" className="input py-1.5"
              onChange={e => setUploadForm({ ...uploadForm, file: e.target.files[0] })}
              required
            />
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
