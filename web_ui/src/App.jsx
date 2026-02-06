import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import DashboardLayout from './components/DashboardLayout';
import PriceChart from './components/PriceChart';
import StrategySelector from './components/StrategySelector';
import SignalCard from './components/SignalCard';
import AIActivityFeed from './components/AIActivityFeed';
import Portfolio from './pages/Portfolio';
import BrainDashboard from './pages/BrainDashboard';
import { Activity, BarChart2, TrendingUp, Cpu, Server } from 'lucide-react';
import axios from 'axios';
import TradeSignals from './components/TradeSignals';

// Stats Component
function StatCard({ title, value, icon, color }) {
  return (
    <div className="bg-neutral-900 p-6 rounded-xl border border-neutral-800 flex items-center shadow-sm">
      <div className={`p-3 rounded-lg bg-neutral-800 ${color} mr-4`}>
        {icon}
      </div>
      <div>
        <p className="text-neutral-500 text-sm font-medium">{title}</p>
        <h3 className="text-2xl font-bold text-white">{value}</h3>
      </div>
    </div>
  )
}

// Dashboard Page Component
function Dashboard() {
  const [serverStatus, setServerStatus] = useState('Offline');
  const [strategy, setStrategy] = useState('composite');
  const [stats, setStats] = useState({ win_rate: 0, total_validated: 0 });
  const [signals, setSignals] = useState([]);
  const [tickers, setTickers] = useState(['RELIANCE.NS']); // Default
  const [selectedTicker, setSelectedTicker] = useState('RELIANCE.NS');

  // Fetch Function
  const fetchData = async () => {
    try {
      const health = await axios.get('/api/health'); // Check Health
      setServerStatus(health.data.status === 'online' ? 'Online' : 'Offline');

      const statsRes = await axios.get('/api/stats');
      setStats(statsRes.data);

      const sigRes = await axios.get(`/api/signals?strategy=${strategy}`);
      setSignals(sigRes.data.signals || []);
    } catch (e) {
      setServerStatus('Offline');
    }
  };

  // Fetch Tickers once
  useEffect(() => {
    const fetchTickers = async () => {
      try {
        const res = await axios.get('/api/tickers');
        setTickers(res.data.tickers);
      } catch (e) { console.error(e); }
    };
    fetchTickers();
  }, []);

  // Poll Data
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [strategy]);

  return (
    <DashboardLayout>
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">

        {/* LEFT COLUMN: Controls & Feed */}
        <div className="lg:col-span-1 space-y-6">
          <TradeSignals /> {/* New Trade Alerts */}

          <AIActivityFeed />

          {/* Strategy Selector */}
          <div className="bg-neutral-900 p-4 rounded-xl border border-neutral-800">
            <h3 className="text-sm font-semibold text-neutral-400 mb-3 uppercase tracking-wider">Strategy Engine</h3>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="w-full bg-neutral-950 border border-neutral-800 text-white p-2 rounded-lg focus:ring-2 focus:ring-brand-500 outline-none"
            >
              <option value="composite">Composite (Safe)</option>
              <option value="orb">ORB (Breakout)</option>
              <option value="supertrend">Supertrend (Trend)</option>
              <option value="rsi_14">RSI Reversion</option>
            </select>
          </div>

          {/* Stats Card */}
          <div className="bg-neutral-900 p-4 rounded-xl border border-neutral-800">
            <h3 className="text-sm font-semibold text-neutral-400 mb-2 uppercase tracking-wider">AI Accuracy</h3>
            <div className="flex justify-between items-end">
              <span className="text-3xl font-bold text-white">{stats.win_rate}%</span>
              <span className="text-xs text-neutral-500 mb-1">{stats.total_validated} Trades Verified</span>
            </div>
            <div className="w-full bg-neutral-800 h-1.5 mt-2 rounded-full overflow-hidden">
              <div className="bg-brand-500 h-full transition-all duration-1000" style={{ width: `${stats.win_rate}%` }}></div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Chart & Scanner */}
        <div className="lg:col-span-3 space-y-6">
          {/* Ticker Selector */}
          <div className="flex space-x-2 overflow-x-auto pb-2 custom-scrollbar">
            {tickers.map(t => (
              <button
                key={t}
                onClick={() => setSelectedTicker(t)}
                className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${selectedTicker === t ? 'bg-brand-600 text-white' : 'bg-neutral-900 text-neutral-400 hover:bg-neutral-800'}`}
              >
                {t}
              </button>
            ))}
          </div>

          <div className="bg-neutral-900 rounded-xl border border-neutral-800 p-4 h-[500px] shadow-lg">
            <PriceChart ticker={selectedTicker} strategy={strategy} />
          </div>

          {/* Active Signals List */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {signals.length === 0 ? (
              <div className="col-span-3 text-center text-neutral-500 py-10 border border-dashed border-neutral-800 rounded-xl">
                <Activity className="w-8 h-8 mx-auto mb-2 opacity-20" />
                No active signals. AI is scanning...
              </div>
            ) : (
              signals.map((sig, idx) => (
                <div key={idx} onClick={() => setSelectedTicker(sig.ticker)} className="cursor-pointer">
                  <SignalCard signal={sig} />
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

// Main App Router
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/portfolio" element={<Portfolio />} />
        <Route path="/brain" element={<BrainDashboard />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
