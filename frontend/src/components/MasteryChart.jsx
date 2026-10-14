import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

function scoreColor(score) {
  if (score < 0.4) return '#d85a4a'
  if (score < 0.7) return '#d5a83b'
  return '#43846b'
}

export default function MasteryChart({ topics }) {
  return (
    <div aria-label="Topic mastery bar chart" className="mastery-chart">
      <ResponsiveContainer height="100%" width="100%">
        <BarChart data={topics} margin={{ top: 12, right: 12, left: -16, bottom: 8 }}>
          <CartesianGrid stroke="#e9e7df" strokeDasharray="3 5" vertical={false} />
          <XAxis
            axisLine={false}
            dataKey="topic"
            tick={{ fill: '#6c7169', fontSize: 12 }}
            tickLine={false}
            tickMargin={10}
          />
          <YAxis
            axisLine={false}
            domain={[0, 1]}
            tick={{ fill: '#858980', fontSize: 11 }}
            tickFormatter={(value) => `${Math.round(value * 100)}%`}
            tickLine={false}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            width={48}
          />
          <Tooltip
            contentStyle={{ border: '1px solid #e6e3d8', borderRadius: 6, fontSize: 13 }}
            formatter={(value) => [`${Math.round(value * 100)}%`, 'Mastery']}
            labelStyle={{ color: '#242922', fontWeight: 700 }}
          />
          <Bar dataKey="score" maxBarSize={54} radius={[4, 4, 0, 0]}>
            {topics.map((topic) => <Cell fill={scoreColor(topic.score)} key={topic.topic} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
