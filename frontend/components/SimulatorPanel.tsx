'use client'

import { useState } from 'react'
import { X, Activity } from 'lucide-react'
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer
} from 'recharts'

interface SimulatorPanelProps {
    isOpen: boolean
    onClose: () => void
}

export default function SimulatorPanel({ isOpen, onClose }: SimulatorPanelProps) {
    const [maskCompliance, setMaskCompliance] = useState(0)
    const [lockdownLevel, setLockdownLevel] = useState(0)
    const [loading, setLoading] = useState(false)
    const [data, setData] = useState<any>(null)

    const runSimulation = async () => {
        setLoading(true)
        try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/simulation/predict`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mask_compliance: maskCompliance / 100,
                    lockdown_level: lockdownLevel / 100
                })
            })
            const result = await res.json()

            // Format for Recharts: [{day: 1, baseline: 100, projected: 80}, ...]
            const formatted = result.baseline.map((b: any, i: number) => ({
                day: `Day ${b.day}`,
                baseline: b.infected,
                projected: result.projected[i].infected
            }))

            setData(formatted)
        } catch (e) {
            console.error(e)
        } finally {
            setLoading(false)
        }
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-x-0 bottom-0 z-[100] bg-slate-900 border-t border-slate-700 shadow-2xl h-[500px] flex flex-col transition-transform duration-300">
            {/* Header */}
            <div className="p-4 border-b border-slate-700 flex justify-between items-center bg-slate-800">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-purple-500/20 rounded-lg">
                        <Activity className="text-purple-400" />
                    </div>
                    <div>
                        <h2 className="text-xl font-bold text-white">Predictive Intervention Simulator</h2>
                        <p className="text-xs text-slate-400">SIR Model Projection (30 Days)</p>
                    </div>
                </div>
                <button onClick={onClose} className="p-2 hover:bg-slate-700 rounded-lg text-slate-400 hover:text-white transition-colors">
                    <X size={24} />
                </button>
            </div>

            <div className="flex-1 overflow-hidden grid grid-cols-1 md:grid-cols-4">
                {/* Controls */}
                <div className="p-6 bg-slate-900 border-r border-slate-800 space-y-8 overflow-y-auto">
                    <div>
                        <label className="flex justify-between text-sm font-bold text-slate-300 mb-2">
                            <span>🎭 Mask Mandate Compliance</span>
                            <span className="text-cyan-400">{maskCompliance}%</span>
                        </label>
                        <input
                            type="range" min="0" max="100"
                            value={maskCompliance} onChange={(e) => setMaskCompliance(parseInt(e.target.value))}
                            className="w-full accent-cyan-500 h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer"
                        />
                        <p className="text-xs text-slate-500 mt-2">Impact: Moderate reduction in transmission coefficient (Beta).</p>
                    </div>

                    <div>
                        <label className="flex justify-between text-sm font-bold text-slate-300 mb-2">
                            <span>🔒 Lockdown Strictness</span>
                            <span className="text-red-400">{lockdownLevel}%</span>
                        </label>
                        <input
                            type="range" min="0" max="100"
                            value={lockdownLevel} onChange={(e) => setLockdownLevel(parseInt(e.target.value))}
                            className="w-full accent-red-500 h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer"
                        />
                        <p className="text-xs text-slate-500 mt-2">Impact: High reduction. Simulates school closures & travel bans.</p>
                    </div>

                    <button
                        onClick={runSimulation}
                        disabled={loading}
                        className="w-full py-4 bg-gradient-to-r from-cyan-600 to-purple-600 hover:from-cyan-500 hover:to-purple-500 rounded-xl font-bold text-white shadow-lg transition-all"
                    >
                        {loading ? 'Simulating...' : 'Run Projection'}
                    </button>
                </div>

                {/* Chart */}
                <div className="col-span-3 p-6 bg-slate-900/50">
                    {data ? (
                        <div className="h-full w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={data}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                    <XAxis dataKey="day" stroke="#94a3b8" />
                                    <YAxis stroke="#94a3b8" />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px' }}
                                        labelStyle={{ color: '#94a3b8' }}
                                    />
                                    <Legend />
                                    <Line type="monotone" dataKey="baseline" stroke="#ef4444" strokeWidth={2} name="Do Nothing (Baseline)" dot={false} />
                                    <Line type="monotone" dataKey="projected" stroke="#22c55e" strokeWidth={2} name={`With Intervention`} dot={false} />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    ) : (
                        <div className="h-full flex flex-col items-center justify-center text-slate-500 border-2 border-dashed border-slate-700 rounded-xl">
                            <Activity size={48} className="mb-4 opacity-50" />
                            <p>Adjust parameters and click Run to see projections.</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
