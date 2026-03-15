import { useRealtimeAlerts } from '../hooks/useRealtimeAlerts'

const severityColors = {
    high: 'bg-red-100 border-red-500 text-red-800',
    medium: 'bg-yellow-100 border-yellow-500 text-yellow-800',
    low: 'bg-blue-100 border-blue-400 text-blue-800',
}

export function AlertSidebar() {
    const alerts = useRealtimeAlerts()
    return (
        <div className='bg-white rounded-lg shadow p-4 h-full overflow-auto'>
            <h2 className='text-lg font-bold text-gray-800 mb-3'>
                Anomaly Alerts
                {alerts.length > 0 && (
                    <span className='ml-2 bg-red-500 text-white text-xs rounded-full px-2 py-0.5'>
                        {alerts.filter(a => !a.resolved).length}
                    </span>
                )}
            </h2>
            {alerts.length === 0 && <p className='text-gray-400 text-sm'>No alerts</p>}
            {alerts.map((alert) => (
                <div key={alert.id}
                    className={`border-l-4 rounded p-3 mb-2 ${severityColors[alert.severity] || severityColors.low}`}>
                    <div className='font-semibold text-sm'>
                        {alert.flag_type?.replace(/_/g, ' ').toUpperCase()}
                    </div>
                    <div className='text-xs mt-1'>{alert.flag_reason}</div>
                    <div className='text-xs text-gray-500 mt-1'>
                        Worker: {alert.worker_id} · {new Date(alert.created_at).toLocaleTimeString()}
                    </div>
                </div>
            ))}
        </div>
    )
}
