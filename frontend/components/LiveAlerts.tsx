'use client'

import { useState, useEffect } from 'react'
import { Bell, AlertTriangle, X } from 'lucide-react'

export default function LiveAlerts() {
    const [alerts, setAlerts] = useState<any[]>([])
    const [expanded, setExpanded] = useState(false)
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    useEffect(() => {
        const fetchAlerts = () => {
            fetch(`${API_URL}/api/alerts/active`)
                .then(res => res.json())
                .then(data => setAlerts(data))
                .catch(err => console.error(err))
        }

        fetchAlerts()
        const interval = setInterval(fetchAlerts, 10000) // Poll every 10s
        return () => clearInterval(interval)
    }, [API_URL])

    if (alerts.length === 0) return null

    const criticalCount = alerts.filter(a => a.severity === 'CRITICAL').length

    return (
        <div className="fixed top-24 right-8 z-50 flex flex-col items-end pointer-events-none">
            {/* Badge / Toggle */}
            <button
                onClick={() => setExpanded(!expanded)}
                className={`pointer-events-auto flex items-center gap-2 px-4 py-2 rounded-full font-bold shadow-lg transition-all ${criticalCount > 0 ? 'bg-red-500 text-white animate-pulse' : 'bg-slate-800 text-slate-300 border border-slate-600'}`}
            >
                <Bell size={18} />
                <span>{alerts.length} Alerts</span>
                {criticalCount > 0 && <span className="bg-white text-red-600 text-xs px-2 rounded-full">{criticalCount} CRITICAL</span>}
            </button>

            {/* Expanded List */}
            {expanded && (
                <div className="pointer-events-auto mt-4 w-96 max-h-[400px] overflow-y-auto glass-panel rounded-xl p-2 shadow-2xl border border-white/10 backdrop-blur-xl">
                    <div className="flex justify-between items-center p-2 mb-2 border-b border-white/10">
                        <h3 className="font-bold text-white uppercase tracking-wider text-xs">System Notifications</h3>
                        <button onClick={() => setExpanded(false)} className="text-slate-400 hover:text-white"><X size={16} /></button>
                    </div>
                    <div className="space-y-2">
                        {alerts.map(alert => (
                            <div key={alert.alert_id} className={`p-3 rounded-lg border flex gap-3 ${alert.severity === 'CRITICAL' ? 'bg-red-500/10 border-red-500/30' : 'bg-orange-500/10 border-orange-500/30'}`}>
                                <AlertTriangle size={20} className={alert.severity === 'CRITICAL' ? 'text-red-500' : 'text-orange-500'} />
                                <div>
                                    <p className="text-xs font-bold text-slate-200 uppercase mb-1">{alert.severity} • {new Date(alert.created_at).toLocaleTimeString()}</p>
                                    <p className="text-sm text-slate-300 leading-tight">{alert.message}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}
