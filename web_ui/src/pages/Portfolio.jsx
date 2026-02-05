import React, { useEffect, useState } from 'react';
import DashboardLayout from '../components/DashboardLayout';
import { PieChart, Wallet, TrendingUp, History } from 'lucide-react';
import axios from 'axios';

const Portfolio = () => {
    const [account, setAccount] = useState({ balance: 0, equity: 0, positions_count: 0 });
    const [positions, setPositions] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const accRes = await axios.get('/account');
                const portRes = await axios.get('/portfolio');
                setAccount(accRes.data);
                setPositions(portRes.data.positions);
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
                        <h3 className="text-2xl font-bold text-white">₹{account.balance.toLocaleString()}</h3>
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
            <div className="bg-neutral-900 rounded-xl border border-neutral-800 overflow-hidden">
                <div className="p-6 border-b border-neutral-800 flex justify-between items-center">
                    <h2 className="text-xl font-semibold text-white">Current Holdings</h2>
                    <span className="text-sm text-neutral-500">Real-time Data</span>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead className="bg-neutral-950 text-neutral-400 uppercase text-xs">
                            <tr>
                                <th className="px-6 py-4">Ticker</th>
                                <th className="px-6 py-4">Quantity</th>
                                <th className="px-6 py-4">Avg Price</th>
                                <th className="px-6 py-4">Total Value</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-neutral-800">
                            {positions.length === 0 ? (
                                <tr>
                                    <td colSpan="4" className="px-6 py-8 text-center text-neutral-500">
                                        No active positions. Go to Dashboard to trade.
                                    </td>
                                </tr>
                            ) : (
                                positions.map((pos) => (
                                    <tr key={pos.ticker} className="hover:bg-neutral-800/50 transition-colors">
                                        <td className="px-6 py-4 font-semibold text-white">{pos.ticker}</td>
                                        <td className="px-6 py-4 text-neutral-300">{pos.qty}</td>
                                        <td className="px-6 py-4 text-neutral-300">₹{pos.avg_price.toFixed(2)}</td>
                                        <td className="px-6 py-4 text-brand-400 font-medium">
                                            ₹{(pos.qty * pos.avg_price).toFixed(2)}
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default Portfolio;
