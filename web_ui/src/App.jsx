import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import DashboardLayout from './components/DashboardLayout';
import PriceChart from './components/PriceChart';
import StrategySelector from './components/StrategySelector';
import SignalCard from './components/SignalCard';
import Portfolio from './pages/Portfolio';
import BrainDashboard from './pages/BrainDashboard';
import { Activity, BarChart2, TrendingUp, Cpu, Server } from 'lucide-react';
import axios from 'axios';

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
  const [selectedTicker, setSelectedTicker] = useState("RELIANCE.NS");
  const [strategy, setStrategy] = useState("composite");
  const [tickers, setTickers] = useState([]);
  const [signals, setSignals] = useState([]);
  const [stats, setStats] = useState({ win_rate: 0, total_validated: 0 });
  const [serverStatus, setServerStatus] = useState("Offline");

  // Fetch Tickers, Health & Stats
  useEffect(() => {
    // Relative paths for production
    axios.get('/api/tickers')
      .then(res => setTickers(res.data.tickers))
      .catch(err => console.error(err));

    axios.get('/api/stats')
      .then(res => setStats(res.data))
      .catch(err => console.error(err));

    const checkHealth = () => {
      // Use specific health endpoint, not root (root serves React)
      axios.get('/api/health')
        .then(() => setServerStatus("Online"))
        .catch(() => setServerStatus("Offline"));
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  // Poll Signals & Stats
  useEffect(() => {
    const fetchSignals = () => {
      axios.get(`/api/signals?strategy=${strategy}`)
        .then(res => setSignals(res.data.signals))
        .catch(err => console.error(err));

      // Refresh stats occasionally
      axios.get('/api/stats')
        .then(res => setStats(res.data))
        .catch(err => console.error(err));
    };

    fetchSignals();
    const interval = setInterval(fetchSignals, 60000); // Every minute
    return () => clearInterval(interval);
  }, [strategy]);

  return (
    <DashboardLayout>
      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          title="System Status"
          value={serverStatus}
          icon={<Server />}
          color={serverStatus === 'Online' ? "text-green-500" : "text-red-500"}
        />
        <StatCard title="Active Strategy" value={strategy.toUpperCase()} icon={<Activity />} color="text-blue-500" />
        <StatCard
          title="AI Win Rate"
          value={`${stats.win_rate}% (${stats.total_validated})`}
          icon={<TrendingUp />}
          color={stats.win_rate > 50 ? "text-green-400" : "text-yellow-400"}
        />
        <StatCard title="Active Signals" value={signals.length} icon={<Cpu />} color="text-purple-500" />
      </div>

      <StrategySelector currentStrategy={strategy} setStrategy={setStrategy} />

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-8">
          <div className="bg-neutral-900 rounded-xl border border-neutral-800 p-6 h-[600px] flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-neutral-200">
                {selectedTicker} <span className="text-neutral-500 text-sm font-normal">Live Chart</span>
              </h2>
              <select
                className="bg-neutral-800 border border-neutral-700 text-white text-sm rounded-lg p-2 focus:ring-brand-500 focus:border-brand-500"
                value={selectedTicker}
                onChange={(e) => setSelectedTicker(e.target.value)}
              >
                {tickers.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>

            <div className="flex-1 w-full relative">
              <PriceChart ticker={selectedTicker} strategy={strategy} />
            </div>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4">
          <div className="bg-neutral-900 rounded-xl border border-neutral-800 p-6 h-[600px] flex flex-col">
            <h2 className="text-xl font-semibold mb-4 text-neutral-200">Market Scanner</h2>

            <div className="flex-1 overflow-y-auto space-y-4 pr-2 custom-scrollbar">
              {signals.length === 0 ? (
                <div className="text-center text-neutral-500 mt-10">
                  <Activity className="w-10 h-10 mx-auto mb-2 opacity-20" />
                  <p>No active signals found.</p>
                  <p className="text-xs mt-1">Scanning market for opportunities...</p>
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
