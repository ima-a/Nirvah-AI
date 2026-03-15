import { useState, useEffect } from 'react'
import { LiveFeed } from './components/LiveFeed'
import { RecordsTable } from './components/RecordsTable'
import { AuditChain } from './components/AuditChain'
import { RiskMap } from './components/RiskMap'
import './App.css'

const TABS = [
  { id: 'feed',    icon: '▶',  label: 'Live Feed' },
  { id: 'records', icon: '☰',  label: 'Records' },
  { id: 'audit',   icon: '🔒', label: 'Audit Chain' },
  { id: 'map',     icon: '🗺', label: 'Risk Map' },
]

function App() {
  const [loggedIn, setLoggedIn] = useState(false)
  const [activeTab, setActiveTab] = useState('feed')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [offlineQueueCount, setOfflineQueueCount] = useState(0)

  useEffect(() => {
    const checkQueue = () => {
      try {
        const req = indexedDB.open('nirvaah-offline', 1)
        req.onsuccess = (e) => {
          const db = e.target.result
          if (db.objectStoreNames.contains('queue')) {
            const tx = db.transaction('queue', 'readonly')
            const countReq = tx.objectStore('queue').count()
            countReq.onsuccess = (ev) => setOfflineQueueCount(ev.target.result)
          }
        }
      } catch (err) { /* indexedDB not available */ }
    }
    checkQueue()
    const interval = setInterval(checkQueue, 5000)
    return () => clearInterval(interval)
  }, [])

  const doLogin = () => {
    if (username === 'admin' && password === 'nirvaah2025') {
      setLoggedIn(true)
      setLoginError('')
    } else {
      setLoginError('Incorrect username or password. Please try again.')
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') doLogin()
  }

  if (!loggedIn) {
    return (
      <div className="login-screen">
        <div className="login-card">
          <div className="login-header">
            <div className="login-logo">
              <div className="login-logo-box">N</div>
              <div className="login-logo-name">NIRVAAH<span>.AI</span></div>
            </div>
            <div className="login-title">Supervisor Portal</div>
            <div className="login-sub">Block-level access · National Health Mission Kerala</div>
          </div>

          <div className="login-gov">
            🏛 Government of Kerala &nbsp;·&nbsp; NHM Maternal Health Division
          </div>

          <div className="field-group">
            <label className="field-label">Username</label>
            <input className="field-input" type="text" placeholder="Enter your username"
              value={username} onChange={e => setUsername(e.target.value)} onKeyDown={handleKeyDown} autoComplete="off" />
          </div>

          <div className="field-group">
            <label className="field-label">Password</label>
            <input className="field-input" type="password" placeholder="Enter your password"
              value={password} onChange={e => setPassword(e.target.value)} onKeyDown={handleKeyDown} />
          </div>

          <button className="login-btn" onClick={doLogin}>Sign In to Dashboard</button>
          {loginError && <div className="login-error">{loginError}</div>}

          <div className="login-footer">
            Secure access · All sessions are logged and audited<br />
            For access issues contact your District NHM Coordinator
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* TOP BAR */}
      <div className="topbar">
        <div className="tb-logo">
          <div className="tb-logo-box">N</div>
          <div className="tb-name">NIRVAAH<span>.AI</span></div>
        </div>

        <div className="tb-nav">
          {TABS.map(tab => (
            <button key={tab.id}
              className={`tb-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}>
              <span className="tb-tab-icon">{tab.icon}</span> {tab.label}
            </button>
          ))}
        </div>

        <div className="tb-right">
          <div className="live-pill">Live</div>
          {offlineQueueCount > 0 && (
            <div className="offline-pill">📵 {offlineQueueCount} pending</div>
          )}
          <div className="tb-user">
            <div className="tb-avatar">RS</div>
            <div className="tb-username">Dr. Rani Sharma</div>
          </div>
          <button className="tb-logout" onClick={() => setLoggedIn(false)}>Sign out</button>
        </div>
      </div>

      {/* CONTENT */}
      <div className="content">
        <div className={`page ${activeTab === 'feed' ? 'active' : ''}`}><LiveFeed /></div>
        <div className={`page ${activeTab === 'records' ? 'active' : ''}`}><RecordsTable /></div>
        <div className={`page ${activeTab === 'audit' ? 'active' : ''}`}><AuditChain /></div>
        <div className={`page ${activeTab === 'map' ? 'active' : ''}`}><RiskMap /></div>
      </div>
    </div>
  )
}

export default App
