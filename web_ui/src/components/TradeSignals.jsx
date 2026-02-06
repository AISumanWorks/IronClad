import React, { useState, useEffect } from 'react';
import { Megaphone, ArrowUp, ArrowDown, Copy, Check } from 'lucide-react';
import axios from 'axios';

const TradeSignals = () => {
    const [alerts, setAlerts] = useState([]);
    const [copied, setCopied] = useState(null);

    // Filter Logs for "TRADE" category or fetch from signals
    // Since the user wants "i buy at price... and sell msg only", we typically get this from Logs or specific Trade endpoint
    // For now, we will parse the logs for key phrases like "Buying" or "Selling" or "Squaring off"

    useEffect(() => {
        const fetchAlerts = async () => {
            try {
                const res = await axios.get('/api/logs');
                const logs = res.data.logs || [];

                // Filter for Trade Executions
                const tradeLogs = logs.filter(l =>
                    l.category === 'TRADE' ||
                    l.message.includes('Buying') ||
                    l.message.includes('Selling') ||
                    l.message.includes('Squaring off')
                ).slice(0, 5); // Show last 5

                setAlerts(tradeLogs);
            } catch (err) {
                console.error("Error fetching signals:", err);
            }
        };

        fetchAlerts();
        const interval = setInterval(fetchAlerts, 2000);
        return () => clearInterval(interval);
    }, []);

    const copyToClipboard = (text, id) => {
        navigator.clipboard.writeText(text);
        setCopied(id);
        setTimeout(() => setCopied(null), 2000);
    };

    return (
        <div className="bg-neutral-900 rounded-xl border border-neutral-800 p-4 mb-6 shadow-lg relative overflow-hidden">
            {/* Glossy Header Effect */}
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-brand-500 to-purple-600"></div>

            <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold text-white flex items-center">
                    <Megaphone className="w-5 h-5 mr-2 text-brand-400 animate-bounce-slow" />
                    Live Trade Alerts
                </h2>
                <div className="text-xs font-mono text-brand-400 bg-brand-400/10 px-2 py-1 rounded border border-brand-400/20">
                    REAL-TIME
                </div>
            </div>

            <div className="space-y-3">
                {alerts.length === 0 ? (
                    <div className="text-center py-6 text-neutral-500 text-sm italic border border-dashed border-neutral-800 rounded-lg">
                        No active trade calls yet. AI is hunting...
                    </div>
                ) : (
                    alerts.map((alert, idx) => {
                        const isBuy = alert.message.toLowerCase().includes('buy');
                        const isSell = alert.message.toLowerCase().includes('sell');
                        const isExit = alert.message.toLowerCase().includes('squaring');

                        let borderColor = 'border-neutral-700';
                        let icon = <Megaphone className="w-4 h-4" />;

                        if (isBuy) {
                            borderColor = 'border-green-500/50 bg-green-950/20';
                            icon = <ArrowUp className="w-5 h-5 text-green-400" />;
                        } else if (isSell || isExit) {
                            borderColor = 'border-red-500/50 bg-red-950/20';
                            icon = <ArrowDown className="w-5 h-5 text-red-400" />;
                        }

                        return (
                            <div key={idx} className={`relative group p-3 rounded-lg border-l-4 ${borderColor} bg-neutral-800/40 hover:bg-neutral-800/60 transition-all`}>
                                <div className="flex justify-between items-start">
                                    <div className="flex items-start space-x-3">
                                        <div className="mt-0.5 shrink-0">{icon}</div>
                                        <div>
                                            <p className="text-sm font-medium text-neutral-200 leading-snug">
                                                {alert.message.replace(/[^a-zA-Z0-9 .:()₹-]/g, "")}
                                            </p>
                                            <p className="text-[10px] text-neutral-500 mt-1 font-mono">
                                                {new Date(alert.time).toLocaleTimeString()}
                                            </p>
                                        </div>
                                    </div>

                                    <button
                                        onClick={() => copyToClipboard(alert.message, idx)}
                                        className="text-neutral-500 hover:text-white transition-colors p-1"
                                        title="Copy Signal"
                                    >
                                        {copied === idx ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                                    </button>
                                </div>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
};

export default TradeSignals;
