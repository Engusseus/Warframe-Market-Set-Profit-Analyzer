import { Loader2 } from 'lucide-react';

interface LoadingProps {
  message?: string;
  progress?: number;
}

export function Loading({ message = 'Loading...', progress }: LoadingProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 space-y-4">
      <div className="relative">
        <Loader2 className="w-12 h-12 text-mint animate-spin" />
        {progress !== undefined && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs font-medium text-mint">{progress}%</span>
          </div>
        )}
      </div>
      <p className="text-gray-400 animate-pulse">{message}</p>
      {progress !== undefined && (
        <div className="w-64 h-2 bg-dark-border rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-mint to-wf-blue transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
}

export function LoadingOverlay({ message, progress }: LoadingProps) {
  return (
    <div className="fixed inset-0 bg-dark-bg/80 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="card p-8">
        <Loading message={message} progress={progress} />
      </div>
    </div>
  );
}
