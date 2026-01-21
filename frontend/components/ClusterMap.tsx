"use client"

import { MapContainer, TileLayer, Marker, Popup, Polyline, Polygon, Tooltip, CircleMarker } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import React, { useMemo, useState } from 'react'
import { getConvexHull } from '../utils/convexHull'

// Fix for default marker icon in Leaflet + Next.js
const icon = new L.Icon({
    iconUrl: "https://unpkg.com/leaflet@1.9.3/dist/images/marker-icon.png",
    shadowUrl: "https://unpkg.com/leaflet@1.9.3/dist/images/marker-shadow.png",
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});

// Color palette for clusters
const COLOR_NAMES = ['blue', 'green', 'orange', 'yellow', 'violet', 'grey', 'black'];
const HEX_COLORS = ['#2A81CB', '#2AAD27', '#CB8427', '#CAC428', '#9C2BCB', '#7B7B7B', '#3D3D3D'];

// Helper to calculate bearing between two points
const calculateBearing = (startLat: number, startLng: number, destLat: number, destLng: number) => {
    const startLatRad = startLat * (Math.PI / 180);
    const startLngRad = startLng * (Math.PI / 180);
    const destLatRad = destLat * (Math.PI / 180);
    const destLngRad = destLng * (Math.PI / 180);

    const y = Math.sin(destLngRad - startLngRad) * Math.cos(destLatRad);
    const x = Math.cos(startLatRad) * Math.sin(destLatRad) -
        Math.sin(startLatRad) * Math.cos(destLatRad) * Math.cos(destLngRad - startLngRad);

    const brng = Math.atan2(y, x);
    let deg = brng * (180 / Math.PI);
    return (deg + 360) % 360;
}

// Arrow Icon Generator
const createArrowIcon = (rotation: number, color: string = 'red') => {
    return L.divIcon({
        className: 'custom-arrow-icon',
        html: `<div style="transform: rotate(${rotation}deg); width: 24px; height: 24px; display: flex; align-items: center; justify-content: center;">
                 <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                   <path d="M12 2L12 19" stroke="${color}" stroke-width="3" stroke-linecap="round"/>
                   <path d="M12 19L5 12" stroke="${color}" stroke-width="3" stroke-linecap="round"/>
                   <path d="M12 19L19 12" stroke="${color}" stroke-width="3" stroke-linecap="round"/>
                 </svg>
               </div>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12]
    });
}
// Note: The SVG path above is an arrow pointing DOWN (towards 19). 
// Since 0 degrees usually means North (Up), we might need to adjust.
// If bearing 0 is North, and our arrow points South (down), we need to rotate it 180 deg?
// Actually simpler: Let's draw an arrow pointing UP (North) in the SVG.
// <path d="M12 22L12 5" ... /> <path d="M5 12L12 5L19 12" ... />
// Let's rewrite the createArrowIcon to be an UP arrow so rotation works naturally.

const createUpArrowIcon = (rotation: number, color: string = 'red') => {
    return L.divIcon({
        className: 'custom-arrow-icon',
        html: `<div style="transform: rotate(${rotation}deg); width: 24px; height: 24px;">
                 <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                   <line x1="12" y1="19" x2="12" y2="5"></line>
                   <polyline points="5 12 12 5 19 12"></polyline>
                 </svg>
               </div>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12]
    });
}




