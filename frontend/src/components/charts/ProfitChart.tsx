import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { ScoredSet } from '../../api/types';

interface ProfitChartProps {
  sets: ScoredSet[];
  limit?: number;
}

export function ProfitChart({ sets, limit = 10 }: ProfitChartProps) {
  const topSets = sets.slice(0, limit).map((set) => ({
    name: set.set_name.replace(' Prime Set', ''),
    profit: set.profit_margin,
    volume: set.volume,
    score: set.total_score,
  }));

  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-gray-100 mb-4">Top {limit} Profitable Sets</h3>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={topSets}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2530" />
            <XAxis type="number" stroke="#9FBCAD" />
            <YAxis
              type="category"
              dataKey="name"
              stroke="#9FBCAD"
              tick={{ fill: '#a0a0a0', fontSize: 12 }}
              width={90}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0d0810',
                border: '1px solid #2a2530',
                borderRadius: '8px',
              }}
              labelStyle={{ color: '#9FBCAD' }}
              itemStyle={{ color: '#f0f0f0' }}
              formatter={(value) => [`${(value as number).toFixed(0)} plat`, 'Profit']}
            />
            <Bar dataKey="profit" radius={[0, 4, 4, 0]}>
              {topSets.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.profit >= 0 ? '#9FBCAD' : '#f87171'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function VolumeChart({ sets, limit = 10 }: ProfitChartProps) {
  const topSets = [...sets]
    .sort((a, b) => b.volume - a.volume)
    .slice(0, limit)
    .map((set) => ({
      name: set.set_name.replace(' Prime Set', ''),
      volume: set.volume,
    }));

  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-gray-100 mb-4">Top {limit} by Volume</h3>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={topSets}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2530" />
            <XAxis type="number" stroke="#7A9DB1" />
            <YAxis
              type="category"
              dataKey="name"
              stroke="#7A9DB1"
              tick={{ fill: '#a0a0a0', fontSize: 12 }}
              width={90}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0d0810',
                border: '1px solid #2a2530',
                borderRadius: '8px',
              }}
              labelStyle={{ color: '#7A9DB1' }}
              itemStyle={{ color: '#f0f0f0' }}
              formatter={(value) => [(value as number).toLocaleString(), 'Volume (48h)']}
            />
            <Bar dataKey="volume" fill="#7A9DB1" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
