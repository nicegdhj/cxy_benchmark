const STATUS_STYLES = {
  pending:   'bg-zinc-800 text-zinc-300',
  running:   'bg-blue-900/40 text-blue-400 ring-1 ring-blue-500/30',
  success:   'bg-emerald-900/40 text-emerald-400',
  failed:    'bg-red-900/40 text-red-400',
  cancelled: 'bg-orange-900/40 text-orange-400',
  eval_done: 'bg-teal-900/40 text-teal-400',
  infer_done:'bg-cyan-900/40 text-cyan-400',
};

export function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.pending;
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${style}`}>
      {status}
    </span>
  );
}
