import { useRealtimeRecords } from '../hooks/useRealtimeRecords'

export function LiveFeed() {
    const records = useRealtimeRecords()
    const getRiskColor = (risk) => {
        if (risk > 0.7) return 'bg-red-100 border-red-400'
        if (risk > 0.4) return 'bg-yellow-100 border-yellow-400'
        return 'bg-green-50 border-green-300'
    }
    return (
        <div className='bg-white rounded-lg shadow p-4 h-full overflow-auto'>
            <h2 className='text-lg font-bold text-gray-800 mb-3'>Live Visit Feed</h2>
            {records.length === 0 && (
                <p className='text-gray-400 text-sm'>Waiting for first submission...</p>
            )}
            {records.map((rec) => (
                <div key={rec.id}
                    className={`border rounded-lg p-3 mb-2 ${getRiskColor(rec.dropout_risk)}`}>
                    <div className='flex justify-between items-start'>
                        <span className='font-semibold text-gray-800'>{rec.beneficiary_name}</span>
                        <span className='text-xs text-gray-400'>
                            {new Date(rec.created_at).toLocaleTimeString()}
                        </span>
                    </div>
                    <div className='text-sm text-gray-600 mt-1'>
                        BP: {rec.bp_systolic}/{rec.bp_diastolic}
                        {rec.hemoglobin && ` · Hb: ${rec.hemoglobin}`}
                        {rec.weight_kg && ` · ${rec.weight_kg}kg`}
                    </div>
                    {rec.dropout_risk > 0.7 && (
                        <span className='text-xs bg-red-500 text-white rounded px-2 py-0.5 mt-1 inline-block'>
                            HIGH RISK
                        </span>
                    )}
                </div>
            ))}
        </div>
    )
}
