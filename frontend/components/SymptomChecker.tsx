"use client"

import { useState } from 'react'
import { X, Thermometer, Activity, AlertTriangle, CheckCircle, ShieldAlert } from 'lucide-react'

interface SymptomCheckerProps {
    isOpen: boolean
    onClose: () => void
}

export default function SymptomChecker({ isOpen, onClose }: SymptomCheckerProps) {
    const [step, setStep] = useState<'intro' | 'form' | 'result'>('intro')
    const [answers, setAnswers] = useState({
        fever: false,
        cough: false,
        breathing: false,
        sore_throat: false,
        body_aches: false,
        contact: false
    })

    if (!isOpen) return null

    const handleCheck = (key: keyof typeof answers) => {
        setAnswers(prev => ({ ...prev, [key]: !prev[key] }))
    }

    const calculateRisk = () => {
        const { fever, cough, breathing, sore_throat, body_aches, contact } = answers

        // Flu Definitions (CDC-like)
        // High Risk: Severe respiratory issues OR combination of contact + high fever
        if ((fever && breathing) || (contact && fever)) return "High"

        // Moderate: Typical Flu combo
        if ((fever && (cough || sore_throat || body_aches))) return "Moderate"

        // Low: Isolated symptoms
        if (fever || cough || contact || sore_throat) return "Low"
        return "None"
    }

    const getResult = () => {
        const risk = calculateRisk()
        switch (risk) {
            case "High":
                return {
                    color: "bg-red-500",
                    title: "High Risk Detected",
                    icon: <ShieldAlert size={48} className="text-red-500" />,
                    msg: "Your symptoms indicate a potential serious infection or high exposure risk. Please visit the nearest hospital triage immediately."
                }
            case "Moderate":
                return {
                    color: "bg-orange-500",
                    title: "Moderate Risk",
                    icon: <AlertTriangle size={48} className="text-orange-500" />,
                    msg: "You are showing some symptoms. Isolate yourself and monitor your temperature for the next 24 hours. If breathing becomes difficult, seek help."
                }
            default:
                return {
                    color: "bg-green-500",
                    title: "Low Risk",
                    icon: <CheckCircle size={48} className="text-green-500" />,
                    msg: "Your responses do not indicate an immediate threat. Continue to practice social distancing and good hygiene."
                }
        }
    }

    const reset = () => {
        setStep('intro')
        setAnswers({ fever: false, cough: false, breathing: false, sore_throat: false, body_aches: false, contact: false })
        onClose()
    }

    return (
        <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
            <div className="glass-panel bg-slate-900/90 w-full max-w-md rounded-2xl shadow-[0_0_50px_rgba(0,243,255,0.1)] overflow-hidden animate-in fade-in zoom-in duration-200 border border-white/10">
                {/* Header */}
                <div className="flex justify-between items-center p-4 border-b border-slate-700 bg-slate-900/50">
                    <h2 className="text-xl font-bold flex items-center gap-2 text-blue-400">
                        <Activity size={20} /> Influenza Screener
                    </h2>
                    <button onClick={reset} className="text-slate-400 hover:text-white transition-colors">
                        <X size={20} />
                    </button>
                </div>

                {/* Content */}
                <div className="p-6">
                    {step === 'intro' && (
                        <div className="text-center space-y-6">
                            <div className="w-20 h-20 bg-blue-500/10 rounded-full flex items-center justify-center mx-auto">
                                <Thermometer size={40} className="text-blue-400" />
                            </div>
                            <div>
                                <h3 className="text-lg font-semibold text-white mb-2">Flu Self-Assessment</h3>
                                <p className="text-slate-400 text-sm">
                                    Answer a few questions to assess your likelihood of having Influenza. This tool is for informational purposes only.
                                </p>
                            </div>
                            <button
                                onClick={() => setStep('form')}
                                className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg transition-all"
                            >
                                Start Assessment
                            </button>
                        </div>
                    )}

                    {step === 'form' && (
                        <div className="space-y-6">
                            <p className="text-slate-300 font-medium">Do you have any of the following?</p>

                            <div className="space-y-3">
                                <label className={`flex items-center gap-4 p-4 rounded-xl border cursor-pointer transition-all ${answers.fever ? 'bg-blue-600/20 border-blue-500' : 'bg-slate-900 border-slate-700 hover:border-slate-500'}`}>
                                    <input type="checkbox" checked={answers.fever} onChange={() => handleCheck('fever')} className="w-5 h-5 accent-blue-500" />
                                    <span className="text-white">Fever (over 100.4°F / 38°C)</span>
                                </label>

                                <label className={`flex items-center gap-4 p-4 rounded-xl border cursor-pointer transition-all ${answers.cough ? 'bg-blue-600/20 border-blue-500' : 'bg-slate-900 border-slate-700 hover:border-slate-500'}`}>
                                    <input type="checkbox" checked={answers.cough} onChange={() => handleCheck('cough')} className="w-5 h-5 accent-blue-500" />
                                    <span className="text-white">Persistent Dry Cough</span>
                                </label>

                                <label className={`flex items-center gap-4 p-4 rounded-xl border cursor-pointer transition-all ${answers.breathing ? 'bg-blue-600/20 border-blue-500' : 'bg-slate-900 border-slate-700 hover:border-slate-500'}`}>
                                    <input type="checkbox" checked={answers.breathing} onChange={() => handleCheck('breathing')} className="w-5 h-5 accent-blue-500" />
                                    <span className="text-white">Difficulty Breathing</span>
                                </label>

                                <label className={`flex items-center gap-4 p-4 rounded-xl border cursor-pointer transition-all ${answers.sore_throat ? 'bg-blue-600/20 border-blue-500' : 'bg-slate-900 border-slate-700 hover:border-slate-500'}`}>
                                    <input type="checkbox" checked={answers.sore_throat} onChange={() => handleCheck('sore_throat')} className="w-5 h-5 accent-blue-500" />
                                    <span className="text-white">Sore Throat</span>
                                </label>

                                <label className={`flex items-center gap-4 p-4 rounded-xl border cursor-pointer transition-all ${answers.body_aches ? 'bg-blue-600/20 border-blue-500' : 'bg-slate-900 border-slate-700 hover:border-slate-500'}`}>
                                    <input type="checkbox" checked={answers.body_aches} onChange={() => handleCheck('body_aches')} className="w-5 h-5 accent-blue-500" />
                                    <span className="text-white">Body Aches</span>
                                </label>

                                <label className={`flex items-center gap-4 p-4 rounded-xl border cursor-pointer transition-all ${answers.contact ? 'bg-blue-600/20 border-blue-500' : 'bg-slate-900 border-slate-700 hover:border-slate-500'}`}>
                                    <input type="checkbox" checked={answers.contact} onChange={() => handleCheck('contact')} className="w-5 h-5 accent-blue-500" />
                                    <span className="text-white">Contact with active cluster?</span>
                                </label>
                            </div>

                            <button
                                onClick={() => setStep('result')}
                                className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg transition-all"
                            >
                                See Results
                            </button>
                        </div>
                    )}

                    {step === 'result' && (
                        <div className="text-center space-y-6 animate-in slide-in-from-bottom-5 fade-in duration-300">
                            <div className="flex justify-center">
                                <div className={`p-4 rounded-full bg-slate-900 border-4 border-slate-800 ${getResult().color.replace('bg-', 'border-').replace('500', '500/30')}`}>
                                    {getResult().icon}
                                </div>
                            </div>

                            <div>
                                <h3 className={`text-2xl font-bold mb-2 ${getResult().color.replace('bg-', 'text-')}`}>
                                    {getResult().title}
                                </h3>
                                <p className="text-slate-300 leading-relaxed">
                                    {getResult().msg}
                                </p>
                            </div>

                            <button
                                onClick={reset}
                                className="w-full py-3 bg-slate-700 hover:bg-slate-600 text-white font-bold rounded-lg transition-all"
                            >
                                Close
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
