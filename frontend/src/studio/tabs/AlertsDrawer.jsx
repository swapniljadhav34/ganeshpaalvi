// Slide-in list of every active stock alert, most urgent first.
import { Link } from 'react-router-dom';
import { ALERT_TONE, Badge, Empty, ErrorState, Loading, Modal, when } from '../ui';

export default function AlertsDrawer({ open, onClose, alerts }) {
  const list = alerts.data?.alerts || [];
  return (
    <Modal open={open} onClose={onClose} title={`Stock alerts (${list.length})`}>
      {alerts.isLoading ? <Loading /> : alerts.isError ? <ErrorState error={alerts.error} retry={alerts.refetch} /> : list.length === 0 ? (
        <Empty title="All clear">No stock needs attention right now.</Empty>
      ) : (
        <ul className="st-alerts">
          {list.map((a) => (
            <li key={a.id}>
              <Badge tone={ALERT_TONE[a.kind]}>{a.label}</Badge>
              <div>
                <strong>{a.item.title}</strong> <span className="st-muted">· {a.item.sku}</span>
                <p className="st-muted">{a.message} · since {when(a.raised_at)}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="st-hint"><Link to="/studio/inventory" onClick={onClose}>Open the Inventory Manager →</Link></p>
    </Modal>
  );
}
