import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Card, CardBody } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { JobLogModal } from './JobLogModal';
import { Activity, FileText, XCircle, AlertTriangle } from 'lucide-react';

const STATUS_FILTERS = [
  { value: '', label: '全部' },
  { value: 'pending', label: '待执行' },
  { value: 'running', label: '运行中' },
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' },
];

export function JobsPage() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState('');
  const [logJobId, setLogJobId] = useState(null);
  const [logOpen, setLogOpen] = useState(false);
  const [confirmCancelId, setConfirmCancelId] = useState(null);

  const { data: jobs, isLoading } = useQuery({
    queryKey: ['jobs', { status: statusFilter }],
    queryFn: () => api.jobs.list(statusFilter ? { status: statusFilter } : {}),
  });

  const cancelMut = useMutation({
    mutationFn: (id) => api.jobs.cancel(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] });
      setConfirmCancelId(null);
    },
  });

  function openLog(id) { setLogJobId(id); setLogOpen(true); }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Activity size={24} className="text-primary-400" />
        <h2 className="text-2xl font-bold text-zinc-100">执行记录</h2>
      </div>

      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <span className="text-sm text-zinc-500">状态筛选:</span>
        {STATUS_FILTERS.map(f => (
          <button
            key={f.value}
            onClick={() => setStatusFilter(f.value)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              statusFilter === f.value ? 'bg-primary-600 text-white' : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <Card>
        <CardBody className="p-0">
          <table className="min-w-full divide-y divide-zinc-800">
            <thead className="bg-zinc-800/50">
              <tr>
                {['ID', '类型', '状态', 'Batch', '模型', '任务', '创建时间', '日志', '操作'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {isLoading ? (
                <tr><td colSpan={9} className="px-4 py-4 text-zinc-400">加载中...</td></tr>
              ) : jobs?.length === 0 ? (
                <tr><td colSpan={9} className="px-4 py-4 text-zinc-400">暂无记录</td></tr>
              ) : jobs?.map(job => (
                <tr key={job.id} className="hover:bg-zinc-800/40 transition-colors">
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-zinc-500">{job.id}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-zinc-300">{job.type}</td>
                  <td className="px-4 py-3 whitespace-nowrap"><StatusBadge status={job.status} /></td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-zinc-500">
                    {job.batch_id ? <a href={`/batches/${job.batch_id}`} className="text-primary-400 hover:underline">{job.batch_id}</a> : '-'}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-zinc-500">{job.model_name || '-'}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-zinc-500 max-w-[160px] truncate">{job.task_key || '-'}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-zinc-500">{job.created_at ? new Date(job.created_at).toLocaleString() : '-'}</td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <button
                      onClick={() => openLog(job.id)}
                      className="flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300 hover:bg-primary-900/20 px-2 py-1 rounded transition-colors"
                    >
                      <FileText size={14} /> 查看
                    </button>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    {(job.status === 'pending' || job.status === 'running') && (
                      confirmCancelId === job.id ? (
                        <div className="flex items-center gap-1">
                          <AlertTriangle size={13} className="text-amber-400" />
                          <span className="text-xs text-zinc-400">确认取消？</span>
                          <button
                            onClick={() => cancelMut.mutate(job.id)}
                            disabled={cancelMut.isPending}
                            className="text-xs text-red-400 font-medium hover:text-red-300 px-1"
                          >确认</button>
                          <button
                            onClick={() => setConfirmCancelId(null)}
                            className="text-xs text-zinc-500 hover:text-zinc-300 px-1"
                          >取消</button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirmCancelId(job.id)}
                          className="flex items-center gap-1 text-xs text-red-500 hover:text-red-400 hover:bg-red-900/20 px-2 py-1 rounded transition-colors"
                        >
                          <XCircle size={14} /> 取消
                        </button>
                      )
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <JobLogModal jobId={logJobId} open={logOpen} onClose={() => setLogOpen(false)} />
    </div>
  );
}
