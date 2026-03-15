import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

export function AuditChain() {
    const [entries, setEntries] = useState([])
    useEffect(() => {
        supabase.from('audit_log').select('*')
            .order('id', { ascending: false }).limit(10)
            .then(({ data }) => setEntries(data || []))
        const channel = supabase.channel('audit-feed')
            .on('postgres_changes',
                { event: 'INSERT', schema: 'public', table: 'audit_log' },
                payload => setEntries(prev => [payload.new, ...prev.slice(0, 9)])
            ).subscribe()
        return () => supabase.removeChannel(channel)
    }, [])
    return (
        <div className='bg-white rounded-lg shadow p-4 h-full overflow-auto'>
            <h2 className='text-lg font-bold text-gray-800 mb-3'>Audit Chain</h2>
            {entries.length === 0 && <p className='text-gray-400 text-sm'>No entries yet</p>}
            {entries.map((entry, i) => (
                <div key={entry.id} className='relative pl-6 mb-3'>
                    {i < entries.length - 1 && (
                        <div className='absolute left-2 top-4 bottom-0 w-0.5 bg-gray-200'></div>
                    )}
                    <div className='absolute left-0 top-1 w-4 h-4 rounded-full bg-blue-500 border-2 border-white shadow'></div>
                    <div className='text-xs font-mono text-gray-500 truncate'>
                        {entry.hash?.substring(0, 20)}...
                    </div>
                    <div className='text-xs text-gray-600'>Record #{entry.record_id}</div>
                    <div className='text-xs text-gray-400'>
                        {new Date(entry.timestamp).toLocaleString()}
                    </div>
                </div>
            ))}
        </div>
    )
}
