import { useRealtimeRecords } from '../hooks/useRealtimeRecords'
import { useRealtimeAlerts } from '../hooks/useRealtimeAlerts'
import { useState, useEffect } from 'react'

const PIPELINE_STEPS = [
  { icon: '🎙', label: 'STT' },
  { icon: '🧠', label: 'Extract' },
  { icon: '✓', label: 'Validate' },
  { icon: '📋', label: 'Map' },
  { icon: '💾', label: 'Sync' },
  { icon: '📊', label: 'Score' },
]

function getRiskClass(risk) {
  const r = parseFloat(risk)
  if (r >= 0.70) return 'high'
  if (r >= 0.50) return 'medium'
  return 'low'
}

function getInitials(name) {
  return (name || '??').split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase()
}

function formatTime(ts) {
  if (!ts) return '--:--:--'
  const d = new Date(ts)
  return d.toTimeString().substring(0, 8)
}

export function LiveFeed() {
  const records = useRealtimeRecords()
  const alerts = useRealtimeAlerts()
  const [clock, setClock] = useState('--:--:--')

  useEffect(() => {
    const tick = () => {
      const d = new Date()
      setClock(`${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`)
    }
    tick()
    const iv = setInterval(tick, 1000)
    return () => clearInterval(iv)
  }, [])

  // Compute summary stats
  const highRisk = records.filter(r => parseFloat(r.dropout_risk) >= 0.70).length
  const anemiaCount = records.filter(r => parseFloat(r.hemoglobin) > 0 && parseFloat(r.hemoglobin) < 11).length
  const synced = records.length

  return (
    <>
      <div className="page-head">
        <div>
          <div className="page-title">Live Submission Feed</div>
          <div className="page-sub">Real-time ASHA worker submissions · Thrissur Block · {records.length} records today</div>
        </div>
        <button className="btn btn-outline">⬇ Export Today</button>
      </div>

      <div className="feed-layout">
        {/* Main feed */}
        <div className="feed-main">
          <div className="feed-top">
            <div className="feed-label">
              <div className="feed-label-dot"></div>
              Incoming Submissions
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text3)', fontFamily: "'DM Mono', monospace" }}>{clock}</div>
          </div>
          <div className="feed-scroll">
            {records.length === 0 && (
              <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text3)', fontSize: '12px' }}>
                Waiting for first submission...
              </div>
            )}
            {records.slice(0, 8).map((rec) => {
              const risk = parseFloat(rec.dropout_risk || 0).toFixed(2)
              const rc = getRiskClass(risk)
              const bpS = rec.bp_systolic || 0
              const bpD = rec.bp_diastolic || 0
              const hb = parseFloat(rec.hemoglobin || 0)
              const hiBP = bpS >= 140 || bpD >= 90
              const anemia = hb > 0 && hb < 11
              const name = rec.beneficiary_name || 'Unknown'
              const flags = []
              if (hiBP) flags.push('High BP')
              if (anemia) flags.push('Anemia')
              if (rc === 'high') flags.push('Dropout Risk')

              return (
                <div key={rec.id} className="pipeline-card">
                  <div className="card-status-bar">
                    <div className="worker-av">{getInitials(name)}</div>
                    <div>
                      <div className="card-worker-name">{name}</div>
                      <div className="card-worker-meta">
                        {rec.visit_type?.replace(/_/g, ' ') || 'Visit'} · {rec.worker_id || 'Worker'} · {rec.next_visit_location || 'PHC'}
                      </div>
                    </div>
                    <div className="card-time">{formatTime(rec.created_at)} IST</div>
                  </div>

                  <div className="pipeline-steps">
                    {PIPELINE_STEPS.map((step, i) => (
                      <div key={i} className="pipeline-step">
                        {i > 0 && <div className="step-arrow done"></div>}
                        <div className="step-node">
                          <div className="step-icon done">{step.icon}</div>
                          <div className="step-label done">{step.label}</div>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="card-fields">
                    <div className="field-item">
                      <div className="field-key">Blood Pressure</div>
                      <div className={`field-val ${hiBP ? 'warn' : ''}`}>{bpS}/{bpD} mmHg{hiBP ? ' ⚠' : ''}</div>
                    </div>
                    <div className="field-item">
                      <div className="field-key">Haemoglobin</div>
                      <div className={`field-val ${anemia ? 'warn' : ''}`}>{hb.toFixed(1)} g/dL{anemia ? ' (Low)' : ''}</div>
                    </div>
                    <div className="field-item">
                      <div className="field-key">Weight</div>
                      <div className="field-val">{rec.weight_kg || '—'} kg</div>
                    </div>
                  </div>

                  <div className="card-footer">
                    <div className={`risk-badge ${rc}`}>{risk} — {rc.toUpperCase()} RISK</div>
                    <div className="flag-chips">
                      {flags.map((f, fi) => <span key={fi} className="flag-chip">{f}</span>)}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Right sidebar */}
        <div className="feed-sidebar">
          <div className="sidebar-section">
            <div className="sidebar-section-title">Today's Summary</div>
            <div className="stat-row">
              <span className="stat-row-label">Total visits</span>
              <span className="stat-row-val">{records.length}</span>
            </div>
            <div className="stat-row">
              <span className="stat-row-label">High risk flagged</span>
              <span className="stat-row-val red">{highRisk}</span>
            </div>
            <div className="stat-row">
              <span className="stat-row-label">Anemia alerts</span>
              <span className="stat-row-val amber">{anemiaCount}</span>
            </div>
            <div className="stat-row">
              <span className="stat-row-label">Records synced</span>
              <span className="stat-row-val green">{synced}</span>
            </div>
          </div>

          <div className="sidebar-section" style={{ paddingBottom: '8px' }}>
            <div className="sidebar-section-title">Recent Alerts</div>
          </div>
          <div className="alert-list">
            {alerts.length === 0 && (
              <div style={{ padding: '16px', fontSize: '12px', color: 'var(--text3)' }}>No alerts yet</div>
            )}
            {alerts.slice(0, 6).map(alert => {
              const sev = alert.severity === 'high' ? 'high' : 'medium'
              return (
                <div key={alert.id} className={`alert-row ${sev}`}>
                  <div className={`alert-row-type ${sev}`}>
                    {sev === 'high' ? '⚡' : '⚠'} {alert.flag_type?.replace(/_/g, ' ').toUpperCase()}
                  </div>
                  <div className="alert-row-desc">{alert.flag_reason}</div>
                  <div className="alert-row-sub">Worker: {alert.worker_id} · {formatTime(alert.created_at)}</div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </>
  )
}
