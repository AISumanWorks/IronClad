import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Layers, Settings, Bell } from 'lucide-react';

const DashboardLayout = ({ children }) => {
    const location = useLocation();

    const isActive = (path) => location.pathname === path;

    return (
        <div className="min-h-screen bg-neutral-950 text-white font-sans selection:bg-brand-500/30">
            {/* Navbar */}
            <header className="fixed top-0 w-full z-50 bg-neutral-950/80 backdrop-blur-md border-b border-neutral-800">
                <div className="container mx-auto px-6 h-16 flex items-center justify-between">
                    <Link to="/" className="flex items-center space-x-3">
                        <div className="w-8 h-8 bg-brand-500 rounded-lg flex items-center justify-center">
                            <Layers className="text-white w-5 h-5" />
                        </div>
                        <span className="text-xl font-bold tracking-tight">IronClad <span className="text-neutral-500 font-normal">Terminal</span></span>
                    </Link>

                    <nav className="hidden md:flex items-center space-x-8">
                        <Link to="/" className={`text-sm font-medium transition-colors ${isActive('/') ? 'text-white' : 'text-neutral-400 hover:text-white'}`}>Dashboard</Link>
                        <Link to="/portfolio" className={`text-sm font-medium transition-colors ${isActive('/portfolio') ? 'text-white' : 'text-neutral-400 hover:text-white'}`}>Portfolio</Link>
                    </nav>

                    <div className="flex items-center space-x-4">
                        <button className="p-2 hover:bg-neutral-800 rounded-full transition-colors relative">
                            <Bell className="w-5 h-5 text-neutral-400" />
                            <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full"></span>
                        </button>
                        <button className="p-2 hover:bg-neutral-800 rounded-full transition-colors">
                            <Settings className="w-5 h-5 text-neutral-400" />
                        </button>
                        <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-brand-500 to-purple-500"></div>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="pt-24 pb-12 container mx-auto px-6">
                {children}
            </main>
        </div>
    );
};

export default DashboardLayout;
