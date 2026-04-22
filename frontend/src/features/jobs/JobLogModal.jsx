import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Modal } from '../../components/ui/Modal';
import { api } from '../../lib/api';
import { useInterval } from '../../hooks/useInterval';

export function JobLogModal({ jobId, open, onClose }) {
  const [logContent, setLogContent] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(true);

  const { data, refetch, isLoading } = useQuery({
    queryKey: ['jobs', jobId, 'log'],
    queryFn: () => api.jobs.log(jobId),
    enabled: open && !!jobId,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (data?.log != null) {
      setLogContent(data.log);
    }
  }, [data]);

  useEffect(() => {
    if (open) {
      setLogContent('');
      setAutoRefresh(true);
    }
  }, [open, jobId]);

  useInterval(() => {
    if (open && autoRefresh) {
      refetch();
    }
  }, 60000);

  return (
    <Modal open={open} onClose={onClose} title={`Job #${jobId} 日志`} size="xl">
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            自动刷新 (60s)
          </label>
          <button
            onClick={() => refetch()}
            className="text-sm text-primary-600 hover:text-primary-700 font-medium"
            disabled={isLoading}
          >
            {isLoading ? '加载中...' : '立即刷新'}
          </button>
        </div>

        <div className="bg-gray-900 text-gray-100 rounded-lg p-4 h-96 overflow-auto font-mono text-xs leading-relaxed whitespace-pre-wrap">
          {logContent || (
            <span className="text-gray-500">
              {isLoading ? '加载中...' : '暂无日志'}
            </span>
          )}
        </div>
      </div>
    </Modal>
  );
}
