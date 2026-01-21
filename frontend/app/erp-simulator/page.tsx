'use client'

import { useState, useEffect, useRef } from 'react'
import { Activity, Send, Play, Square, Settings, Database, Wifi } from 'lucide-react'

export default function ERPSimulator() {
    // State
    const [apiKey, setApiKey] = useState('')
    const [isSimulating, setIsSimulating] = useState(false)
    const [logs, setLogs] = useState<string[]>([])
    const [simSpeed, setSimSpeed] = useState(2000)

    // Form State
    const [name, setName] = useState('')
    const [age, setAge] = useState('')
    const [gender, setGender] = useState('M')
    const [symptoms, setSymptoms] = useState<string[]>([])

    const intervalRef = useRef<NodeJS.Timeout | null>(null)
    const logsEndRef = useRef<HTMLDivElement>(null)

    // Scroll logs
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [logs])

    const SYMPTOMS_LIST = ["Fever", "Cough", "Shortness of Breath", "Fatigue", "Headache", "Sore Throat", "Running Nose"]

    const addLog = (msg: string) => {
        setLogs(prev => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev].slice(0, 50))
    }

    const generateRandomPatient = () => {
        const randomSymptoms = SYMPTOMS_LIST.sort(() => 0.5 - Math.random()).slice(0, Math.floor(Math.random() * 3) + 1)
        return {
            event_type: "ADMISSION",
            patient_id_hash: Math.random().toString(36).substring(7),
            age: Math.floor(Math.random() * 80) + 5,
            gender: Math.random() > 0.5 ? 'M' : 'F',
            admission_date: new Date().toISOString().split('T')[0],
            symptoms: randomSymptoms.join(", "),
            diagnosis: Math.random() > 0.7 ? "FLU_POS" : "FLU_NEG"
        }
    }

    const sendData = async (payload: any) => {
        if (!apiKey) {
            addLog("❌ Error: Missing API Key")
            return
        }

        try {
            const apiPayload = {
                api_key: apiKey,
                event_type: "ADMISSION",
                data: payload
            }

            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/connect/admission`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(apiPayload)
            })

            if (res.ok) {
                addLog(`✅ Data Sent: ${payload.patient_id_hash} (${payload.diagnosis})`)
            } else {
                addLog(`⚠️ Failed: ${res.status} ${res.statusText}`)
            }
        } catch (e) {
            addLog(`❌ Network Error: ${(e as Error).message}`)
        }
    }

    const handleManualSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        const payload = {
            event_type: "ADMISSION",
            patient_id_hash: Math.random().toString(36).substring(7),
            age: parseInt(age),
            gender: gender,
            admission_date: new Date().toISOString().split('T')[0],
            symptoms: symptoms.join(", "),
            diagnosis: "PENDING" // Manual entry usually pending
        }
        await sendData(payload)
        // Reset form
        setName('')
        setAge('')
        setSymptoms([])
    }

    const toggleSimulation = () => {
        if (isSimulating) {
            if (intervalRef.current) clearInterval(intervalRef.current)
            setIsSimulating(false)
            addLog("🛑 Simulation Stopped")
        } else {
            addLog("🚀 Simulation Started")
            setIsSimulating(true)
            intervalRef.current = setInterval(() => {
                const p = generateRandomPatient()
                sendData(p)
            }, simSpeed)
        }
    }

    // Cleanup
    useEffect(() => {
        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current)
        }
    }, [])

    return (
        <div className="min-h-screen bg-slate-200 text-slate-800 font-sans">
            {/* Header - Enterprise Style */}
            <header className="bg-slate-800 text-white p-4 shadow-md border-b-4 border-blue-500">
                <div className="container mx-auto flex justify-between items-center">
                    <div className="flex items-center gap-3">
                        <div className="bg-blue-600 p-2 rounded">
                            <Database size={24} className="text-white" />
                        </div>
                        <div>
                            <h1 className="text-xl font-bold tracking-tight">General Hospital EMS</h1>
                            <p className="text-xs text-slate-400 font-mono">v4.2.1 | Connected to OutbreakNet</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2 px-3 py-1 bg-slate-900 rounded border border-slate-700">
                            <Settings size={14} className="text-slate-400" />
                            <input
                                type="text"
                                placeholder="Paste API Key Here..."
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                className="bg-transparent border-none focus:outline-none text-sm text-green-400 font-mono w-64"
                            />
                        </div>
                        <div className={`h-3 w-3 rounded-full ${apiKey ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                    </div>
                </div>
            </header>

            <main className="container mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Manual Entry Column */}
                <div className="bg-white rounded-lg shadow-sm border border-slate-300 p-6">
                    <h2 className="text-lg font-bold text-slate-700 mb-4 flex items-center gap-2">
                        <Activity className="text-blue-600" /> Patient Admission (Manual)
                    </h2>

                    <form onSubmit={handleManualSubmit} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-600">Patient Name (Internal Ref)</label>
                            <input type="text" value={name} onChange={e => setName(e.target.value)} className="w-full p-2 border border-slate-300 rounded focus:border-blue-500 outline-none" placeholder="Doe, John" />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-600">Age</label>
                                <input type="number" value={age} onChange={e => setAge(e.target.value)} className="w-full p-2 border border-slate-300 rounded" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-600">Gender</label>
                                <select value={gender} onChange={e => setGender(e.target.value)} className="w-full p-2 border border-slate-300 rounded">
                                    <option value="M">Male</option>
                                    <option value="F">Female</option>
                                </select>
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-600 mb-2">Symptoms</label>
                            <div className="grid grid-cols-2 gap-2">
                                {SYMPTOMS_LIST.map(sym => (
                                    <label key={sym} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-slate-50 p-1 rounded">
                                        <input
                                            type="checkbox"
                                            checked={symptoms.includes(sym)}
                                            onChange={(e) => {
                                                if (e.target.checked) setSymptoms([...symptoms, sym])
                                                else setSymptoms(symptoms.filter(s => s !== sym))
                                            }}
                                            className="rounded text-blue-600 focus:ring-blue-500"
                                        />
                                        {sym}
                                    </label>
                                ))}
                            </div>
                        </div>

                        <button type="submit" className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded flex items-center justify-center gap-2 transition-all">
                            <Send size={18} /> Admit Patient
                        </button>
                    </form>
                </div>

                {/* Simulation Control */}
                <div className="lg:col-span-2 space-y-6">
                    <div className="bg-white rounded-lg shadow-sm border border-slate-300 p-6 flex items-center justify-between">
                        <div>
                            <h2 className="text-lg font-bold text-slate-700 flex items-center gap-2">
                                <Wifi className="text-purple-600" /> Auto-Simulation Mode
                            </h2>
                            <p className="text-sm text-slate-500">Automatically generate and push random patient records to the API.</p>
                        </div>

                        <div className="flex items-center gap-4">
                            <div className="flex flex-col items-end">
                                <span className="text-xs font-bold text-slate-500 uppercase">Speed: {simSpeed}ms</span>
                                <input
                                    type="range" min="200" max="5000" step="100"
                                    value={simSpeed} onChange={e => setSimSpeed(Number(e.target.value))}
                                    className="w-32 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-purple-600"
                                />
                            </div>
                            <button
                                onClick={toggleSimulation}
                                className={`px-6 py-3 rounded-lg font-bold text-white flex items-center gap-2 transition-all shadow-lg ${isSimulating ? 'bg-red-500 hover:bg-red-600' : 'bg-purple-600 hover:bg-purple-700'}`}
                            >
                                {isSimulating ? <><Square size={18} fill="currentColor" /> Stop Simulation</> : <><Play size={18} fill="currentColor" /> Start Simulation</>}
                            </button>
                        </div>
                    </div>

                    {/* Console / Network Log */}
                    <div className="bg-slate-900 rounded-lg shadow-inner overflow-hidden flex flex-col h-[400px]">
                        <div className="bg-slate-950 px-4 py-2 border-b border-slate-800 flex justify-between items-center">
                            <span className="text-xs font-mono text-slate-400">NETWORK LOGS (Outgoing :8000)</span>
                            <span className="text-xs font-mono text-green-500 flex items-center gap-1">
                                <span className="h-2 w-2 bg-green-500 rounded-full animate-pulse"></span> ONLINE
                            </span>
                        </div>
                        <div className="flex-1 p-4 font-mono text-xs overflow-y-auto space-y-1">
                            {logs.length === 0 && <span className="text-slate-600 italic">Waiting for events...</span>}
                            {logs.map((log, i) => (
                                <div key={i} className={`border-l-2 pl-2 ${log.includes('Failed') || log.includes('Error') ? 'border-red-500 text-red-400' : 'border-green-500 text-green-400'}`}>
                                    {log}
                                </div>
                            ))}
                            <div ref={logsEndRef} />
                        </div>
                    </div>
                </div>

            </main>
        </div>
    )
}
