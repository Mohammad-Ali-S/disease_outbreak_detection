'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, Trash2, Calendar, Activity, AlertTriangle, ArrowLeft, Upload, Download, BarChart2, Bed, FileText, Eye, EyeOff, Copy, Search } from 'lucide-react'
import { Line } from 'react-chartjs-2'

import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
} from 'chart.js'

ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend
)

function PredictionChart({ token, apiUrl }: { token: string | null, apiUrl: string }) {
    const [chartData, setChartData] = useState<any>(null)

    useEffect(() => {
        if (!token) return
        const load = async () => {
            try {
                const res = await fetch(`${apiUrl}/api/hospital/predict?days=7`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                })
                if (!res.ok) return
                const data = await res.json()
                // Assuming data is array of { ds, yhat } or { date, value }
                if (Array.isArray(data)) {
                    setChartData({
                        labels: data.map((d: any) => d.ds ? d.ds.split('T')[0] : (d.date || d.admission_date)),
                        datasets: [
                            {
                                label: 'Predicted Flux',
                                data: data.map((d: any) => d.yhat || d.value || 0),
                                borderColor: 'rgb(34, 197, 94)',
                                backgroundColor: 'rgba(34, 197, 94, 0.5)',
                                tension: 0.4
                            }
                        ]
                    })
                }
            } catch (e) {
                console.error(e)
            }
        }
        load()
    }, [token, apiUrl])

    if (!chartData) return <div className="flex items-center justify-center h-full text-slate-500 text-sm">Initializing AI Model...</div>
    return (
        <div className="h-[300px] w-full">
            <Line options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }} data={chartData} />
        </div>
    )
}

