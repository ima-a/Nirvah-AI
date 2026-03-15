import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { useRealtimeRecords } from '../hooks/useRealtimeRecords'

const DEMO_LOCATIONS = [
  [10.52, 76.21], [10.85, 76.27], [10.78, 76.65],
  [10.63, 76.08], [11.01, 76.43], [10.94, 76.18],
  [10.44, 76.56], [10.71, 76.38], [10.88, 76.53], [10.67, 76.29],
]

function getColor(risk) {
  if (risk > 0.7) return '#C0392B'
  if (risk > 0.4) return '#E67E22'
  return '#0B6B38'
}

export function RiskMap() {
  const records = useRealtimeRecords()

  const highCount = records.filter(r => parseFloat(r.dropout_risk) >= 0.70).length
  const anomCount = records.filter(r => parseFloat(r.dropout_risk) >= 0.40 && parseFloat(r.dropout_risk) < 0.70).length
  const lowCount = records.filter(r => parseFloat(r.dropout_risk) < 0.40).length
  const total = records.length || 1

  return (
    <>
      <div className="page-head" style={{ flexShrink: 0 }}>
        <div>
          <div className="page-title">Dropout Risk Map</div>
          <div className="page-sub">Kerala district-level risk heatmap</div>
        </div>
        <div className="map-legend">
          <div className="map-legend-item">
            <div className="map-legend-dot" style={{ background: '#C0392B' }}></div> High Dropout Risk
          </div>
          <div className="map-legend-item">
            <div className="map-legend-dot" style={{ background: '#E67E22' }}></div> Anomaly Flagged
          </div>
          <div className="map-legend-item">
            <div className="map-legend-dot" style={{ background: '#0B6B38' }}></div> Routine
          </div>
        </div>
      </div>

      <div className="map-layout" style={{ height: 'calc(100% - 65px)' }}>
        {/* Map */}
        <div className="map-container">
          <MapContainer center={[10.85, 76.27]} zoom={9}
            style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
            <TileLayer url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png' />
            {records.map((rec, i) => (
              <CircleMarker key={rec.id}
                center={DEMO_LOCATIONS[i % DEMO_LOCATIONS.length]}
                radius={parseFloat(rec.dropout_risk) > 0.7 ? 10 : 7}
                pathOptions={{
                  color: getColor(parseFloat(rec.dropout_risk)),
                  fillColor: getColor(parseFloat(rec.dropout_risk)),
                  fillOpacity: 0.7
                }}>
                <Popup>
                  <b>{rec.beneficiary_name}</b><br />
                  BP: {rec.bp_systolic}/{rec.bp_diastolic}<br />
                  Risk: {(parseFloat(rec.dropout_risk) * 100).toFixed(0)}%
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>

        {/* Sidebar */}
        <div className="map-sidebar">
          <div className="map-sidebar-head">
            <div className="map-sidebar-head-title">Risk Breakdown</div>
          </div>

          <div className="map-stat">
            <div className="map-stat-row">
              <span className="map-stat-label">High Risk Beneficiaries</span>
              <span className="map-stat-val" style={{ color: 'var(--red)' }}>{highCount}</span>
            </div>
            <div className="map-bar">
              <div className="map-bar-fill" style={{ background: 'var(--red)', width: `${(highCount / total) * 100}%` }}></div>
            </div>
          </div>

          <div className="map-stat">
            <div className="map-stat-row">
              <span className="map-stat-label">Anomaly Flagged</span>
              <span className="map-stat-val" style={{ color: '#E67E22' }}>{anomCount}</span>
            </div>
            <div className="map-bar">
              <div className="map-bar-fill" style={{ background: '#E67E22', width: `${(anomCount / total) * 100}%` }}></div>
            </div>
          </div>

          <div className="map-stat">
            <div className="map-stat-row">
              <span className="map-stat-label">Routine</span>
              <span className="map-stat-val" style={{ color: 'var(--green)' }}>{lowCount}</span>
            </div>
            <div className="map-bar">
              <div className="map-bar-fill" style={{ background: 'var(--green)', width: `${(lowCount / total) * 100}%` }}></div>
            </div>
          </div>

          <div className="map-sidebar-head">
            <div className="map-sidebar-head-title">Flagged Locations</div>
          </div>

          <div className="map-list">
            {records.filter(r => parseFloat(r.dropout_risk) >= 0.50).slice(0, 10).map(r => (
              <div key={r.id} className="map-list-item">
                <div style={{ fontWeight: 600, fontSize: '12px', color: 'var(--text1)' }}>
                  {r.beneficiary_name || 'Unknown'}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text3)' }}>
                  Risk: {(parseFloat(r.dropout_risk) * 100).toFixed(0)}% · {r.next_visit_location || 'PHC'} · {r.worker_id || '—'}
                </div>
              </div>
            ))}
            {records.filter(r => parseFloat(r.dropout_risk) >= 0.50).length === 0 && (
              <div className="map-list-item" style={{ color: 'var(--text3)', fontSize: '12px' }}>
                No flagged locations
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
