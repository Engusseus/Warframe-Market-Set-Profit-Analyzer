import { Link, useLocation } from 'react-router-dom';
import { BarChart3, History, Download, Activity } from 'lucide-react';
import clsx from 'clsx';

const navItems = [
  { path: '/', label: 'Dashboard', icon: BarChart3 },
  { path: '/analysis', label: 'Analysis', icon: Activity },
  { path: '/history', label: 'History', icon: History },
  { path: '/export', label: 'Export', icon: Download },
];

export function Header() {
  const location = useLocation();

  return (
    <header className="bg-dark-card border-b border-dark-border sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-mint via-wf-blue to-wf-purple flex items-center justify-center">
              <BarChart3 className="w-6 h-6 text-dark-bg" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-mint">Warframe Market</h1>
              <p className="text-xs text-gray-400">Prime Set Analyzer</p>
            </div>
          </Link>

          {/* Navigation */}
          <nav className="flex items-center space-x-1">
            {navItems.map(({ path, label, icon: Icon }) => {
              const isActive = location.pathname === path;
              return (
                <Link
                  key={path}
                  to={path}
                  className={clsx(
                    'flex items-center space-x-2 px-4 py-2 rounded-lg transition-all duration-200',
                    isActive
                      ? 'bg-mint/10 text-mint border border-mint/30'
                      : 'text-gray-400 hover:text-mint hover:bg-dark-hover'
                  )}
                >
                  <Icon className="w-4 h-4" />
                  <span className="hidden sm:inline">{label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </div>
    </header>
  );
}
