import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import { Terminal, Activity, ShieldAlert, Zap } from 'lucide-react';

const AIActivityFeed = () => {
    const [logs, setLogs] = useState([]);
    const scrollRef = useRef(null);

    useEffect(() => {
        const fetchLogs = async () => {
            try {
                const res = await axios.get('/api/logs');
                if (res.data.logs) {
                    setLogs(res.data.logs);
                }
            } catch (err) {
                console.error("Error fetching logs:", err);
            }
        };

        fetchLogs();
        const interval = setInterval(fetchLogs, 2000); // Poll every 2s
        return () => clearInterval(interval);
    }, []);

    // Auto-scroll to top (since newest is at top usually? No, terminal usually scrolls bottom.
    // Backend sends newest first (appendleft). So we render newest at top.

    const getIcon = (category) => {
        switch (category) {
            case 'TRADE': return <Zap className="w-4 h-4 text-yellow-400" />;
            case 'VETO': return <ShieldAlert className="w-4 h-4 text-red-400" />;
            case 'SCAN': return <Activity className="w-4 h-4 text-blue-400" />;
            case 'ERROR': return <span className="text-red-500 font-bold">!</span>;
            default: return <Terminal className="w-4 h-4 text-neutral-500" />;
        }
    };

    const getColor = (category) => {
        switch (category) {
            case 'TRADE': return 'text-yellow-100 bg-yellow-500/10 border-yellow-500/20';
            case 'VETO': return 'text-red-300 bg-red-500/10 border-red-500/20';
            case 'SCAN': return 'text-blue-200 bg-blue-500/5 border-blue-500/10'; // Subtle for scan
            case 'ERROR': return 'text-red-500';
            default: return 'text-neutral-300';
        }
    };

    return (
        <div className="bg-neutral-900 rounded-xl border border-neutral-800 flex flex-col h-[600px] overflow-hidden shadow-2xl">
            <div className="p-3 border-b border-neutral-800 flex justify-between items-center bg-neutral-950">
                <h2 className="text-sm font-bold text-neutral-200 flex items-center tracking-widest uppercase">
                    <Terminal className="w-4 h-4 mr-2 text-brand-500" />
                    Neural Net Logs
                </h2>
                <div className="flex items-center space-x-2">
                    <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.6)]"></div>
                    <span className="text-[10px] text-green-500/80 font-mono tracking-widest">LIVE</span>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-3 custom-scrollbar space-y-1.5 font-mono text-xs">
                {logs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-neutral-700 space-y-2">
                        <Activity className="w-8 h-8 animate-pulse opacity-20" />
                        <span className="italic">Initializing Cortex...</span>
                    </div>
                ) : (
                    logs.map((log, idx) => (
                        <div key={idx} className={`p-2 rounded border-l-2 flex items-start space-x-2 transition-all duration-300 animate-in fade-in slide-in-from-left-4 ${getColor(log.category)}`}>
                            <div className="mt-0.5 opacity-80 shrink-0">
                                {getIcon(log.category)}
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="flex justify-between items-start mb-0.5">
                                    <span className="font-bold opacity-70 text-[9px] uppercase tracking-wider bg-black/20 px-1 rounded">{log.category}</span>
                                    <span className="text-[9px] opacity-40 font-mono text-right ml-2 whitespace-nowrap">{log.time.split('T')[1]?.split('.')[0] || log.time}</span>
                                </div>
                                <p className="leading-tight break-words opacity-90">{log.message}</p>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default AIActivityFeed;
