import { useEffect, useState } from 'react'
import { LiveFeed } from './components/LiveFeed'
import { AlertSidebar } from './components/AlertSidebar'
import { AuditChain } from './components/AuditChain'
import { RiskMap } from './components/RiskMap'

function App() {
  const [offlineQueueCount, setOfflineQueueCount] = useState(0);

  useEffect(() => {
    const checkQueue = () => {
      const req = indexedDB.open('nirvaah-offline', 1);
      req.onsuccess = (e) => {
        const db = e.target.result;
        if (db.objectStoreNames.contains('queue')) {
          const tx = db.transaction('queue', 'readonly');
          const countReq = tx.objectStore('queue').count();
          countReq.onsuccess = (e) => setOfflineQueueCount(e.target.result);
        }
      };
    };
    checkQueue();
    const interval = setInterval(checkQueue, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className='min-h-screen bg-gray-100 p-4'>
      {/* Header */}
      <div className='mb-4 flex items-center justify-between'>
        <div>
          <h1 className='text-2xl font-bold text-blue-900'>Nirvaah AI</h1>
          <p className='text-sm text-gray-500'>Supervisor Dashboard ┬╖ Kerala</p>
        </div>
        <div className='flex items-center gap-3'>
          {offlineQueueCount > 0 && (
            <div className='flex items-center gap-1 bg-orange-100 text-orange-700 text-xs px-2 py-1 rounded-full'>
              <span>📵</span>
              <span>{offlineQueueCount} pending sync</span>
            </div>
          )}
          <div className='flex items-center gap-2'>
            <span className='w-2 h-2 rounded-full bg-green-500'></span>
            <span className='text-sm text-gray-600'>Live</span>
          </div>
        </div>
      </div>
      {/* Main grid: 3 columns */}
      <div className='grid grid-cols-3 gap-4 h-[calc(100vh-120px)]'>
        <div className='col-span-1'><LiveFeed /></div>
        <div className='col-span-1 flex flex-col gap-4'>
          <RiskMap />
          <AuditChain />
        </div>
        <div className='col-span-1'><AlertSidebar /></div>
      </div>
    </div>
  )
}

export default App
