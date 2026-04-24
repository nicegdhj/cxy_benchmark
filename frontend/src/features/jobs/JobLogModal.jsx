import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Modal } from '../../components/ui/Modal';
import { api } from '../../lib/api';
import { useInterval } from '../../hooks/useInterval';
import { Download } from 'lucide-react';

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
          <label className="flex items-center gap-2 text-sm text-zinc-400 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            自动刷新 (60s)
          </label>
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                if (!logContent) return;
                const blob = new Blob([logContent], { type: 'text/plain;charset=utf-8' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `job-${jobId}.txt`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              disabled={!logContent}
              className="flex items-center gap-1 text-sm text-zinc-400 hover:text-zinc-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <Download size={14} /> 下载 .txt
            </button>
            <button
              onClick={() => refetch()}
              className="text-sm text-primary-400 hover:text-primary-300 font-medium transition-colors"
              disabled={isLoading}
            >
              {isLoading ? '加载中...' : '立即刷新'}
            </button>
          </div>
        </div>

        <div className="bg-zinc-950 text-zinc-200 rounded-lg p-4 max-h-[60vh] min-h-[300px] overflow-auto font-mono text-xs leading-relaxed whitespace-pre-wrap border border-zinc-800">
          {logContent || (
            <span className="text-zinc-600">
              {isLoading ? '加载中...' : '暂无日志'}
            </span>
          )}
        </div>
      </div>
    </Modal>
  );
}
