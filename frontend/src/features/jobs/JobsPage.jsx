import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Card, CardBody } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { JobLogModal } from './JobLogModal';
import { Activity, FileText, XCircle, User } from 'lucide-react';
import { userDisplay } from '../../lib/userDisplay';

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

  const { data: jobs, isLoading } = useQuery({
    queryKey: ['jobs', { status: statusFilter }],
    queryFn: () => api.jobs.list(statusFilter ? { status: statusFilter } : {}),
  });

  const cancelMut = useMutation({
    mutationFn: (id) => api.jobs.cancel(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  function openLog(id) {
    setLogJobId(id);
    setLogOpen(true);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Activity size={24} className="text-primary-600" />
          <h2 className="text-2xl font-bold text-gray-900">执行记录</h2>
        </div>
      </div>

      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <span className="text-sm text-gray-500">状态筛选:</span>
        {STATUS_FILTERS.map(f => (
          <button
            key={f.value}
            onClick={() => setStatusFilter(f.value)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              statusFilter === f.value
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <Card>
        <CardBody className="p-0">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {['ID', '类型', '状态', 'Batch', '模型', '任务', '提交人', '创建时间', '操作'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {isLoading ? (
                <tr><td colSpan={9} className="px-4 py-4 text-gray-500">加载中...</td></tr>
              ) : jobs?.length === 0 ? (
                <tr><td colSpan={9} className="px-4 py-4 text-gray-500">暂无记录</td></tr>
              ) : jobs?.map(job => (
                <tr key={job.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{job.id}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">{job.type}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm">
                    <StatusBadge status={job.status} />
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                    {job.batch_id ? (
                      <a href={`/batches/${job.batch_id}`} className="text-primary-600 hover:underline">{job.batch_id}</a>
                    ) : '-'}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{job.model_name || '-'}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{job.task_key || '-'}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                    {job.submitted_by ? (
                      <span className="flex items-center gap-1">
                        <User size={14} />
                        {userDisplay(job.submitted_by)}
                      </span>
                    ) : '-'}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                    {job.created_at ? new Date(job.created_at).toLocaleString() : '-'}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => openLog(job.id)}
                        className="p-1.5 text-gray-500 hover:text-primary-600 hover:bg-primary-50 rounded transition-colors"
                        title="查看日志"
                      >
                        <FileText size={16} />
                      </button>
                      {(job.status === 'pending' || job.status === 'running') && (
                        <button
                          onClick={() => cancelMut.mutate(job.id)}
                          disabled={cancelMut.isPending}
                          className="p-1.5 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                          title="取消任务"
                        >
                          <XCircle size={16} />
                        </button>
                      )}
                    </div>
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
