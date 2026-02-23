import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { BarChart3, History, Download, Activity, ChevronRight, Menu } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '../common/SpotlightCard';

const navItems = [
    { path: '/', label: 'Terminal', icon: BarChart3 },
    { path: '/analysis', label: 'Market Data', icon: Activity },
    { path: '/history', label: 'History Logs', icon: History },
    { path: '/export', label: 'Extraction', icon: Download },
];

export function Sidebar() {
    const location = useLocation();
    const [isExpanded, setIsExpanded] = useState(true);

    return (
        <motion.div
            initial={false}
            animate={{ width: isExpanded ? 260 : 80 }}
            className="relative flex flex-col h-screen bg-black/80 backdrop-blur-xl border-r border-white/10 z-50 flex-shrink-0"
        >
            {/* Decorative top gradient */}
            <div className="absolute top-0 w-full h-32 bg-gradient-to-b from-[#00f0ff]/10 to-transparent pointer-events-none" />

            {/* Header Logo Area */}
            <div className="flex items-center p-6 h-24 mb-4">
                <Link to="/" className="flex items-center gap-4 w-full">
                    <div className="relative flex-shrink-0 w-10 h-10 rounded-lg bg-gradient-to-br from-[#00f0ff] via-[#8a2be2] to-[#ffd700] p-[1px]">
                        <div className="w-full h-full bg-black rounded-lg flex items-center justify-center">
                            <BarChart3 className="w-5 h-5 text-[#00f0ff]" />
                        </div>
                        {/* Pulsing glow */}
                        <div className="absolute inset-0 bg-[#00f0ff]/30 blur-md rounded-lg -z-10 animate-pulse-glow" />
                    </div>

                    <AnimatePresence mode="wait">
                        {isExpanded && (
                            <motion.div
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -10 }}
                                transition={{ duration: 0.2 }}
                                className="whitespace-nowrap overflow-hidden"
                            >
                                <h1 className="text-lg font-bold text-white tracking-wide">WF<span className="text-[#00f0ff]">Market</span></h1>
                                <p className="text-[10px] uppercase tracking-widest text-[#ffd700] opacity-80 font-mono">Set Analyzer</p>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </Link>
            </div>

            {/* Navigation Links */}
            <nav className="flex-1 px-4 space-y-2">
                {navItems.map(({ path, label, icon: Icon }) => {
                    const isActive = location.pathname === path;
                    return (
                        <Link key={path} to={path} className="group block">
                            <div
                                className={cn(
                                    'relative flex items-center h-12 rounded-lg transition-all duration-300',
                                    isActive
                                        ? 'bg-[#00f0ff]/10 border border-[#00f0ff]/30 text-white shadow-[0_0_15px_rgba(0,240,255,0.1)]'
                                        : 'text-gray-400 hover:text-white hover:bg-white/5 border border-transparent'
                                )}
                            >
                                {/* Active Indicator Line */}
                                {isActive && (
                                    <motion.div
                                        layoutId="active-nav-indicator"
                                        className="absolute left-0 top-1/4 bottom-1/4 w-1 bg-[#00f0ff] rounded-r-full shadow-[0_0_10px_rgba(0,240,255,0.8)]"
                                    />
                                )}

                                <div className="flex items-center w-full px-4">
                                    <Icon className={cn("w-5 h-5 flex-shrink-0 transition-colors duration-300", isActive ? "text-[#00f0ff]" : "group-hover:text-[#ffd700]")} />

                                    <AnimatePresence mode="wait">
                                        {isExpanded && (
                                            <motion.span
                                                initial={{ opacity: 0, width: 0 }}
                                                animate={{ opacity: 1, width: "auto" }}
                                                exit={{ opacity: 0, width: 0 }}
                                                transition={{ duration: 0.2 }}
                                                className="ml-4 font-medium tracking-wide whitespace-nowrap overflow-hidden text-sm"
                                            >
                                                {label}
                                            </motion.span>
                                        )}
                                    </AnimatePresence>
                                </div>
                            </div>
                        </Link>
                    );
                })}
            </nav>

            {/* Expand/Collapse Toggle */}
            <div className="p-4 mt-auto border-t border-white/5">
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="w-full h-10 flex items-center justify-center rounded-lg hover:bg-white/5 text-gray-500 hover:text-white transition-colors"
                >
                    {isExpanded ? (
                        <div className="flex items-center gap-2 text-xs uppercase tracking-widest font-mono">
                            <ChevronRight className="w-4 h-4 rotate-180" />
                            <span>Collapse</span>
                        </div>
                    ) : (
                        <Menu className="w-5 h-5" />
                    )}
                </button>
            </div>
        </motion.div>
    );
}