export default function HospitalPortal() {
    const router = useRouter()
    const [token, setToken] = useState<string | null>(null)
    const [activeTab, setActiveTab] = useState('overview') // overview, admissions, operations

    // Data State
    const [entries, setEntries] = useState<any[]>([])
    const [analytics, setAnalytics] = useState<any[]>([])
    const [capacity, setCapacity] = useState({ total_beds: 100, occupied_beds: 0, icu_beds: 20, ventilators: 10 })
    const [loading, setLoading] = useState(true)

    // Forms
    const [date, setDate] = useState(new Date().toISOString().split('T')[0])
    const [isFlu, setIsFlu] = useState(false)
    const [submitting, setSubmitting] = useState(false)
    const [file, setFile] = useState<File | null>(null)
    const [uploadStatus, setUploadStatus] = useState('')

    // Alert State
    const [alertData, setAlertData] = useState<any>(null)

    // Profile State
    const [profile, setProfile] = useState({
        name: '',
        city: '',
        region: '',
        latitude: '',
        longitude: ''
    })
    const [profileLoading, setProfileLoading] = useState(false)
    const [successMessage, setSuccessMessage] = useState('')

    // Search State
    const [searchQuery, setSearchQuery] = useState('')
    const [searchResults, setSearchResults] = useState<any[]>([])
    const [isSearching, setIsSearching] = useState(false)

    // Debounce Effect
    useEffect(() => {
        const timer = setTimeout(() => {
            if (searchQuery.length > 3) {
                searchHospitals(searchQuery)
            } else {
                setSearchResults([])
            }
        }, 500)

        return () => clearTimeout(timer)
    }, [searchQuery])

    const [showKey, setShowKey] = useState(false)

    // Use environment variable for API URL, defaulting to localhost:8000
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    useEffect(() => {
        const t = localStorage.getItem('token')
        const role = localStorage.getItem('role')

        if (!t) { router.push('/login'); return }
        if (role !== 'admin') { alert("Access Denied"); router.push('/'); return }

        setToken(t)
        fetchData(t)
        checkAlerts(t)
        fetchProfile(t)
        fetchKey(t)

        // Poll for new admissions every 30 seconds
        const interval = setInterval(() => {
            fetchData(t)
            checkAlerts(t)
        }, 30000)

        return () => clearInterval(interval)
    }, [router, API_URL])

    const fetchKey = async (authToken: string) => {
        try {
            const res = await fetch(`${API_URL}/api/hospital/key`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            })
            if (res.ok) {
                const data = await res.json()
                setApiKey(data.api_secret)
            }
        } catch (e) { console.error(e) }
    }

    const generateKey = async () => {
        if (!confirm("Warning: Generating a new key will INVALIDATE the old one. Your ERP connection will stop until you update it. Proceed?")) return

        try {
            const res = await fetch(`${API_URL}/api/hospital/key`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            })
            if (res.status === 401) {
                alert("Session Expired. Please login again.")
                localStorage.removeItem('token')
                router.push('/login')
                return
            }
            if (res.ok) {
                const data = await res.json()
                setApiKey(data.api_secret)
                alert("New Secure Key Generated")
            }
        } catch (e) { console.error(e) }
    }

    const fetchProfile = async (authToken: string) => {
        try {
            const res = await fetch(`${API_URL}/api/hospital/profile`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            })
            if (res.ok) {
                const data = await res.json()
                // Default to 0 if not set, or keep existing
                setProfile({
                    name: data.name || '',
                    city: data.city || '',
                    region: data.region || '',
                    latitude: data.latitude ? data.latitude.toString() : '',
                    longitude: data.longitude ? data.longitude.toString() : ''
                })
            }
        } catch (e) { console.error("Profile fetch error", e) }
    }

    const handleSearchLocation = async () => {
        if (!profile.city && !profile.name) {
            alert("Please enter a Hospital Name and City first")
            return
        }
        setProfileLoading(true)
        try {
            const query = `${profile.name}, ${profile.city}`
            const res = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=1`)
            const data = await res.json()

            if (data && data.length > 0) {
                const { lat, lon } = data[0]
                setProfile({
                    ...profile,
                    latitude: lat,
                    longitude: lon
                })
                alert(`Location Found: ${lat}, ${lon}`)
            } else {
                alert("Location not found. Please try adding more details (Region) or enter manually.")
            }
        } catch (e) {
            console.error(e)
            alert("Geocoding failed")
        } finally {
            setProfileLoading(false)
        }
    }

    const searchHospitals = async (query: string) => {
        if (!query) return
        setIsSearching(true)
        try {
            // Use Backend Proxy to avoid CORS and add correct headers
            const res = await fetch(`${API_URL}/api/hospital/search?q=${encodeURIComponent(query)}`)
            const data = await res.json()
            setSearchResults(data)
        } catch (e) {
            console.error("Search failed", e)
        } finally {
            setIsSearching(false)
        }
    }

    const selectHospital = (item: any) => {
        const addr = item.address || {}
        setProfile({
            ...profile,
            name: item.name || item.display_name.split(',')[0],
            city: addr.city || addr.town || addr.village || '',
            region: addr.state || addr.county || '',
            latitude: item.lat,
            longitude: item.lon
        })
        setSearchResults([])
        setSearchQuery('')
    }



    const handleUpdateProfile = async () => {
        setProfileLoading(true)
        console.log("Saving to:", `${API_URL}/api/hospital/profile`)
        try {
            const payload = {
                ...profile,
                latitude: parseFloat(profile.latitude) || 0,
                longitude: parseFloat(profile.longitude) || 0
            }

            const res = await fetch(`${API_URL}/api/hospital/profile`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify(payload)
            })
            if (res.ok) {
                setSuccessMessage("Profile Updated Successfully")
            } else {
                const err = await res.text()
                console.error("Save failed", res.status, err)
                alert(`Failed to update profile: ${res.status}`)
            }
        } catch (e) {
            console.error(e)
            alert("Error updating profile")
        } finally {
            setProfileLoading(false)
        }
    }

    const checkAlerts = async (authToken: string) => {
        try {
            const res = await fetch(`${API_URL}/api/hospital/alerts`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            })
            const data = await res.json()
            if (data.alert) {
                setAlertData(data)
            }
        } catch (e) { console.error("Alert check failed", e) }
    }

    const fetchData = async (authToken: string) => {
        try {
            // Parallel fetch
            const [recRes, capRes, anaRes] = await Promise.all([
                fetch(`${API_URL}/api/patients/recent`, { headers: { 'Authorization': `Bearer ${authToken}` } }),
                fetch(`${API_URL}/api/hospital/capacity`, { headers: { 'Authorization': `Bearer ${authToken}` } }),
                fetch(`${API_URL}/api/hospital/analytics`, { headers: { 'Authorization': `Bearer ${authToken}` } })
            ])

            if (recRes.status === 401 || capRes.status === 401 || anaRes.status === 401) {
                alert("Session Expired. Please login again.")
                localStorage.removeItem('token') // force logout
                router.push('/login')
                return
            }

            if (recRes.ok) setEntries(await recRes.json())
            if (capRes.ok) setCapacity(await capRes.json())
            if (anaRes.ok) setAnalytics(await anaRes.json())

        } catch (e) {
            console.error(e)
        } finally {
            setLoading(false)
        }
    }

    // --- Handlers ---

    const handleAddPatient = async (e: React.FormEvent) => {
        e.preventDefault()
        setSubmitting(true)
        try {
            const res = await fetch(`${API_URL}/api/patients`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ admission_date: date, is_flu_positive: isFlu })
            })
            if (res.ok) {
                fetchData(token!)
                setIsFlu(false)
                alert("Record Added Successfully")
            } else {
                const err = await res.json()
                console.error("Add Patient Failed:", err)
                alert(`Failed to add record: ${JSON.stringify(err.detail || err)}`)
            }
        } catch (e: any) {
            console.error(e)
            alert(`Network Error: ${e.message}`)
        } finally { setSubmitting(false) }
    }

    const handleDelete = async (id: number) => {
        if (!confirm("Delete this record?")) return
        console.log(`[DELETE] Attempting to delete patient ${id} at ${API_URL}/api/patients/${id}`)
        try {
            const res = await fetch(`${API_URL}/api/patients/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            })
            console.log(`[DELETE] Response status: ${res.status}`)

            if (res.ok) {
                setEntries(entries.filter(e => e.patient_id !== id))
            } else {
                const text = await res.text()
                console.error(`[DELETE] Failed: ${text}`)
                alert(`Delete failed (Status: ${res.status}): ${text}`)
            }
        } catch (e: any) {
            console.error("[DELETE] Network Error:", e)
            alert(`Network Error during delete: ${e.message}\nCheck console for details.`)
        }
    }

    const handleDischarge = async (id: number) => {
        try {
            const res = await fetch(`${API_URL}/api/patients/${id}/status`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ status: 'Recovered' })
            })
            if (res.ok) {
                // Optimistic update
                setEntries(entries.map(e => e.patient_id === id ? { ...e, status: 'Recovered' } : e))
            }
        } catch (e) { console.error(e) }
    }

    const handleUpdateCapacity = async () => {
        try {
            await fetch(`${API_URL}/api/hospital/capacity`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify(capacity)
            })
            alert("Capacity Updated")
        } catch (e) { console.error(e) }
    }

    const handleFileUpload = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!file) return
        setUploadStatus('Uploading...')
        const formData = new FormData()
        formData.append('file', file)

        try {
            const res = await fetch(`${API_URL}/api/hospital/upload`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            })
            const data = await res.json()
            if (res.ok) {
                setUploadStatus(`Success! Imported ${data.imported} records.`)
                fetchData(token!)
            } else {
                setUploadStatus(`Error: ${data.detail}`)
            }
        } catch (e) { setUploadStatus('Upload failed') }
    }

    // --- Chart Config ---
    const chartData = {
        labels: analytics.map(d => d.admission_date),
        datasets: [
            {
                label: 'Total Admissions',
                data: analytics.map(d => d.count),
                borderColor: 'rgb(59, 130, 246)',
                backgroundColor: 'rgba(59, 130, 246, 0.5)',
            },
            {
                label: 'Flu Positive',
                data: analytics.map(d => d.flu_positive),
                borderColor: 'rgb(239, 68, 68)',
                backgroundColor: 'rgba(239, 68, 68, 0.5)',
            },
        ],
    }

    return (
        <div className="min-h-screen text-slate-100 p-8 relative">
            <div className="mesh-bg fixed inset-0 pointer-events-none" />

            {/* Alert Banner */}
            {alertData && (
                <div className="relative z-10 max-w-6xl mx-auto mb-6 glass-panel border-l-4 border-red-500 p-4 flex items-center gap-3 animate-pulse-slow">
                    <div className="bg-red-500/20 p-2 rounded-full">
                        <Activity size={24} className="text-red-400" />
                    </div>
                    <div>
                        <h3 className="font-bold text-lg text-red-400">Cluster Alert: {alertData.risk_level} Risk</h3>
                        <p className="text-slate-300">{alertData.message}</p>
                    </div>
                </div>
            )}

            {/* Header */}
            <div className="relative z-10 max-w-6xl mx-auto mb-8 flex flex-col md:flex-row justify-between items-center gap-4">
                <div>
                    <button onClick={() => router.push('/')} className="flex items-center text-cyan-400 hover:text-cyan-300 mb-2 text-sm transition-colors uppercase tracking-wider font-bold">
                        <ArrowLeft size={16} className="mr-1" /> Back to Dashboard
                    </button>
                    <h1 className="text-3xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-cyan-300">
                        Hospital Admin Portal
                    </h1>
                </div>
                <div className="flex gap-2 p-1 glass-panel rounded-full relative">
                    {['overview', 'admissions', 'operations', 'settings'].map(tab => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`px-6 py-2 rounded-full capitalize font-medium transition-all ${activeTab === tab ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-500/30' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}
                        >
                            {tab}
                        </button>
                    ))}
                </div>
            </div>

            <div className="relative z-10 max-w-6xl mx-auto">

                {/* TAB: OVERVIEW */}
                {activeTab === 'overview' && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {/* Status Cards */}
                        <div className="glass-panel p-6 rounded-2xl relative overflow-hidden">
                            <h3 className="text-cyan-300 text-xs font-bold uppercase tracking-widest mb-2">Current Occupancy</h3>
                            <div className="flex items-end gap-2">
                                <span className="text-5xl font-mono font-bold text-white">{capacity.occupied_beds}</span>
                                <span className="text-slate-500 mb-1 font-mono">/ {capacity.total_beds}</span>
                            </div>
                            <div className="w-full bg-slate-800/50 h-2 rounded-full mt-4 overflow-hidden border border-white/5">
                                <div
                                    className={`h-full rounded-full shadow-[0_0_10px_currentColor] transition-all duration-1000 ${capacity.occupied_beds / capacity.total_beds > 0.8 ? 'bg-red-500 text-red-500' : 'bg-cyan-500 text-cyan-500'}`}
                                    style={{ width: `${Math.min((capacity.occupied_beds / capacity.total_beds) * 100, 100)}%` }}
                                ></div>
                            </div>
                        </div>

                        <div className="glass-panel p-6 rounded-2xl">
                            <h3 className="text-blue-300 text-xs font-bold uppercase tracking-widest mb-2">7-Day Admissions</h3>
                            <div className="text-5xl font-mono font-bold text-blue-400 text-shadow">
                                {analytics.reduce((sum, d) => sum + d.count, 0)}
                            </div>
                            <p className="text-xs text-slate-500 mt-2">Total new patients this week</p>
                        </div>

                        <div className="glass-panel p-6 rounded-2xl">
                            <h3 className="text-purple-300 text-xs font-bold uppercase tracking-widest mb-2">Flu Positivity Rate</h3>
                            <div className="text-5xl font-mono font-bold text-purple-400 text-shadow">
                                {analytics.length ? Math.round((analytics.reduce((s, d) => s + d.flu_positive, 0) / analytics.reduce((s, d) => s + d.count, 1)) * 100) : 0}%
                            </div>
                            <p className="text-xs text-slate-500 mt-2">Of tested patients</p>
                        </div>

                        {/* Chart */}
                        <div className="md:col-span-3 glass-panel p-6 rounded-2xl">
                            <h3 className="text-lg font-semibold mb-6 text-white border-b border-white/10 pb-2">Admission Trends</h3>
                            <div className="h-[300px] w-full">
                                {analytics.length > 0 ? <Line options={{ responsive: true, maintainAspectRatio: false }} data={chartData} /> : <div className="flex items-center justify-center h-full text-slate-500">No data available</div>}
                            </div>
                        </div>
                    </div>
                )}

                {/* TAB: ADMISSIONS */}
                {activeTab === 'admissions' && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                        {/* Form */}
                        <div className="glass-panel p-6 rounded-2xl h-fit">
                            <h2 className="text-xl font-semibold mb-6 flex items-center gap-2 text-cyan-400"><Plus size={20} /> New Admission</h2>
                            <form onSubmit={handleAddPatient} className="space-y-6">
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Date of Admission</label>
                                    <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-full bg-slate-900/50 border border-slate-600 rounded-lg p-3 outline-none focus:border-cyan-500 text-white" required />
                                </div>
                                <div onClick={() => setIsFlu(!isFlu)} className={`cursor-pointer p-4 rounded-xl border transition-all flex justify-between items-center ${isFlu ? 'bg-red-500/10 border-red-500 shadow-[0_0_15px_rgba(239,68,68,0.2)]' : 'bg-slate-900/50 border-slate-600 hover:border-slate-500'}`}>
                                    <span className={isFlu ? 'text-red-400 font-bold' : 'text-slate-400'}>Flu Positive Diagnosis</span>
                                    <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all ${isFlu ? 'bg-red-500 border-red-500' : 'border-slate-500'}`}>{isFlu && <Activity size={14} className="text-white" />}</div>
                                </div>
                                <button disabled={submitting} className="w-full btn-primary py-3 rounded-xl font-bold uppercase tracking-wider text-sm">{submitting ? 'Saving...' : 'Add Record'}</button>
                            </form>
                        </div>
                        {/* List */}
                        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl min-h-[500px]">
                            <h2 className="text-xl font-semibold mb-6 text-white border-b border-white/10 pb-4 flex items-center gap-2">
                                <span className="relative flex h-3 w-3">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                                </span>
                                Live Patient Pipeline
                            </h2>
                            <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse">
                                    <thead><tr className="text-slate-400 uppercase text-xs tracking-wider"><th className="p-4">Date</th><th className="p-4">Diagnosis</th><th className="p-4">Status</th><th className="p-4 text-right">Action</th></tr></thead>
                                    <tbody className="divide-y divide-white/5">
                                        {entries.map(e => (
                                            <tr key={e.patient_id} className="hover:bg-white/5 transition-colors">
                                                <td className="p-4 font-mono text-sm">{e.admission_date}</td>
                                                <td className="p-4">{e.is_flu_positive ? <span className="inline-flex items-center px-2 py-1 rounded bg-red-500/20 text-red-400 text-xs font-bold uppercase border border-red-500/30">Positive</span> : <span className="inline-flex items-center px-2 py-1 rounded bg-green-500/20 text-green-400 text-xs font-bold uppercase border border-green-500/30">Negative</span>}</td>
                                                <td className="p-4">
                                                    <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-bold uppercase border ${e.status === 'Recovered' ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30' : 'bg-amber-500/20 text-amber-400 border-amber-500/30'}`}>
                                                        {e.status || 'Admitted'}
                                                    </span>
                                                </td>
                                                <td className="p-4 text-right flex justify-end gap-2">
                                                    {e.status !== 'Recovered' && (
                                                        <button onClick={() => handleDischarge(e.patient_id)} className="px-3 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold transition-colors">
                                                            Discharge
                                                        </button>
                                                    )}
                                                    <button onClick={() => handleDelete(e.patient_id)} className="text-slate-500 hover:text-red-400 transition-colors"><Trash2 size={16} /></button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                )}

                {/* TAB: OPERATIONS */}
                {activeTab === 'operations' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                        {/* Prediction Chart */}
                        <div className="md:col-span-2 glass-panel p-6 rounded-2xl">
                            <h2 className="text-xl font-semibold mb-6 flex items-center gap-2 text-green-400"><Activity size={20} /> 7-Day Admission Forecast</h2>
                            <PredictionChart token={token} apiUrl={API_URL} />
                        </div>

                        {/* Capacity Management */}
                        <div className="glass-panel p-6 rounded-2xl">
                            <h2 className="text-xl font-semibold mb-6 flex items-center gap-2 text-blue-400 border-b border-white/10 pb-2"><Bed size={20} /> Resource Management</h2>
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase mb-2">Total Bed Capacity</label>
                                    <input
                                        type="number"
                                        value={capacity.total_beds}
                                        onChange={(e) => setCapacity({ ...capacity, total_beds: parseInt(e.target.value) })}
                                        className="w-full bg-slate-900/50 border border-slate-600 rounded-lg p-3 text-white focus:border-blue-500 outline-none font-mono"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 uppercase mb-2">Currently Occupied (General)</label>
                                    <input
                                        type="number"
                                        value={capacity.occupied_beds}
                                        onChange={(e) => setCapacity({ ...capacity, occupied_beds: parseInt(e.target.value) })}
                                        className="w-full bg-slate-900/50 border border-slate-600 rounded-lg p-3 text-white focus:border-blue-500 outline-none font-mono"
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-xs font-bold text-slate-400 uppercase mb-2">ICU Capacity</label>
                                        <input
                                            type="number"
                                            value={capacity.icu_beds}
                                            onChange={(e) => setCapacity({ ...capacity, icu_beds: parseInt(e.target.value) })}
                                            className="w-full bg-slate-900/50 border border-slate-600 rounded-lg p-3 text-white focus:border-blue-500 outline-none font-mono"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-slate-400 uppercase mb-2">Ventilators</label>
                                        <input
                                            type="number"
                                            value={capacity.ventilators}
                                            onChange={(e) => setCapacity({ ...capacity, ventilators: parseInt(e.target.value) })}
                                            className="w-full bg-slate-900/50 border border-slate-600 rounded-lg p-3 text-white focus:border-blue-500 outline-none font-mono"
                                        />
                                    </div>
                                </div>
                                <button onClick={handleUpdateCapacity} className="w-full py-3 bg-blue-600 rounded-xl hover:bg-blue-500 font-bold transition-all shadow-lg shadow-blue-500/20">Update Capacity</button>
                            </div>
                        </div>

                        {/* Batch Upload */}
                        <div className="glass-panel p-6 rounded-2xl">
                            <h2 className="text-xl font-semibold mb-6 flex items-center gap-2 text-purple-400 border-b border-white/10 pb-2"><Upload size={20} /> Batch Data Import</h2>
                            <form onSubmit={handleFileUpload} className="space-y-4">
                                <div className="border-2 border-dashed border-slate-600 rounded-xl p-8 text-center hover:border-purple-500 hover:bg-purple-500/5 transition-all cursor-pointer group">
                                    <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} className="hidden" id="csv-upload" accept=".csv" />
                                    <label htmlFor="csv-upload" className="cursor-pointer block">
                                        <FileText className="mx-auto text-slate-500 mb-2 group-hover:text-purple-400 transition-colors" size={32} />
                                        <p className="text-slate-300 group-hover:text-white transition-colors">{file ? file.name : "Click to Upload CSV"}</p>
                                        <p className="text-xs text-slate-500 mt-1">Format: Date (YYYY-MM-DD), IsFlu (True/False)</p>
                                    </label>
                                </div>
                                {uploadStatus && <p className="text-center text-sm text-cyan-400">{uploadStatus}</p>}
                                <button disabled={!file} className="w-full py-3 bg-purple-600 rounded-xl hover:bg-purple-500 disabled:opacity-50 font-bold shadow-lg shadow-purple-500/20 transition-all">Upload Records</button>
                            </form>

                            <div className="mt-8 pt-6 border-t border-white/10">
                                <h3 className="font-semibold mb-4 text-sm text-slate-400 uppercase">Export Data</h3>
                                <a href={`${API_URL}/api/hospital/export?token=${token}`} target="_blank" className="flex items-center justify-center gap-2 w-full py-2 border border-slate-600 rounded-lg hover:bg-white/5 text-sm transition-colors text-slate-300 hover:text-white">
                                    <Download size={16} /> Download Full Report (CSV)
                                </a>
                            </div>
                        </div>
                    </div>
                )}

                {/* TAB: SETTINGS */}
                {activeTab === 'settings' && (
                    <div className="max-w-2xl mx-auto glass-panel p-8 rounded-2xl">
                        <h2 className="text-2xl font-bold mb-8 flex items-center gap-2 text-cyan-400 border-b border-white/10 pb-4">Facility Profile</h2>

                        {/* Search Section */}
                        <div className="mb-8 relative z-50">
                            <label className="block text-xs font-bold text-cyan-400 mb-2 uppercase tracking-wider">Search & Auto-fill Hospital Details</label>
                            <div className="relative">
                                <input
                                    type="text"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    placeholder="Type hospital name (e.g. 'Mount Sinai')..."
                                    className="w-full bg-slate-900 border border-cyan-500/30 rounded-xl p-4 pl-12 text-white focus:border-cyan-500 outline-none shadow-lg shadow-cyan-500/10 transition-all placeholder:text-slate-600"
                                />
                                <Search className="absolute left-4 top-4 text-cyan-500" size={20} />
                                {isSearching && <div className="absolute right-4 top-4 text-xs text-slate-500 animate-pulse">Searching...</div>}
                            </div>

                            {/* Search Results Dropdown */}
                            {searchResults.length > 0 && (
                                <div className="absolute top-full left-0 right-0 mt-2 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden max-h-60 overflow-y-auto">
                                    {searchResults.map((item, i) => (
                                        <div
                                            key={i}
                                            onClick={() => selectHospital(item)}
                                            className="p-4 hover:bg-white/5 cursor-pointer border-b border-white/5 last:border-0 transition-colors"
                                        >
                                            <p className="font-bold text-sm text-cyan-200">{item.display_name.split(',')[0]}</p>
                                            <p className="text-xs text-slate-500 truncate">{item.display_name}</p>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div className="space-y-6">
                            <div>
                                <label className="block text-xs font-bold text-slate-400 mb-2 uppercase">Hospital Name</label>
                                <input
                                    type="text"
                                    value={profile.name}
                                    onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                                    className="w-full bg-slate-900/50 border border-slate-600 rounded-lg p-3 text-white focus:border-cyan-500 outline-none"
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 mb-2 uppercase">City</label>
                                    <input
                                        type="text"
                                        value={profile.city}
                                        onChange={(e) => setProfile({ ...profile, city: e.target.value })}
                                        className="w-full bg-slate-900/50 border border-slate-600 rounded-lg p-3 text-white focus:border-cyan-500 outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 mb-2 uppercase">Region</label>
                                    <input
                                        type="text"
                                        value={profile.region}
                                        onChange={(e) => setProfile({ ...profile, region: e.target.value })}
                                        className="w-full bg-slate-900/50 border border-slate-600 rounded-lg p-3 text-white focus:border-cyan-500 outline-none"
                                    />
                                </div>
                            </div>

                        </div>

                        <div className="bg-slate-800/50 p-4 rounded-xl border border-white/5">
                            <div className="flex justify-between items-center mb-4">
                                <label className="text-xs font-bold text-slate-400 uppercase">Geo-Location</label>
                                <button onClick={handleSearchLocation} className="text-xs flex items-center gap-1 bg-cyan-500/10 text-cyan-400 px-3 py-1 rounded-lg border border-cyan-500/20 hover:bg-cyan-500/20 transition-all">
                                    <Activity size={12} className="animate-pulse" /> Auto-Detect via GPS
                                </button>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 mb-1 uppercase">Latitude</label>
                                    <input
                                        type="text"
                                        value={profile.latitude}
                                        onChange={(e) => setProfile({ ...profile, latitude: e.target.value })}
                                        className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-slate-300 focus:border-cyan-500 outline-none font-mono text-sm"
                                        placeholder="0.0000"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 mb-1 uppercase">Longitude</label>
                                    <input
                                        type="text"
                                        value={profile.longitude}
                                        onChange={(e) => setProfile({ ...profile, longitude: e.target.value })}
                                        className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-slate-300 focus:border-cyan-500 outline-none font-mono text-sm"
                                        placeholder="0.0000"
                                    />
                                </div>
                            </div>
                        </div>




                        {/* ERP Integration Section */}
                        <div className="bg-slate-800/50 p-6 rounded-xl border border-dashed border-slate-700/50 mb-6">
                            <div className="flex items-center gap-3 mb-4">
                                <div className="p-2 bg-purple-500/10 rounded-lg">
                                    <Activity className="text-purple-400" size={20} />
                                </div>
                                <div>
                                    <h3 className="text-lg font-bold text-white">ERP Integration</h3>
                                    <p className="text-xs text-slate-400">Connect your Hospital System (Epic/Cerner)</p>
                                </div>
                            </div>

                            <div className="space-y-4">
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 mb-1 uppercase">API Secret Key</label>
                                    <div className="flex gap-2">
                                        <div className="relative flex-1">
                                            <input
                                                type={showKey ? "text" : "password"}
                                                readOnly
                                                value={apiKey || "Not Generated"}
                                                className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-slate-300 font-mono text-sm"
                                            />
                                            <button
                                                onClick={() => setShowKey(!showKey)}
                                                className="absolute right-3 top-3 text-slate-500 hover:text-white"
                                            >
                                                {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
                                            </button>
                                        </div>
                                        <button
                                            onClick={() => {
                                                navigator.clipboard.writeText(apiKey || "")
                                                alert("Copied to clipboard!")
                                            }}
                                            className="p-3 bg-slate-700 hover:bg-slate-600 rounded-lg text-white"
                                            title="Copy Key"
                                        >
                                            <Copy size={20} />
                                        </button>
                                    </div>
                                </div>
                                <button
                                    onClick={generateKey}
                                    className="text-xs text-purple-400 hover:text-purple-300 underline font-medium"
                                >
                                    Generate New Secret Key
                                </button>
                            </div>
                        </div>

                        <div className="pt-6 border-t border-white/10">
                            <button
                                onClick={handleUpdateProfile}
                                disabled={profileLoading}
                                className="w-full py-3 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 rounded-xl font-bold transition-all shadow-lg shadow-cyan-500/20 text-white uppercase tracking-wider"
                            >
                                {profileLoading ? 'Saving...' : 'Save Configuration'}
                            </button>
                            <p className="text-xs text-slate-500 mt-4 text-center">
                                Updating location requires system re-indexing (takes ~5s).
                            </p>
                        </div>
                    </div>
                )}
                {/* Success Popup */}
                {
                    successMessage && (
                        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
                            <div className="bg-slate-900 border border-green-500/30 p-8 rounded-2xl shadow-2xl max-w-sm text-center transform scale-100 animate-in zoom-in-95 duration-200">
                                <div className="mx-auto w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mb-4">
                                    <Activity className="text-green-400" size={32} />
                                </div>
                                <h3 className="text-xl font-bold text-white mb-2">Success!</h3>
                                <p className="text-slate-300 mb-6">{successMessage}</p>
                                <button
                                    onClick={() => setSuccessMessage('')}
                                    className="bg-green-600 hover:bg-green-500 text-white px-6 py-2 rounded-lg font-bold transition-colors w-full"
                                >
                                    Awesome
                                </button>
                            </div>
                        </div>
                    )
                }
            </div>
        </div>
    )
}

