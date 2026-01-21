"use client"
import React from 'react'
import { AlertTriangle, MapPin, Activity } from 'lucide-react'

// Color palette matching ClusterMap
const COLOR_NAMES = ['blue', 'green', 'orange', 'yellow', 'violet', 'grey', 'black'];

interface RiskSidebarProps {
    clusters: any[]
    onSelectCluster: (lat: number, lon: number) => void
}

export default function RiskSidebar({ clusters, onSelectCluster }: RiskSidebarProps) {

    // Sort clusters by risk (for now, just size or ID)
    // Assuming backend will eventually send a 'risk_score'. 
    // For now, we simulate risk based on member count.

    const sortedClusters = [...clusters].sort((a, b) => b.members.length - a.members.length)

    return (
        <div className="w-full bg-transparent p-4 h-full overflow-y-auto flex flex-col">
            <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                <AlertTriangle className="text-red-500" />
                Active Risk Zones
            </h2>

            <div className="space-y-3 flex-1">
                {sortedClusters.length === 0 ? (
                    <p className="text-slate-500 text-center mt-10">No active clusters detected.</p>
                ) : (
                    sortedClusters.map((cluster, idx) => {
                        // Calculate center
                        const lats = cluster.members.map((m: any) => m.latitude)
                        const lons = cluster.members.map((m: any) => m.longitude)
                        const lat = lats.reduce((a: any, b: any) => a + b, 0) / lats.length
                        const lon = lons.reduce((a: any, b: any) => a + b, 0) / lons.length

                        const riskLevel = cluster.members.length > 3 ? "High" : "Moderate"
                        const riskColor = riskLevel === "High" ? "text-red-400 border-red-500/30 bg-red-500/10" : "text-orange-400 border-orange-500/30 bg-orange-500/10"

                        return (
                            <div
                                key={cluster.cluster_id}
                                onClick={() => onSelectCluster(lat, lon)}
                                className={`p-4 rounded-lg border cursor-pointer hover:bg-slate-700 transition-colors ${riskColor}`}
                            >
                                <div className="flex justify-between items-start mb-2">
                                    <span className="font-bold text-lg">Cluster {cluster.cluster_id}</span>
                                    <span className={`text-xs px-2 py-1 rounded-full uppercase font-bold border ${riskLevel === 'High' ? 'border-red-500 bg-red-500/20' : 'border-orange-500 bg-orange-500/20'}`}>
                                        {riskLevel} Risk
                                    </span>
                                </div>

                                <div className="text-sm text-slate-300 mb-2">
                                    <div className="flex items-center gap-2">
                                        <Activity size={14} />
                                        <span>{cluster.members.length} Facilities Affected</span>
                                    </div>
                                </div>

                                <div className="space-y-1">
                                    {cluster.members.slice(0, 3).map((m: any, i: number) => (
                                        <div key={i} className="flex items-center gap-2 text-xs text-slate-400">
                                            <MapPin size={12} />
                                            <span className="truncate">{m.name}</span>
                                        </div>
                                    ))}
                                    {cluster.members.length > 3 && (
                                        <div className="text-xs text-slate-500 pl-5">
                                            + {cluster.members.length - 3} more...
                                        </div>
                                    )}
                                </div>
                            </div>
                        )
                    })
                )}
            </div>

            <div className="mt-4 pt-4 border-t border-slate-700 text-xs text-slate-500 text-center">
                Data updated in real-time based on hospital admissions.
            </div>
        </div>
    )
}
