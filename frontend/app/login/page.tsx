"use client"

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Lock, User, Building } from 'lucide-react'

export default function LoginPage() {
    const router = useRouter()
    const [isLogin, setIsLogin] = useState(true)
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [role, setRole] = useState('user')
    const [hospitalId, setHospitalId] = useState('')
    const [isNewFacility, setIsNewFacility] = useState(false)
    const [newHospital, setNewHospital] = useState({ name: '', city: '', region: '' })

    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    const [successMsg, setSuccessMsg] = useState('')

    // API URL - Use relative path for production (served by FastAPI) or localhost for dev
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')
        setSuccessMsg('')
        setLoading(true)

        const endpoint = isLogin ? '/api/auth/login' : '/api/auth/register'

        let body: any = { username, password }

        if (!isLogin) {
            body.role = role
            if (role === 'admin') {
                if (isNewFacility) {
                    body.hospital_name = newHospital.name
                    body.city = newHospital.city
                    body.region = newHospital.region
                } else {
                    body.hospital_id = hospitalId
                }
            }
        }

        try {
            const res = await fetch(`${API_URL}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            })

            const data = await res.json()

            if (!res.ok) {
                throw new Error(data.detail || 'Authentication failed')
            }

            if (isLogin) {
                // Login Success: Store Token & Redirect
                localStorage.setItem('token', data.access_token)
                localStorage.setItem('role', data.role)
                localStorage.setItem('username', username)
                window.location.href = '/'
            } else {
                // Registration Success: Switch to Login
                setIsLogin(true)
                setSuccessMsg('Registration successful! Please sign in with your new account.')
                setPassword('') // Clear password for security
            }

        } catch (err: any) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
            <div className="bg-gray-800 p-8 rounded-2xl shadow-2xl w-full max-w-md border border-gray-700">
                <div className="text-center mb-8">
                    <h1 className="text-3xl font-bold text-white mb-2">
                        {isLogin ? 'Welcome Back' : 'Create Account'}
                    </h1>
                    <p className="text-gray-400">
                        Disease Outbreak Detection System
                    </p>
                </div>

                {error && (
                    <div className="bg-red-500/20 border border-red-500 text-red-100 p-3 rounded-lg mb-6 text-sm">
                        {error}
                    </div>
                )}

                {successMsg && (
                    <div className="bg-green-500/20 border border-green-500 text-green-100 p-3 rounded-lg mb-6 text-sm">
                        {successMsg}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-6">
                    <div>
                        <label className="block text-gray-300 text-sm font-medium mb-2">Username</label>
                        <div className="relative">
                            <User className="absolute left-3 top-3 text-gray-500" size={18} />
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="w-full bg-gray-900 border border-gray-600 rounded-lg py-2.5 pl-10 pr-4 text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                                placeholder="Enter username"
                                required
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-gray-300 text-sm font-medium mb-2">Password</label>
                        <div className="relative">
                            <Lock className="absolute left-3 top-3 text-gray-500" size={18} />
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full bg-gray-900 border border-gray-600 rounded-lg py-2.5 pl-10 pr-4 text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                                placeholder="Enter password"
                                required
                            />
                        </div>
                    </div>

                    {!isLogin && (
                        <>
                            <div>
                                <label className="block text-gray-300 text-sm font-medium mb-2">Role</label>
                                <select
                                    value={role}
                                    onChange={(e) => setRole(e.target.value)}
                                    className="w-full bg-gray-900 border border-gray-600 rounded-lg py-2.5 px-4 text-white focus:ring-2 focus:ring-blue-500 outline-none"
                                >
                                    <option value="user">User (View Only)</option>
                                    <option value="admin">Admin (Full Access)</option>
                                </select>
                            </div>

                            {role === 'admin' && (
                                <div className="space-y-4">
                                    <div className="flex items-center gap-2 mb-4">
                                        <input
                                            type="checkbox"
                                            id="newFacility"
                                            checked={isNewFacility}
                                            onChange={(e) => setIsNewFacility(e.target.checked)}
                                            className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 bg-gray-700 border-gray-600"
                                        />
                                        <label htmlFor="newFacility" className="text-sm text-gray-300">
                                            Register New Facility
                                        </label>
                                    </div>

                                    {!isNewFacility ? (
                                        <div>
                                            <label className="block text-gray-300 text-sm font-medium mb-2">Hospital ID</label>
                                            <div className="relative">
                                                <Building className="absolute left-3 top-3 text-gray-500" size={18} />
                                                <input
                                                    type="text"
                                                    value={hospitalId}
                                                    onChange={(e) => setHospitalId(e.target.value)}
                                                    className="w-full bg-gray-900 border border-gray-600 rounded-lg py-2.5 pl-10 pr-4 text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                                                    placeholder="Ex: H001, H002"
                                                    required={role === 'admin' && !isNewFacility}
                                                />
                                            </div>
                                            <p className="text-xs text-gray-500 mt-1">Found in your accreditation documents.</p>
                                        </div>
                                    ) : (
                                        <div className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-200">
                                            <div>
                                                <label className="block text-gray-300 text-sm font-medium mb-2">Facility Name</label>
                                                <input
                                                    type="text"
                                                    value={newHospital.name}
                                                    onChange={(e) => setNewHospital({ ...newHospital, name: e.target.value })}
                                                    className="w-full bg-gray-900 border border-gray-600 rounded-lg py-2.5 px-4 text-white focus:ring-2 focus:ring-blue-500 outline-none"
                                                    placeholder="General Hospital"
                                                    required={isNewFacility}
                                                />
                                            </div>
                                            <div className="grid grid-cols-2 gap-4">
                                                <div>
                                                    <label className="block text-gray-300 text-sm font-medium mb-2">City</label>
                                                    <input
                                                        type="text"
                                                        value={newHospital.city}
                                                        onChange={(e) => setNewHospital({ ...newHospital, city: e.target.value })}
                                                        className="w-full bg-gray-900 border border-gray-600 rounded-lg py-2.5 px-4 text-white focus:ring-2 focus:ring-blue-500 outline-none"
                                                        placeholder="City"
                                                        required={isNewFacility}
                                                    />
                                                </div>
                                                <div>
                                                    <label className="block text-gray-300 text-sm font-medium mb-2">Region</label>
                                                    <input
                                                        type="text"
                                                        value={newHospital.region}
                                                        onChange={(e) => setNewHospital({ ...newHospital, region: e.target.value })}
                                                        className="w-full bg-gray-900 border border-gray-600 rounded-lg py-2.5 px-4 text-white focus:ring-2 focus:ring-blue-500 outline-none"
                                                        placeholder="State/Prov"
                                                        required={isNewFacility}
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </>
                    )}

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-lg transition-all shadow-lg shadow-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? 'Processing...' : (isLogin ? 'Sign In' : 'Register')}
                    </button>
                </form>

                <div className="mt-6 text-center text-sm text-gray-400">
                    {isLogin ? "Don't have an account? " : "Already have an account? "}
                    <button
                        onClick={() => setIsLogin(!isLogin)}
                        className="text-blue-400 hover:text-blue-300 font-semibold"
                    >
                        {isLogin ? 'Register' : 'Login'}
                    </button>
                </div>
            </div>
        </div>
    )
}
