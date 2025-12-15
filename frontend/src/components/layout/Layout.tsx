import type { ReactNode } from 'react';
import { Header } from './Header';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-dark-bg">
      <Header />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
      <footer className="border-t border-dark-border py-6 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between text-sm text-gray-500">
            <p>Warframe Market Prime Set Analyzer</p>
            <p>Data from <a href="https://warframe.market" target="_blank" rel="noopener noreferrer" className="text-mint hover:underline">warframe.market</a></p>
          </div>
        </div>
      </footer>
    </div>
  );
}
