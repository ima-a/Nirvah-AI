import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

export function useRealtimeRecords() {
    const [records, setRecords] = useState([])
    useEffect(() => {
        // Load the last 50 records immediately when the page opens
        supabase.from('records').select('*')
            .order('created_at', { ascending: false }).limit(50)
            .then(({ data }) => setRecords(data || []))
        // Listen for NEW records arriving in real time
        const channel = supabase.channel('records-feed')
            .on('postgres_changes',
                { event: 'INSERT', schema: 'public', table: 'records' },
                payload => setRecords(prev => [payload.new, ...prev.slice(0, 49)])
            ).subscribe()
        return () => supabase.removeChannel(channel)
    }, [])
    return records
}
