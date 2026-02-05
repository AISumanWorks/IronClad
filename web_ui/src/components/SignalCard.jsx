import React, { useState } from 'react';
import { ArrowUpRight, ArrowDownRight, AlertCircle } from 'lucide-react';
import axios from 'axios';

const SignalCard = ({ signal }) => {
    const isBuy = signal.signal === 'BUY';
    const [loading, setLoading] = useState(false);
    const [status, setStatus] = useState(null); // 'success' | 'error'

    const handleTrade = async (action) => {
        setLoading(true);
        setStatus(null);
        try {
            await axios.post('/api/trade', {
                ticker: signal.ticker,
                action: action, // 'BUY' or 'SELL'
                qty: 10, // Default qty for now
                price: signal.price,
                strategy: 'manual_signal'
            });
            setStatus('success');
            setTimeout(() => setStatus(null), 3000);
        } catch (err) {
            console.error(err);
            setStatus('error');
            setTimeout(() => setStatus(null), 3000);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="p-4 bg-neutral-800 rounded-lg border border-neutral-700 hover:border-neutral-600 transition-colors">
            <div className="flex justify-between items-center mb-2">
                <span className="font-bold text-lg text-white">{signal.ticker}</span>
                <span className={`px-2 py-1 text-xs font-bold rounded border flex items-center gap-1 ${isBuy
                    ? 'bg-green-900/30 text-green-400 border-green-800'
                    : 'bg-red-900/30 text-red-400 border-red-800'
                    }`}>
                    {isBuy ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                    {signal.signal}
                </span>
            </div>

            <div className="flex justify-between text-sm text-neutral-400 mb-2">
                <span>Price: <span className="text-white">{signal.price.toFixed(2)}</span></span>
                <span>ATR: {signal.atr.toFixed(2)}</span>
            </div>

            <div className="w-full bg-neutral-700 rounded-full h-1.5 mb-3">
                <div
                    className={`h-1.5 rounded-full ${signal.confidence > 0.7 ? 'bg-brand-500' : 'bg-yellow-500'}`}
                    style={{ width: `${signal.confidence * 100}%` }}
                ></div>
            </div>

            <div className="grid grid-cols-2 gap-2 mt-2">
                <button
                    onClick={() => handleTrade('BUY')}
                    disabled={loading}
                    className="bg-green-600 hover:bg-green-700 text-white text-xs font-bold py-2 px-4 rounded transition-colors disabled:opacity-50"
                >
                    {loading ? '...' : 'BUY'}
                </button>
                <button
                    onClick={() => handleTrade('SELL')}
                    disabled={loading}
                    className="bg-red-600 hover:bg-red-700 text-white text-xs font-bold py-2 px-4 rounded transition-colors disabled:opacity-50"
                >
                    {loading ? '...' : 'SELL'}
                </button>
            </div>
            {status === 'success' && <p className="text-green-500 text-xs mt-2 text-center">Trade Executed!</p>}
            {status === 'error' && <p className="text-red-500 text-xs mt-2 text-center">Trade Failed</p>}
        </div>
    );
};

export default SignalCard;
