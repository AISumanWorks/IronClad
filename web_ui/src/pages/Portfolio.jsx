import React, { useEffect, useState } from 'react';
import DashboardLayout from '../components/DashboardLayout';
import { PieChart, Wallet, TrendingUp, History } from 'lucide-react';
import axios from 'axios';

const Portfolio = () => {
    const [account, setAccount] = useState({ cash: 0, equity: 0, positions_count: 0 });
    const [positions, setPositions] = useState([]);
    const [history, setHistory] = useState([]); // New History State
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const accRes = await axios.get('/api/account');
                const portRes = await axios.get('/api/portfolio');
                const histRes = await axios.get('/api/history'); // Fetch History

                setAccount(accRes.data);
                setPositions(portRes.data.positions || []);
                setHistory(histRes.data.trades || []);
                setLoading(false);
            } catch (err) {
                console.error("Error fetching portfolio:", err);
                setLoading(false);
            }
        };
        fetchData();
        const interval = setInterval(fetchData, 5000); // Live update
        return () => clearInterval(interval);
    }, []);

    return (
        <DashboardLayout>
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white mb-2">Paper Trading Portfolio</h1>
                <p className="text-neutral-400">Track your virtual performance and holdings.</p>
            </div>

            {/* Account Summary */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div className="bg-neutral-900 p-6 rounded-xl border border-neutral-800 flex items-center">
                    <div className="p-4 bg-brand-500/20 text-brand-500 rounded-lg mr-4">
                        <Wallet className="w-8 h-8" />
                    </div>
                    <div>
                        <p className="text-neutral-500 text-sm font-medium">Available Cash</p>
                        <h3 className="text-2xl font-bold text-white">₹{(account.cash || 0).toLocaleString()}</h3>
                    </div>
                </div>

                <div className="bg-neutral-900 p-6 rounded-xl border border-neutral-800 flex items-center">
                    <div className="p-4 bg-purple-500/20 text-purple-500 rounded-lg mr-4">
                        <TrendingUp className="w-8 h-8" />
                    </div>
                    <div>
                        <p className="text-neutral-500 text-sm font-medium">Total Equity</p>
                        <h3 className="text-2xl font-bold text-white">₹{account.equity.toLocaleString()}</h3>
                    </div>
                </div>

                <div className="bg-neutral-900 p-6 rounded-xl border border-neutral-800 flex items-center">
                    <div className="p-4 bg-green-500/20 text-green-500 rounded-lg mr-4">
                        <PieChart className="w-8 h-8" />
                    </div>
                    <div>
                        <p className="text-neutral-500 text-sm font-medium">Open Positions</p>
                        <h3 className="text-2xl font-bold text-white">{account.positions_count}</h3>
                    </div>
                </div>
            </div>

            {/* Holdings Table */}
            <div className="bg-neutral-900 rounded-xl border border-neutral-800 overflow-hidden mb-8">
                <div className="p-6 border-b border-neutral-800 flex justify-between items-center bg-neutral-950/30">
                    <div>
                        <h2 className="text-xl font-semibold text-white">Live Positions</h2>
                        <p className="text-xs text-neutral-500 mt-1">
                            <span className="text-brand-400 font-bold">INTRADAY MODE:</span> Auto-square off at 3:15 PM
                        </p>
                    </div>
                    <span className="text-sm text-neutral-500 flex items-center">
                        <span className="w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse"></span>
                        Real-time Updates
                    </span>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-left whitespace-nowrap">
                        <thead className="bg-neutral-950 text-neutral-400 uppercase text-xs font-semibold tracking-wider">
                            <tr>
                                <th className="px-6 py-4">Ticker</th>
                                <th className="px-6 py-4">Qty</th>
                                <th className="px-6 py-4">Avg Price</th>
                                <th className="px-6 py-4">LTP</th>
                                <th className="px-6 py-4">Current Value</th>
                                <th className="px-6 py-4">P&L</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-neutral-800 font-mono text-sm">
                            {positions.length === 0 ? (
                                <tr>
                                    <td colSpan="6" className="px-6 py-12 text-center text-neutral-500 italic">
                                        No active positions. AI is scanning for entries...
                                    </td>
                                </tr>
                            ) : (
                                positions.map((pos) => {
                                    const pnl = pos.pnl || 0;
                                    const isProfit = pnl >= 0;
                                    return (
                                        <tr key={pos.ticker} className="hover:bg-neutral-800/30 transition-colors">
                                            <td className="px-6 py-4 font-bold text-white">{pos.ticker}</td>
                                            <td className="px-6 py-4 text-neutral-300">{pos.qty}</td>
                                            <td className="px-6 py-4 text-neutral-400">₹{pos.avg_price.toFixed(2)}</td>
                                            <td className="px-6 py-4 text-white font-medium">₹{(pos.current_price || pos.avg_price).toFixed(2)}</td>
                                            <td className="px-6 py-4 text-neutral-300">
                                                ₹{((pos.current_price || pos.avg_price) * pos.qty).toFixed(2)}
                                            </td>
                                            <td className={`px-6 py-4 font-bold ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                                                {isProfit ? '+' : ''}₹{pnl.toFixed(2)}
                                                <span className="text-xs font-normal ml-1 opacity-75">
                                                    ({pos.pnl_percent ? pos.pnl_percent.toFixed(2) : '0.00'}%)
                                                </span>
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Trade History Table */}
            <div className="bg-neutral-900 rounded-xl border border-neutral-800 overflow-hidden">
                <div className="p-6 border-b border-neutral-800 flex justify-between items-center bg-neutral-950/30">
                    <h2 className="text-xl font-semibold text-white flex items-center">
                        <History className="w-5 h-5 mr-2 text-neutral-400" />
                        Trade History
                    </h2>
                </div>
                <div className="overflow-x-auto max-h-[400px]">
                    <table className="w-full text-left whitespace-nowrap">
                        <thead className="bg-neutral-950 text-neutral-400 uppercase text-xs font-semibold tracking-wider sticky top-0 z-10">
                            <tr>
                                <th className="px-6 py-4">Time</th>
                                <th className="px-6 py-4">Ticker</th>
                                <th className="px-6 py-4">Action</th>
                                <th className="px-6 py-4">Qty</th>
                                <th className="px-6 py-4">Price</th>
                                <th className="px-6 py-4">Realized P&L</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-neutral-800 font-mono text-sm">
                            {history.length === 0 ? (
                                <tr>
                                    <td colSpan="6" className="px-6 py-8 text-center text-neutral-500 italic">
                                        No trade history yet.
                                    </td>
                                </tr>
                            ) : (
                                history.map((trade, idx) => {
                                    const isBuy = trade.side === "BUY";
                                    const pnl = trade.pnl || 0;
                                    return (
                                        <tr key={idx} className="hover:bg-neutral-800/30 transition-colors">
                                            <td className="px-6 py-4 text-neutral-500 text-xs">
                                                {new Date(trade.timestamp).toLocaleString()}
                                            </td>
                                            <td className="px-6 py-4 font-bold text-white">{trade.ticker}</td>
                                            <td className={`px-6 py-4 font-bold ${isBuy ? 'text-green-400' : 'text-red-400'}`}>
                                                {trade.side}
                                            </td>
                                            <td className="px-6 py-4 text-neutral-300">{trade.qty}</td>
                                            <td className="px-6 py-4 text-neutral-300">₹{trade.price.toFixed(2)}</td>
                                            <td className={`px-6 py-4 font-bold ${pnl > 0 ? 'text-green-500' : pnl < 0 ? 'text-red-500' : 'text-neutral-500'}`}>
                                                {trade.side === "SELL" ? (
                                                    <span>{pnl > 0 ? '+' : ''}₹{pnl.toFixed(2)}</span>
                                                ) : (
                                                    <span className="opacity-20">-</span>
                                                )}
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default Portfolio;

