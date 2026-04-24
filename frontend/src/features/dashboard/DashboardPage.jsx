import { useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Card, CardBody } from '../../components/ui/Card';
import { FolderKanban, Activity, CheckCircle, XCircle } from 'lucide-react';

export function DashboardPage() {
  const { data: batches } = useQuery({ queryKey: ['batches'], queryFn: api.batches.list });
  const { data: jobs } = useQuery({ queryKey: ['jobs'], queryFn: api.jobs.list });

  const totalBatches = batches?.length || 0;
  const runningJobs = jobs?.filter(j => j.status === 'running').length || 0;
  const successJobs = jobs?.filter(j => j.status === 'success').length || 0;
  const failedJobs = jobs?.filter(j => j.status === 'failed').length || 0;

  const stats = [
    { label: '总批次', value: totalBatches, icon: FolderKanban, color: 'text-primary-400', bg: 'bg-primary-900/30' },
    { label: '运行中', value: runningJobs, icon: Activity, color: 'text-amber-400', bg: 'bg-amber-900/30' },
    { label: '成功', value: successJobs, icon: CheckCircle, color: 'text-emerald-400', bg: 'bg-emerald-900/30' },
    { label: '失败', value: failedJobs, icon: XCircle, color: 'text-red-400', bg: 'bg-red-900/30' },
  ];

  return (
    <div>
      <h2 className="text-2xl font-bold text-zinc-100 mb-6">仪表盘</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map(s => (
          <Card key={s.label}>
            <CardBody className="flex items-center gap-4">
              <div className={`p-3 rounded-lg ${s.bg}`}>
                <s.icon size={24} className={s.color} />
              </div>
              <div>
                <p className="text-sm text-zinc-400">{s.label}</p>
                <p className="text-2xl font-bold text-zinc-100">{s.value}</p>
              </div>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
