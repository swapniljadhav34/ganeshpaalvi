// Traffic (super admin only): first-party, cookie-free visit counts.
// Charts: one-series trend (no legend needed) with hover/focus tooltips and a table view;
// part-to-whole bars carry a text label on every segment (identity is never colour alone).
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api, qs } from '../api';
import { Empty, ErrorState, Kpi, Loading, num } from '../ui';

const PERIODS = [['24h', 'Last 24 hours'], ['7d', 'Last 7 days'], ['30d', 'Last 30 days']];

function label(t, hourly) {
  const d = new Date(hourly ? t : `${t}T00:00:00`);
  return hourly ? d.toLocaleTimeString('en-IN', { hour: '2-digit' }) : d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

function niceMax(v) {
  if (v <= 5) return 5;
  const p = 10 ** Math.floor(Math.log10(v));
  return Math.ceil(v / p) * p;
}

function TrendChart({ trend, hourly }) {
  const [hover, setHover] = useState(null);
  const [table, setTable] = useState(false);
  const max = niceMax(Math.max(...trend.map((d) => d.views), 1));
  const ticks = [max, max / 2, 0];
  return (
    <figure className="st-chart">
      <figcaption className="st-chart-title">Visits per {hourly ? 'hour' : 'day'}</figcaption>
      <div className="st-trend">
        <div className="st-trend-axis" aria-hidden="true">{ticks.map((t) => <span key={t}>{num(t)}</span>)}</div>
        <div className="st-trend-plot" role="img" aria-label={`Visits per ${hourly ? 'hour' : 'day'}, peak ${num(Math.max(...trend.map((d) => d.views)))}`}>
          {ticks.map((t) => <span key={t} className="st-grid-line" style={{ bottom: `${(t / max) * 100}%` }} aria-hidden="true" />)}
          {trend.map((d, i) => (
            <button key={d.t} type="button" className="st-bar-hit" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(i)} onBlur={() => setHover(null)} aria-label={`${label(d.t, hourly)}: ${d.views} visits, ${d.sessions} sessions`}>
              <span className="st-bar" style={{ height: `${Math.max((d.views / max) * 100, d.views ? 1.5 : 0)}%` }} />
              {hover === i && (
                <span className="st-tip" role="tooltip">
                  <strong>{label(d.t, hourly)}</strong><br />{num(d.views)} visits · {num(d.sessions)} sessions
                </span>
              )}
            </button>
          ))}
        </div>
      </div>
      <div className="st-trend-x" aria-hidden="true">
        <span>{trend[0] && label(trend[0].t, hourly)}</span><span>{trend.at(-1) && label(trend.at(-1).t, hourly)}</span>
      </div>
      <button type="button" className="st-link" onClick={() => setTable((v) => !v)} aria-expanded={table}>{table ? 'Hide' : 'Show'} as table</button>
      {table && (
        <div className="st-table-wrap">
          <table className="st-table"><thead><tr><th>{hourly ? 'Hour' : 'Day'}</th><th className="st-num">Visits</th><th className="st-num">Sessions</th></tr></thead>
            <tbody>{trend.map((d) => <tr key={d.t}><td>{label(d.t, hourly)}</td><td className="st-num">{num(d.views)}</td><td className="st-num">{num(d.sessions)}</td></tr>)}</tbody>
          </table>
        </div>
      )}
    </figure>
  );
}

/** Part-to-whole bar: segments in fixed categorical order, 2px gaps, each with a text label. */
function SplitBar({ title, parts }) {
  const total = parts.reduce((s, p) => s + p.value, 0) || 1;
  return (
    <figure className="st-chart">
      <figcaption className="st-chart-title">{title}</figcaption>
      <div className="st-split" role="img" aria-label={parts.map((p) => `${p.label} ${Math.round((p.value / total) * 100)}%`).join(', ')}>
        {parts.filter((p) => p.value > 0).map((p) => (
          <span key={p.key} style={{ flexGrow: p.value, background: `var(--series-${p.slot})` }} title={`${p.label}: ${num(p.value)}`} />
        ))}
      </div>
      <ul className="st-legend">
        {parts.map((p) => (
          <li key={p.key}><i style={{ background: `var(--series-${p.slot})` }} aria-hidden="true" />
            <span>{p.label}</span> <strong>{Math.round((p.value / total) * 100)}%</strong> <span className="st-muted">{num(p.value)}</span></li>
        ))}
      </ul>
    </figure>
  );
}

