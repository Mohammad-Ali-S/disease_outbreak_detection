'use client'

import { useState, useEffect } from 'react'
import 'leaflet/dist/leaflet.css'
import dynamic from 'next/dynamic'
import { useRouter } from 'next/navigation'
import RiskSidebar from '../components/RiskSidebar'
import SymptomChecker from '../components/SymptomChecker'
import LiveAlerts from '../components/LiveAlerts'

// Dynamically import Leaflet map to avoid SSR issues
const MapComponent = dynamic(() => import('../components/ClusterMap'), { ssr: false })
import ReportModal from '../components/ReportModal'
import SimulatorPanel from '../components/SimulatorPanel'

export default function Dashboard() {
    const router = useRouter()
    const [showChecker, setShowChecker] = useState(false)
    const [showReport, setShowReport] = useState(false)
    const [showSim, setShowSim] = useState(false)
    // Auth state
    const [token, setToken] = useState<string | null>(null)
    const [role, setRole] = useState<string | null>(null)

    // Data state
    const [stats, setStats] = useState<any>(null)
    const [clusters, setClusters] = useState<any[]>([])
    const [network, setNetwork] = useState<any[]>([])
    const [loading, setLoading] = useState(true)
    const [hospitals, setHospitals] = useState<any[]>([])

    // Use relative URL for single-port deployment
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    // State for Time-Lapse
    const [history, setHistory] = useState<any>({})
    const [dates, setDates] = useState<string[]>([])
    const [sliderIndex, setSliderIndex] = useState<number>(-1)
    const [isPlaying, setIsPlaying] = useState(false)

    useEffect(() => {
        // Check Auth
        const storedToken = localStorage.getItem('token')
        const storedRole = localStorage.getItem('role')
        setToken(storedToken)
        setRole(storedRole)

        // Function to fetch latest data
        const fetchDashboardData = () => {
            fetch(`${API_URL}/api/public/dashboard`)
                .then(res => res.json())
                .then(data => {
                    setStats(data.stats)
                    if (data.analysis) {
                        setClusters(data.analysis.clusters || [])
                        setNetwork(data.analysis.network || [])
                    }
                    if (data.hospitals_list) {
                        setHospitals(data.hospitals_list)
                    }
                    setLoading(false)
                })
                .catch(err => {
                    console.error("Dashboard load error", err)
                    setLoading(false)
                })
        }

        // Initial fetch
        fetchDashboardData()

        // Poll every 2 seconds for "Live" effect
        const interval = setInterval(fetchDashboardData, 2000)

        // Fetch History only once
        fetch(`${API_URL}/api/public/history`)
            .then(res => res.json())
            .then(data => {
                setHistory(data)
                const sortedDates = Object.keys(data).sort()
                setDates(sortedDates)
                setSliderIndex(sortedDates.length - 1)
            })

        return () => clearInterval(interval)

    }, [API_URL])

    // Playback Logic
    useEffect(() => {
        let interval: any;
        if (isPlaying && sliderIndex < dates.length - 1) {
            interval = setInterval(() => {
                setSliderIndex(prev => {
                    if (prev >= dates.length - 1) {
                        setIsPlaying(false)
                        return prev
                    }
                    return prev + 1
                })
            }, 800) // 800ms per day
        } else if (sliderIndex >= dates.length - 1) {
            setIsPlaying(false)
        }
        return () => clearInterval(interval)
    }, [isPlaying, sliderIndex, dates])


    const handleLogout = () => {
        localStorage.removeItem('token')
        localStorage.removeItem('role')
        localStorage.removeItem('username')
        router.push('/login')
    }

    return (
        <div className="min-h-screen text-slate-100 p-6 md:p-8 relative">
            <div className="mesh-bg fixed inset-0 pointer-events-none" />
            <LiveAlerts />

            {/* Header */}
            <div className="relative z-10 flex flex-col md:flex-row justify-between items-center mb-10 gap-4">
                <div>
                    <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-purple-500">
                        NEXUS <span className="text-white font-light">Flu-View</span>
                    </h1>
                    <p className="text-slate-400 mt-2 flex items-center gap-2 text-sm uppercase tracking-widest">
                        <span className="relative flex h-3 w-3">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                        </span>
                        Influenza Surveillance System
                    </p>
                </div>
                <div className="flex gap-4">
                    <button
                        onClick={() => setShowChecker(true)}
                        className="btn-primary px-6 py-2 rounded-full font-semibold shadow-lg shadow-purple-500/10 flex items-center gap-2"
                    >
                        <span className="text-xl">🩺</span> Check Symptoms
                    </button>
                    <button
                        onClick={() => setShowReport(true)}
                        className="px-6 py-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 rounded-full font-bold shadow-lg shadow-purple-500/30 transition-all flex items-center gap-2"
                    >
                        <span className="text-xl">📢</span> Report
                    </button>
                    {token ? (
                        <div className="flex items-center gap-4 glass-panel px-4 py-2 rounded-full">
                            <span className="text-sm text-cyan-300 font-mono">
                                {role === 'admin' ? 'CMD::ADMIN' : 'USR::VIEWER'}
                            </span>
                            {role === 'admin' && (
                                <button
                                    onClick={() => router.push('/hospital')}
                                    className="text-sm hover:text-white transition-colors border-l border-white/20 pl-4"
                                >
                                    Portal
                                </button>
                            )}
                            <button
                                onClick={handleLogout}
                                className="text-sm text-red-400 hover:text-red-300 transition-colors border-l border-white/20 pl-4"
                            >
                                Logout
                            </button>
                        </div>
                    ) : (
                        <button
                            onClick={() => router.push('/login')}
                            className="px-6 py-2 border border-cyan-500/50 text-cyan-400 hover:bg-cyan-500/10 rounded-full transition-all text-sm font-medium tracking-wide"
                        >
                            Staff Login
                        </button>
                    )}
                </div>
            </div>

            {/* Stats Grid */}
            <div className="relative z-10 grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                {[
                    { label: 'Flu Active Sites', value: stats?.hospitals || 0, color: 'text-cyan-400', unit: 'Hospitals' },
                    { label: 'Total Flu Cases', value: stats?.total_visits || 0, color: 'text-white', unit: 'Confirmed Positive' },
                    { label: 'System Stress', value: (stats?.system_stress || 0) + '%', color: (stats?.system_stress > 80) ? 'text-red-500' : 'text-orange-400', unit: 'ICU Utilization' },
                    { label: 'System Alert Level', value: stats?.risk_level || 'NOMINAL', color: (stats?.risk_level === 'CRITICAL') ? 'text-red-500 animate-pulse' : (stats?.risk_level === 'ELEVATED') ? 'text-orange-400' : 'text-green-400', unit: 'Real-time Status' }
                ].map((stat, i) => (
                    <div key={i} className="glass-panel p-6 rounded-2xl relative overflow-hidden group">
                        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                            <div className={`w-16 h-16 rounded-full ${stat.color.includes('red') ? 'bg-red-500' : stat.color.includes('cyan') ? 'bg-cyan-500' : 'bg-white'}`} />
                        </div>
                        <p className="text-slate-400 text-xs font-bold uppercase tracking-widest mb-1">{stat.label}</p>
                        <p className={`text-3xl font-bold font-mono ${stat.color} text-shadow`}>{stat.value}</p>
                        <p className="text-xs text-slate-500 mt-1">{stat.unit}</p>
                    </div>
                ))}
            </div>

            {/* Main Content Area */}
            <div className="relative z-10 grid grid-cols-1 lg:grid-cols-4 gap-6">

                {/* Map Section (3/4 width) */}
                <div className="lg:col-span-3 glass-panel rounded-2xl overflow-hidden min-h-[600px] relative flex flex-col p-1">
                    <div className="flex-grow relative rounded-xl overflow-hidden">
                        <MapComponent
                            clusters={clusters.length > 0 ? clusters : []}
                            network={network}
                            hospitals={hospitals}
                            dailyData={(sliderIndex >= 0 && dates[sliderIndex]) ? history[dates[sliderIndex]] : []}
                        />
                        {/* Overlay for instructions */}
                        <div className="absolute top-4 right-4 glass-panel p-4 rounded-xl z-[1000] border-l-4 border-cyan-500">
                            <h3 className="font-bold text-xs mb-2 text-cyan-400 uppercase tracking-wider">Map Legend</h3>
                            <div className="space-y-2">
                                <div className="flex items-center gap-2 text-xs text-slate-300">
                                    <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.8)]"></div> Active Facility
                                </div>
                                <div className="flex items-center gap-2 text-xs text-slate-300">
                                    <div className="w-2 h-2 rounded-full bg-red-500 border border-red-200 shadow-[0_0_10px_rgba(239,68,68,0.8)]"></div> Outbreak Origin
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Time Slider Control */}
                    {dates.length > 0 && (
                        <div className="p-4 bg-black/20 backdrop-blur-sm border-t border-white/5 flex items-center gap-6">
                            <button
                                onClick={() => {
                                    if (sliderIndex >= dates.length - 1) setSliderIndex(0);
                                    setIsPlaying(!isPlaying);
                                }}
                                className="w-12 h-12 flex items-center justify-center rounded-full bg-cyan-600 hover:bg-cyan-500 text-white transition-all shadow-[0_0_15px_rgba(8,145,178,0.5)] border border-cyan-400"
                            >
                                {isPlaying ? '❚❚' : '▶'}
                            </button>
                            <div className="flex-grow">
                                <div className="flex justify-between text-xs text-cyan-300 font-mono mb-2">
                                    <span>START: {dates[0]}</span>
                                    <span className="text-white font-bold text-lg glow">{dates[sliderIndex]}</span>
                                    <span>END: {dates[dates.length - 1]}</span>
                                </div>
                                <input
                                    type="range"
                                    min="0"
                                    max={dates.length - 1}
                                    value={sliderIndex}
                                    onChange={(e) => {
                                        setSliderIndex(parseInt(e.target.value));
                                        setIsPlaying(false);
                                    }}
                                    className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                                />
                            </div>
                        </div>
                    )}
                </div>

                {/* Sidebar - Risk Zones */}
                <div className="h-[600px] glass-panel rounded-2xl p-1">
                    <RiskSidebar
                        clusters={clusters}
                        onSelectCluster={(lat, lon) => {
                            console.log("Pan to", lat, lon)
                        }}
                    />
                </div>
            </div>

            <SymptomChecker isOpen={showChecker} onClose={() => setShowChecker(false)} />
            <ReportModal isOpen={showReport} onClose={() => setShowReport(false)} />
            <SimulatorPanel isOpen={showSim} onClose={() => setShowSim(false)} />
        </div>
    )
}
