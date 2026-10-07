interface Props {
  label: string;
  offset: number;
  count: number;
  total: number;
  pageSize: number;
  loading: boolean;
  onChange: (offset: number) => void;
}

export default function Pagination({ label, offset, count, total, pageSize, loading, onChange }: Props) {
  return (
    <nav aria-label={`${label} pages`} className="flex flex-wrap items-center gap-3 my-3 text-sm text-gray-300">
      <span>{label}: {count ? offset + 1 : 0}–{offset + count} of {total}</span>
      <button type="button" disabled={loading || offset === 0} onClick={() => onChange(Math.max(0, offset - pageSize))}
        className="rounded border border-gray-600 px-3 py-1 disabled:opacity-40">Previous</button>
      <button type="button" disabled={loading || offset + pageSize >= total} onClick={() => onChange(offset + pageSize)}
        className="rounded border border-gray-600 px-3 py-1 disabled:opacity-40">Next</button>
    </nav>
  );
}
