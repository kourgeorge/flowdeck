import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface DailyDataPoint {
  date: string;
  count: number;
}

interface DailyBarChartProps {
  data: DailyDataPoint[];
  color: string;
  label: string;
}

export default function DailyBarChart({ data, color, label }: DailyBarChartProps) {
  return (
    <div className="flex-1 min-w-[300px] rounded-lg border border-gray-700 bg-gray-800/80 p-4">
      <h3 className="text-sm font-semibold text-white mb-3">{label}</h3>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="date"
            stroke="#9ca3af"
            fontSize={11}
            tick={{ fill: '#9ca3af' }}
          />
          <YAxis
            stroke="#9ca3af"
            fontSize={11}
            tick={{ fill: '#9ca3af' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1f2937',
              border: '1px solid #374151',
              borderRadius: '0.5rem',
              color: '#f3f4f6',
              fontSize: '0.875rem',
            }}
            labelStyle={{ color: '#d1d5db' }}
          />
          <Bar dataKey="count" fill={color} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// Made with Bob
