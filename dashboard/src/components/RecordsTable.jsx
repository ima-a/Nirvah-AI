import { useState } from 'react'
import { useRealtimeRecords } from '../hooks/useRealtimeRecords'

function getRiskClass(risk) {
  const r = parseFloat(risk)
  if (r >= 0.70) return 'high'
  if (r >= 0.50) return 'medium'
  return 'low'
}

export function RecordsTable() {
  const records = useRealtimeRecords()
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')

  const filtered = records.filter(r => {
    const name = (r.beneficiary_name || '').toLowerCase()
    const worker = (r.worker_id || '').toLowerCase()
    const phc = (r.next_visit_location || '').toLowerCase()
    const q = search.toLowerCase()
    const matchQ = !q || name.includes(q) || worker.includes(q) || phc.includes(q)

    const risk = parseFloat(r.dropout_risk || 0)
    const hb = parseFloat(r.hemoglobin || 0)
    const matchF = filter === 'all' ||
      (filter === 'high' && risk >= 0.70) ||
      (filter === 'medium' && risk >= 0.50 && risk < 0.70) ||
      (filter === 'anemia' && hb > 0 && hb < 11)
    return matchQ && matchF
  })

  return (
    <>
      <div className="page-head">
        <div>
          <div className="page-title">Beneficiary Records</div>
          <div className="page-sub">All submitted visit records · searchable · {filtered.length} records</div>
        </div>
        <button className="btn btn-primary">📄 Generate HMIS Report</button>
      </div>

      <div className="records-layout">
        <div className="search-bar">
          <input className="search-input" placeholder="🔍  Search by name, worker, or PHC..."
            value={search} onChange={e => setSearch(e.target.value)} />
          {['all', 'high', 'medium', 'anemia'].map(f => (
            <button key={f} className={`filter-btn ${filter === f ? 'active' : ''}`}
              onClick={() => setFilter(f)}>
              {f === 'all' ? 'All' : f === 'high' ? 'High Risk' : f === 'medium' ? 'Medium Risk' : 'Anemia'}
            </button>
          ))}
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Beneficiary</th>
                <th>Visit Type</th>
                <th>ASHA Worker</th>
                <th>BP</th>
                <th>Hb</th>
                <th>Dropout Risk</th>
                <th>Time</th>
              </tr>
            </thead>
          </table>
          <div className="scroll-tbody">
            <table>
              <tbody>
                {filtered.map(r => {
                  const risk = parseFloat(r.dropout_risk || 0).toFixed(2)
                  const rc = getRiskClass(risk)
                  const bpS = r.bp_systolic || 0
                  const bpD = r.bp_diastolic || 0
                  const hb = parseFloat(r.hemoglobin || 0)
                  const hiBP = bpS >= 140 || bpD >= 90
                  const anemia = hb > 0 && hb < 11

                  return (
                    <tr key={r.id}>
                      <td>
                        <div style={{ fontWeight: 600 }}>{r.beneficiary_name || 'Unknown'}</div>
                        <div style={{ fontSize: '11px', color: 'var(--text3)' }}>{r.next_visit_location || 'PHC'}</div>
                      </td>
                      <td style={{ color: 'var(--text2)' }}>
                        {r.visit_type?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || 'Visit'}
                      </td>
                      <td style={{ color: 'var(--text2)' }}>{r.worker_id || 'Unknown'}</td>
                      <td style={{ fontFamily: "'DM Mono', monospace", fontSize: '12px', color: hiBP ? 'var(--red)' : undefined, fontWeight: hiBP ? 600 : undefined }}>
                        {bpS}/{bpD}
                      </td>
                      <td style={{ fontFamily: "'DM Mono', monospace", fontSize: '12px', color: anemia ? 'var(--amber)' : undefined, fontWeight: anemia ? 600 : undefined }}>
                        {hb.toFixed(1)}
                      </td>
                      <td><span className={`td-badge ${rc}`}>{risk} {rc.toUpperCase()}</span></td>
                      <td style={{ fontFamily: "'DM Mono', monospace", fontSize: '11px', color: 'var(--text3)' }}>
                        {r.created_at ? new Date(r.created_at).toTimeString().substring(0, 8) : '--'}
                      </td>
                    </tr>
                  )
                })}
                {filtered.length === 0 && (
                  <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text3)', padding: '40px' }}>
                    No records match your search
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  )
}
