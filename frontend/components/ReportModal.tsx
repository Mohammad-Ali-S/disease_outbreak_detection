'use client'

import { useState } from 'react'
import { X, MapPin, Loader, ShieldCheck } from 'lucide-react'

interface ReportModalProps {
    isOpen: boolean
    onClose: () => void
}

export default function ReportModal({ isOpen, onClose }: ReportModalProps) {
    const [step, setStep] = useState(1)
    const [symptoms, setSymptoms] = useState<string[]>([])
    const [coords, setCoords] = useState<{ lat: number, lon: number } | null>(null)
    const [loading, setLoading] = useState(false)
    const [trustScore, setTrustScore] = useState<number | null>(null)

    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    const commonSymptoms = ['Fever', 'Cough', 'Sore Throat', 'Body Aches', 'Fatigue', 'Breathing Difficulty']

    const getLocation = () => {
        setLoading(true)
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    setCoords({
                        lat: position.coords.latitude,
                        lon: position.coords.longitude
                    })
                    setLoading(false)
                    setStep(2)
                },
                (err) => {
                    alert("Location access denied. We cannot verify your report.")
                    setLoading(false)
                }
            )
        } else {
            alert("Geolocation not supported")
            setLoading(false)
        }
    }

    const toggleSymptom = (sym: string) => {
        if (symptoms.includes(sym)) setSymptoms(symptoms.filter(s => s !== sym))
        else setSymptoms([...symptoms, sym])
    }

    const submitReport = async () => {
        if (!coords) return
        setLoading(true)
        try {
            const res = await fetch(`${API_URL}/api/public/report`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    latitude: coords.lat,
                    longitude: coords.lon,
                    symptoms: symptoms.join(',')
                })
            })

            if (res.ok) {
                const data = await res.json()
                setTrustScore(data.trust_score)
                setStep(3)
            } else {
                const err = await res.json()
                alert(`Submission Rejected: ${err.detail}`)
            }
        } catch (e) {
            alert("Network Error")
        } finally {
            setLoading(false)
        }
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm">
            <div className="glass-panel w-full max-w-md p-6 rounded-2xl relative border border-white/10 mx-4">
                <button onClick={onClose} className="absolute top-4 right-4 text-slate-400 hover:text-white"><X size={20} /></button>

                {step === 1 && (
                    <div className="text-center">
                        <div className="w-16 h-16 bg-blue-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                            <MapPin size={32} className="text-blue-400 hover:scale-110 transition-transform" />
                        </div>
                        <h2 className="text-xl font-bold text-white mb-2">Anonymous Symptom Report</h2>
                        <p className="text-slate-400 mb-6 text-sm">Help us track disease spread. We need your location to verify constraints (outliers are filtered).</p>

                        <button
                            onClick={getLocation}
                            disabled={loading}
                            className="w-full btn-primary py-3 rounded-xl flex items-center justify-center gap-2 font-bold"
                        >
                            {loading ? <Loader className="animate-spin" /> : <MapPin size={18} />}
                            {loading ? "Verifying..." : "Verify My Location"}
                        </button>
                    </div>
                )}

                {step === 2 && (
                    <div>
                        <h2 className="text-xl font-bold text-white mb-4">What are you feeling?</h2>
                        <div className="grid grid-cols-2 gap-3 mb-6">
                            {commonSymptoms.map(sym => (
                                <button
                                    key={sym}
                                    onClick={() => toggleSymptom(sym)}
                                    className={`p-3 rounded-lg border text-sm font-medium transition-all ${symptoms.includes(sym) ? 'bg-blue-600 border-blue-500 text-white' : 'bg-slate-800/50 border-slate-600 text-slate-300 hover:border-slate-400'}`}
                                >
                                    {sym}
                                </button>
                            ))}
                        </div>
                        <button
                            onClick={submitReport}
                            disabled={symptoms.length === 0 || loading}
                            className="w-full btn-primary py-3 rounded-xl font-bold disabled:opacity-50"
                        >
                            {loading ? "Analyzing..." : "Submit Securely"}
                        </button>
                    </div>
                )}

                {step === 3 && (
                    <div className="text-center">
                        <div className="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-4 animate-bounce">
                            <ShieldCheck size={32} className="text-green-400" />
                        </div>
                        <h2 className="text-xl font-bold text-white mb-2">Report Accepted</h2>
                        <p className="text-slate-400 mb-6 text-sm">
                            Thank you. Your data point has been anonymized and added to the community layer.
                        </p>
                        <div className="bg-slate-800/50 p-4 rounded-xl mb-6">
                            <p className="text-xs text-slate-500 uppercase font-bold">Data Trust Score</p>
                            <p className="text-2xl font-mono text-green-400 font-bold">{trustScore}</p>
                        </div>
                        <button onClick={onClose} className="text-slate-400 hover:text-white text-sm underline">Close</button>
                    </div>
                )}
            </div>
        </div>
    )
}
