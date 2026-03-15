import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

export function useRealtimeAlerts() {
    const [alerts, setAlerts] = useState([])
    useEffect(() => {
        supabase.from('alerts').select('*')
            .order('created_at', { ascending: false }).limit(20)
            .then(({ data }) => setAlerts(data || []))
        const channel = supabase.channel('alerts-feed')
            .on('postgres_changes',
                { event: 'INSERT', schema: 'public', table: 'alerts' },
                payload => setAlerts(prev => [payload.new, ...prev.slice(0, 19)])
            ).subscribe()
        return () => supabase.removeChannel(channel)
    }, [])
    return alerts
}