export default function ClusterMap({ clusters, network, hospitals, dailyData }: { clusters: any[], network: any[], hospitals?: any[], dailyData?: any[] }) {

    // State for Community Reports
    const [reports, setReports] = useState<any[]>([])
    const [showReports, setShowReports] = useState(false)

    React.useEffect(() => {
        // Fetch Reports
        fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/public/reports`)
            .then(res => res.json())
            .then(data => setReports(data))
            .catch(e => console.error("Report fetch error", e))
    }, [])

    // Helper to get marker color
    const getIcon = (colorName: string, isCritical: boolean = false) => {
        if (isCritical) {
            return L.divIcon({
                className: 'custom-pulsing-icon',
                html: `<div style="position: relative; width: 24px; height: 24px;">
                         <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background-color: #ef4444; border-radius: 9999px; border: 2px solid white; z-index: 10;"></div>
                         <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background-color: #ef4444; border-radius: 9999px; opacity: 0.75; animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
                       </div>`,
                iconSize: [24, 24],
                iconAnchor: [12, 12]
            })
        }
        return new L.Icon({
            iconUrl: `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-${colorName}.png`,
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        })
    }

    // Compute Hulls
    const clusterHulls = useMemo(() => {
        if (!clusters || clusters.length === 0) return []

        return clusters.map((cluster, idx) => {
            const points = cluster.members.map((h: any) => ({ latitude: h.latitude, longitude: h.longitude }))
            const hull = getConvexHull(points) // [lat, lon][]
            return {
                clusterId: cluster.cluster_id,
                positions: hull,
                color: HEX_COLORS[idx % HEX_COLORS.length]
            }
        })
    }, [clusters])

    // Compute Centers for Network Lines
    const clusterCenters = useMemo(() => {
        const centers: { [key: number]: [number, number] } = {}
        if (!clusters) return centers
        clusters.forEach(c => {
            const lats = c.members.map((m: any) => m.latitude)
            const lons = c.members.map((m: any) => m.longitude)
            centers[c.cluster_id] = [
                lats.reduce((a: any, b: any) => a + b, 0) / lats.length,
                lons.reduce((a: any, b: any) => a + b, 0) / lons.length
            ]
        })
        return centers
    }, [clusters])

    // Fallback: If no clusters, show raw list of hospitals in grey
    const featuresToRender = (clusters && clusters.length > 0)
        ? clusters.flatMap((cluster, idx) =>
            cluster.members.map((h: any) => ({ ...h, clusterColor: COLOR_NAMES[idx % COLOR_NAMES.length], clusterId: cluster.cluster_id }))
        )
        : (hospitals || []).map((h: any) => ({ ...h, clusterColor: 'grey', clusterId: 'Unassigned' }));

    // Merge live hospital data if available to get usage key
    // The 'clusters' members might be subsets without usage data if the Miner didn't pass it through.
    // We should rely on 'hospitals' prop for the full data and join it with cluster info.
    const mergedFeatures = featuresToRender.map(f => {
        const fullData = hospitals?.find(h => h.hospital_id === f.hospital_id);

        let markerColor = f.clusterColor; // Default to cluster color
        let stressLevel = "Normal";

        if (fullData && fullData.usage) {
            const icuUtil = fullData.usage.icu_utilization;
            if (icuUtil > 80) {
                markerColor = 'red';
                stressLevel = "CRITICAL";
            } else if (icuUtil > 50) {
                markerColor = 'orange';
                stressLevel = "Warning";
            } else {
                markerColor = 'green';
            }
        }

        return { ...f, ...fullData, markerColor, stressLevel };
    });

    return (
        <MapContainer center={[45.0, -79.0]} zoom={6} scrollWheelZoom={true} style={{ height: "100%", width: "100%" }}>
            <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {/* Time-Lapse Data Layer (Bubbles) - Keep as is */}
            {dailyData && dailyData.map((d: any, i: number) => (
                <CircleMarker
                    key={`bubble-${i}`}
                    center={[d.lat, d.lon]}
                    radius={Math.sqrt(d.count) * 8}
                    pathOptions={{ color: 'red', fillColor: '#f03', fillOpacity: 0.5, weight: 1 }}
                >
                    <Tooltip direction="top" offset={[0, -10]} opacity={1}>
                        <div className="text-center font-bold text-red-600">
                            {d.count} New Cases
                        </div>
                    </Tooltip>
                </CircleMarker>
            ))}

            {/* Render Cluster Zones (Hulls) */}
            {clusterHulls.map((hull) => (
                <Polygon
                    key={`hull-${hull.clusterId}`}
                    positions={hull.positions as [number, number][]}
                    pathOptions={{ color: hull.color, fillOpacity: 0.15, weight: 2, dashArray: '5, 5' }}
                >
                    <Tooltip sticky direction="center" className="bg-transparent border-none text-white font-bold shadow-none">
                        Cluster {hull.clusterId}
                    </Tooltip>
                </Polygon>
            ))}

            {/* Render Spread Network (Edges) */}
            {network.map((edge, idx) => {
                const start = clusterCenters[edge.source]
                const end = clusterCenters[edge.target]
                if (!start || !end) return null

                return (
                    <React.Fragment key={`edge-${idx}`}>
                        <Polyline
                            positions={[start, end]}
                            pathOptions={{ color: 'red', weight: 1 + (edge.strength * 3), dashArray: '5, 10', opacity: 0.6 }}
                        >
                            <Tooltip sticky>
                                <div className="text-center text-slate-800">
                                    <strong>Likely Spread</strong><br />
                                    Lag: {edge.lag} Days<br />
                                    Strength: {(edge.strength * 100).toFixed(0)}%
                                </div>
                            </Tooltip>
                        </Polyline>
                    </React.Fragment>
                )
            })}

            {mergedFeatures.map((hospital, idx) => (
                <Marker
                    key={hospital.hospital_id || idx}
                    position={[hospital.latitude, hospital.longitude]}
                    icon={getIcon(hospital.markerColor, hospital.stressLevel === 'CRITICAL')}
                >
                    <Popup>
                        <div className="text-slate-800 min-w-[200px]">
                            <b className="text-lg">{hospital.name}</b>
                            <span className={`float-right text-xs font-bold px-2 py-1 rounded-full text-white ${hospital.stressLevel === 'CRITICAL' ? 'bg-red-500' : hospital.stressLevel === 'Warning' ? 'bg-orange-500' : 'bg-green-500'}`}>
                                {hospital.stressLevel}
                            </span>
                            <hr className="my-2 border-slate-300" />

                            <div className="grid grid-cols-2 gap-2 text-sm mb-2">
                                <div>
                                    <span className="font-semibold text-slate-500 block text-xs">Cluster</span>
                                    {hospital.clusterId !== 'Unassigned' ? `Zone ${hospital.clusterId}` : 'N/A'}
                                </div>
                                <div className="text-right">
                                    <span className="font-semibold text-slate-500 block text-xs">Region</span>
                                    {hospital.region}
                                </div>
                            </div>

                            {hospital.usage ? (
                                <div className="bg-slate-100 p-2 rounded-lg space-y-2">
                                    <div>
                                        <div className="flex justify-between text-xs font-bold text-slate-600 mb-1">
                                            <span>ICU Beds</span>
                                            <span className={hospital.usage.icu_utilization > 80 ? 'text-red-600' : ''}>
                                                {hospital.usage.icu_used}/{hospital.icu_beds} ({hospital.usage.icu_utilization}%)
                                            </span>
                                        </div>
                                        <div className="w-full bg-slate-300 rounded-full h-1.5 overflow-hidden">
                                            <div
                                                className={`h-full rounded-full ${hospital.usage.icu_utilization > 80 ? 'bg-red-500' : 'bg-blue-500'}`}
                                                style={{ width: `${Math.min(100, hospital.usage.icu_utilization)}%` }}
                                            />
                                        </div>
                                    </div>
                                    <div>
                                        <div className="flex justify-between text-xs font-bold text-slate-600 mb-1">
                                            <span>Live Admissions</span>
                                            <span>{hospital.usage.beds_used}/{hospital.total_beds} ({hospital.usage.bed_utilization}%)</span>
                                        </div>
                                        <div className="w-full bg-slate-300 rounded-full h-1.5 overflow-hidden">
                                            <div
                                                className="h-full rounded-full bg-cyan-500"
                                                style={{ width: `${Math.min(100, hospital.usage.bed_utilization)}%` }}
                                            />
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                <p className="text-xs text-slate-500 italic mt-2">No live capacity data.</p>
                            )}
                        </div>
                    </Popup>
                </Marker>
            ))}

            {/* Community Reports Layer */}
            {showReports && reports.map((rep, i) => (
                <CircleMarker
                    key={`rep-${i}`}
                    center={[rep.latitude, rep.longitude]}
                    radius={5}
                    pathOptions={{ color: '#a855f7', fillColor: '#d8b4fe', fillOpacity: 0.9, weight: 2 }}
                >
                    <Popup>
                        <div className="text-slate-800">
                            <h4 className="font-bold text-xs uppercase text-purple-600 mb-1">Community Report</h4>
                            <p className="text-sm font-semibold">{rep.symptoms}</p>
                            <div className="mt-2 flex items-center gap-1">
                                <span className="text-[10px] uppercase font-bold text-slate-500">Trust Score</span>
                                <span className={`text-xs font-mono font-bold ${rep.trust_score > 0.8 ? 'text-green-600' : 'text-orange-500'}`}>{rep.trust_score}</span>
                            </div>
                        </div>
                    </Popup>
                </CircleMarker>
            ))}

            <div className="leaflet-bottom leaflet-left" style={{ bottom: '20px', left: '20px', pointerEvents: 'auto', zIndex: 1000 }}>
                <div onClick={() => setShowReports(!showReports)} className={`cursor-pointer px-4 py-2 rounded-lg font-bold text-sm shadow-xl transition-all flex items-center gap-2 border ${showReports ? 'bg-purple-600 text-white border-purple-400' : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-50'}`}>
                    <span className="text-lg">📢</span>
                    {showReports ? 'Hide Community Reports' : 'Show Community Reports'}
                </div>
            </div>

        </MapContainer>
    )
}