function RankList({ title, rows, empty }) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <div className="st-panel">
      <h3>{title}</h3>
      {rows.length === 0 ? <p className="st-muted">{empty}</p> : (
        <ol className="st-rank">
          {rows.map((r) => (
            <li key={r.key}>
              <span className="st-rank-name">{r.name}</span>
              <span className="st-rank-bar" aria-hidden="true"><span style={{ width: `${(r.value / max) * 100}%` }} /></span>
              <span className="st-num">{num(r.value)}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export default function Traffic() {
  const [period, setPeriod] = useState('7d');
  const res = useQuery({ queryKey: ['studio', 'traffic', period], queryFn: () => api(`/analytics/summary${qs({ period })}`), placeholderData: (p) => p });
  const d = res.data;
  const share = d ? Math.round(((d.tiers.wholesale || 0) / Math.max(d.total_views, 1)) * 100) : 0;
  return (
    <section className="st-section" aria-labelledby="tr-h">
      <div className="st-head">
        <div><h1 id="tr-h">Traffic</h1><p className="st-muted">Counted without cookies or IP addresses. Bots are ignored.</p></div>
        <div className="st-chips" role="radiogroup" aria-label="Period">
          {PERIODS.map(([k, l]) => <button key={k} type="button" role="radio" aria-checked={period === k} className={period === k ? 'is-on' : ''} onClick={() => setPeriod(k)}>{l}</button>)}
        </div>
      </div>
      {res.isLoading ? <Loading /> : res.isError ? <ErrorState error={res.error} retry={res.refetch} /> : d.total_views === 0 ? (
        <Empty title="No visits yet in this period">Visits appear here a few seconds after people open the website.</Empty>
      ) : (
        <>
          <div className="st-kpis">
            <Kpi label="Total visits" value={num(d.total_views)} />
            <Kpi label="Unique sessions" value={num(d.unique_sessions)} />
            <Kpi label="Product views" value={num(d.product_views)} sub={`${Math.round((d.product_views / d.total_views) * 100)}% of visits`} />
            <Kpi label="Wholesale traffic" value={`${share}%`} sub={`${num(d.tiers.wholesale || 0)} visits in wholesale mode`} />
          </div>
          <div className="st-panel"><TrendChart trend={d.trend} hourly={period === '24h'} /></div>
          <div className="st-grid2">
            <div className="st-panel">
              <SplitBar title="Mobile vs desktop" parts={[
                { key: 'mobile', label: 'Mobile', value: d.devices.mobile || 0, slot: 1 },
                { key: 'desktop', label: 'Desktop', value: d.devices.desktop || 0, slot: 2 },
                { key: 'tablet', label: 'Tablet', value: d.devices.tablet || 0, slot: 3 },
              ]} />
            </div>
            <div className="st-panel">
              <SplitBar title="Retail vs wholesale" parts={[
                { key: 'retail', label: 'Retail', value: d.tiers.retail || 0, slot: 1 },
                { key: 'wholesale', label: 'Wholesale', value: d.tiers.wholesale || 0, slot: 2 },
              ]} />
            </div>
          </div>
          <div className="st-grid2">
            <RankList title="Top viewed products" empty="No product views yet."
              rows={d.top_products.map((p) => ({ key: p.slug, name: p.title, value: p.views }))} />
            <RankList title="Where visitors come from" empty="Mostly direct visits so far."
              rows={d.top_referrers.map((r) => ({ key: r.host, name: r.host, value: r.views }))} />
          </div>
        </>
      )}
    </section>
  );
}
