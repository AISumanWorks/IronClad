import React, { useEffect, useState } from 'react';
import axios from 'axios';
import DashboardLayout from '../components/DashboardLayout';
import { Brain, TrendingUp, TrendingDown, Activity, Zap } from 'lucide-react';

const BrainDashboard = () => {
    const [strategies, setStrategies] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const res = await axios.get('/api/brain');
                setStrategies(res.data.strategies || []);
                setLoading(false);
            } catch (err) {
                console.error("Error fetching brain stats:", err);
                setLoading(false);
            }
        };

        fetchStats();
        const interval = setInterval(fetchStats, 5000);
        return () => clearInterval(interval);
    }, []);

    return (
        <DashboardLayout>
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white mb-2 flex items-center">
                    <Brain className="w-8 h-8 mr-3 text-brand-500" />
                    The Advanced Brain
                </h1>
                <p className="text-neutral-400">
                    Self-learning engine monitoring strategy performance.
                    Strategies with higher "Trust Score" get priority allocation.
                </p>
            </div>

            {loading ? (
                <div className="text-white">Loading Neural Network...</div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {strategies.length === 0 && (
                        <div className="col-span-full bg-neutral-900/50 border border-neutral-800 rounded-xl p-8 text-center text-neutral-500">
                            No strategy data collected yet. The Brain is waiting for trade outcomes.
                        </div>
                    )}

                    {strategies.map((strat) => (
                        <div key={strat.strategy} className="bg-neutral-900 border border-neutral-800 rounded-xl p-6 relative overflow-hidden group hover:border-brand-500/50 transition-colors">
                            <div className="absolute top-0 right-0 w-32 h-32 bg-brand-500/5 rounded-full blur-3xl -mr-16 -mt-16 transition-all group-hover:bg-brand-500/10"></div>

                            <div className="flex justify-between items-start mb-4">
                                <div>
                                    <h3 className="text-lg font-bold text-white capitalize">{strat.strategy.replace('_', ' ')}</h3>
                                    <span className="text-xs text-neutral-500 uppercase tracking-wider">Strategy Engine</span>
                                </div>
                                <div className={`px-3 py-1 rounded-full text-xs font-bold ${strat.trust_score >= 0.7 ? 'bg-green-500/20 text-green-500' :
                                        strat.trust_score < 0.4 ? 'bg-red-500/20 text-red-500' : 'bg-yellow-500/20 text-yellow-500'
                                    }`}>
                                    Trust: {Math.round(strat.trust_score * 100)}%
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4 mb-4">
                                <div className="bg-neutral-950/50 p-3 rounded-lg">
                                    <div className="text-xs text-neutral-500 mb-1">Win Rate</div>
                                    <div className="text-xl font-mono font-semibold text-white">
                                        {strat.win_rate ? strat.win_rate.toFixed(1) : 0}%
                                    </div>
                                </div>
                                <div className="bg-neutral-950/50 p-3 rounded-lg">
                                    <div className="text-xs text-neutral-500 mb-1">Avg PnL</div>
                                    <div className={`text-xl font-mono font-semibold ${strat.avg_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        {strat.avg_pnl ? (strat.avg_pnl * 100).toFixed(2) : 0.00}%
                                    </div>
                                </div>
                            </div>

                            <div className="space-y-2">
                                <div className="flex justify-between text-xs">
                                    <span className="text-neutral-400">Total Trades</span>
                                    <span className="text-white">{strat.total_trades}</span>
                                </div>
                                <div className="w-full bg-neutral-800 h-1.5 rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-green-500"
                                        style={{ width: `${strat.win_rate}%` }}
                                    ></div>
                                </div>
                                <div className="flex justify-between text-[10px] text-neutral-500 mt-1">
                                    <span>{strat.wins} Wins</span>
                                    <span>{strat.losses} Losses</span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </DashboardLayout>
    );
};

export default BrainDashboard;
