import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { BarChart3, History, Download, Activity, ChevronRight, Menu } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '../../utils/cn';

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
            <div className="absolute top-0 w-full h-32 bg-gradient-to-b from-[#e5c158]/5 to-transparent pointer-events-none" />

            {/* Header Logo Area */}
            <div className="flex items-center p-6 h-24 mb-4">
                <Link to="/" className="flex items-center gap-4 w-full">
                    <div className="relative flex-shrink-0 w-10 h-10 border border-[#e5c158]/30 bg-[#1a1c23] wf-corner flex items-center justify-center shadow-[0_0_15px_rgba(229,193,88,0.1)]">
                        <BarChart3 className="w-5 h-5 text-[#e5c158]" />
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
                                <h1 className="text-lg font-bold text-white tracking-wide">WF<span className="text-[#e5c158]">Market</span></h1>
                                <p className="text-[10px] uppercase tracking-widest text-[#2ebfcc] opacity-80 font-mono">Set Analyzer</p>
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
                                    'relative flex items-center h-12 transition-all duration-300',
                                    isActive
                                        ? 'bg-[#e5c158]/10 border border-[#e5c158]/20 text-white shadow-[0_0_15px_rgba(229,193,88,0.05)] wf-corner'
                                        : 'text-gray-400 hover:text-white hover:bg-white/5 border border-transparent rounded-lg'
                                )}
                            >
                                {/* Active Indicator Line */}
                                {isActive && (
                                    <motion.div
                                        layoutId="active-nav-indicator"
                                        className="absolute left-0 top-2 bottom-2 w-1 bg-[#e5c158] shadow-[0_0_8px_rgba(229,193,88,0.4)]"
                                    />
                                )}

                                <div className="flex items-center w-full px-4">
                                    <Icon className={cn("w-5 h-5 flex-shrink-0 transition-colors duration-300", isActive ? "text-[#e5c158]" : "group-hover:text-[#2ebfcc]")} />

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
