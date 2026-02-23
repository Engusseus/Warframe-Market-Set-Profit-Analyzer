import type { ReactNode } from 'react';
import { Sidebar } from './Sidebar';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="flex h-screen bg-dark-bg font-sans bg-[url('/grid.svg')] bg-fixed" style={{ backgroundImage: "radial-gradient(ellipse at top, rgba(0, 240, 255, 0.05), transparent), radial-gradient(ellipse at bottom, rgba(138, 43, 226, 0.05), transparent)" }}>
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        <main className="flex-1 overflow-y-auto px-4 sm:px-8 lg:px-12 py-10 relative z-10">
          <div className="max-w-[1600px] mx-auto">
            {children}
          </div>
        </main>

        {/* Decorative scanning line */}
        <div className="absolute inset-0 pointer-events-none z-0 opacity-20 overflow-hidden">
          <div className="w-full h-1 bg-[#00f0ff] shadow-[0_0_20px_#00f0ff] animate-[scrolling-bg_8s_linear_infinite]" />
        </div>
      </div>
    </div>
  );
}
