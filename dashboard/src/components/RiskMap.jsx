import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { useRealtimeRecords } from '../hooks/useRealtimeRecords'

// Demo GPS positions in Kerala — real app uses actual beneficiary coordinates
const DEMO_LOCATIONS = [
    [10.52, 76.21], [10.85, 76.27], [10.78, 76.65],
    [10.63, 76.08], [11.01, 76.43], [10.94, 76.18],
    [10.44, 76.56], [10.71, 76.38], [10.88, 76.53], [10.67, 76.29]
]

export function RiskMap() {
    const records = useRealtimeRecords()
    const getColor = (risk) => {
        if (risk > 0.7) return '#EF4444'
        if (risk > 0.4) return '#F59E0B'
        return '#10B981'
    }
    return (
        <div className='bg-white rounded-lg shadow p-4 h-full'>
            <h2 className='text-lg font-bold text-gray-800 mb-3'>District Risk Map (Kerala)</h2>
            <MapContainer center={[10.85, 76.27]} zoom={9}
                style={{ height: '280px', borderRadius: '8px' }}>
                <TileLayer url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png' />
                {records.map((rec, i) => (
                    <CircleMarker key={rec.id}
                        center={DEMO_LOCATIONS[i % DEMO_LOCATIONS.length]}
                        radius={rec.dropout_risk > 0.7 ? 10 : 7}
                        pathOptions={{
                            color: getColor(rec.dropout_risk),
                            fillColor: getColor(rec.dropout_risk),
                            fillOpacity: 0.7
                        }}>
                        <Popup>
                            <b>{rec.beneficiary_name}</b><br />
                            BP: {rec.bp_systolic}/{rec.bp_diastolic}<br />
                            Risk: {(rec.dropout_risk * 100).toFixed(0)}%
                        </Popup>
                    </CircleMarker>
                ))}
            </MapContainer>
        </div>
    )
}
