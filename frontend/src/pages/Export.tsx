import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, FileJson, Database, Check } from 'lucide-react';
import { getStats, exportData } from '../api/analysis';
import { Layout } from '../components/layout/Layout';
import { Card, StatCard } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Loading } from '../components/common/Loading';

export function Export() {
  const [exporting, setExporting] = useState(false);
  const [exported, setExported] = useState(false);

  const { data: stats, isLoading } = useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
  });

  const handleExport = async () => {
    setExporting(true);
    setExported(false);
    try {
      const blob = await exportData();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `market_data_export_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      setExported(true);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setExporting(false);
    }
  };

  if (isLoading) {
    return (
      <Layout>
        <Loading message="Loading export information..." />
      </Layout>
    );
  }

  const hasData = stats && stats.database.total_runs > 0;

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold gradient-text">Export Data</h1>
          <p className="text-gray-400 mt-1">
            Export historical analysis data for external analysis
          </p>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard
              label="Total Runs"
              value={stats.database.total_runs}
              icon={<Database className="w-5 h-5" />}
              color="mint"
            />
            <StatCard
              label="Total Records"
              value={stats.database.total_profit_records.toLocaleString()}
              icon={<FileJson className="w-5 h-5" />}
              color="blue"
            />
            <StatCard
              label="Database Size"
              value={`${(stats.database.database_size_bytes / 1024).toFixed(1)} KB`}
              icon={<Download className="w-5 h-5" />}
              color="purple"
            />
          </div>
        )}

        {/* Export Card */}
        <Card className="max-w-2xl">
          <div className="flex items-start space-x-4">
            <div className="p-3 rounded-lg bg-mint/10">
              <FileJson className="w-8 h-8 text-mint" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-gray-100">JSON Export</h3>
              <p className="text-gray-400 text-sm mt-1">
                Export all historical market runs and profit data as a JSON file.
                Includes metadata, run summaries, and detailed profit margins for each set.
              </p>

              {stats && (
                <div className="mt-4 p-3 bg-dark-hover rounded-lg">
                  <h4 className="text-sm font-medium text-gray-300 mb-2">Export Contents</h4>
                  <ul className="text-sm text-gray-400 space-y-1">
                    <li>• {stats.database.total_runs} market runs</li>
                    <li>• {stats.database.total_profit_records} profit records</li>
                    {stats.database.first_run && (
                      <li>• Data from {stats.database.first_run} to {stats.database.last_run}</li>
                    )}
                    {stats.database.time_span_days && (
                      <li>• {stats.database.time_span_days.toFixed(1)} days of data</li>
                    )}
                  </ul>
                </div>
              )}

              <div className="mt-6 flex items-center space-x-4">
                <Button
                  onClick={handleExport}
                  loading={exporting}
                  disabled={!hasData}
                  icon={exported ? <Check className="w-4 h-4" /> : <Download className="w-4 h-4" />}
                >
                  {exported ? 'Downloaded!' : 'Download JSON'}
                </Button>
                {!hasData && (
                  <span className="text-sm text-gray-500">
                    Run an analysis first to have data to export
                  </span>
                )}
              </div>
            </div>
          </div>
        </Card>

        {/* Info Card */}
        <Card className="max-w-2xl bg-wf-blue/5 border-wf-blue/30">
          <h4 className="text-sm font-medium text-wf-blue mb-2">About the Export</h4>
          <p className="text-sm text-gray-400">
            The exported JSON file contains structured data suitable for analysis in tools
            like Excel, Python, or data visualization platforms. Each market run includes
            timestamps, profit margins, and lowest prices for all Prime sets analyzed.
          </p>
        </Card>
      </div>
    </Layout>
  );
}
