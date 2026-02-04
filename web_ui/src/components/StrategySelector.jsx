import React from 'react';
import { Sliders } from 'lucide-react';

const StrategySelector = ({ currentStrategy, setStrategy }) => {
    const strategies = [
        { id: 'composite', name: 'IronClad Composite', desc: 'VWAP Reversion + ML' },
        { id: 'orb', name: 'ORB (15m)', desc: 'Opening Range Breakout' },
        { id: 'supertrend', name: 'Supertrend', desc: 'Trend Following (10,3)' },
        { id: 'ma_crossover', name: 'MA Crossover', desc: 'SMA 20/50 Cross' },
    ];

    return (
        <div className="mb-6">
            <label className="text-sm text-neutral-400 font-medium mb-2 block flex items-center gap-2">
                <Sliders className="w-4 h-4" /> Active Strategy
            </label>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {strategies.map((strat) => (
                    <button
                        key={strat.id}
                        onClick={() => setStrategy(strat.id)}
                        className={`p-3 rounded-lg border text-left transition-all ${currentStrategy === strat.id
                                ? 'bg-brand-500/10 border-brand-500 text-white'
                                : 'bg-neutral-800 border-neutral-700 text-neutral-400 hover:bg-neutral-700'
                            }`}
                    >
                        <div className="font-semibold text-sm">{strat.name}</div>
                        <div className="text-xs opacity-70 truncate">{strat.desc}</div>
                    </button>
                ))}
            </div>
        </div>
    );
};

export default StrategySelector;
