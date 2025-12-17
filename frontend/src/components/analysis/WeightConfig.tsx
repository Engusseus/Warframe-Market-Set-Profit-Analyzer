import { useState } from 'react';
import { Sliders, RotateCcw } from 'lucide-react';
import { Button } from '../common/Button';

interface WeightConfigProps {
  profitWeight: number;
  volumeWeight: number;
  onApply: (profitWeight: number, volumeWeight: number) => void;
  loading?: boolean;
}

const presets = [
  { name: 'Balanced', profit: 1.0, volume: 1.2, description: 'Default weights' },
  { name: 'Profit Focus', profit: 1.5, volume: 0.8, description: 'Emphasize margins' },
  { name: 'Volume Focus', profit: 0.8, volume: 1.5, description: 'Emphasize liquidity' },
];

export function WeightConfig({ profitWeight, volumeWeight, onApply, loading }: WeightConfigProps) {
  const [profit, setProfit] = useState(profitWeight);
  const [volume, setVolume] = useState(volumeWeight);

  const handleApply = () => {
    onApply(profit, volume);
  };

  const handleReset = () => {
    setProfit(1.0);
    setVolume(1.2);
  };

  const applyPreset = (preset: typeof presets[0]) => {
    setProfit(preset.profit);
    setVolume(preset.volume);
  };

  return (
    <div className="card space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Sliders className="w-5 h-5 text-wf-purple" />
          <h3 className="text-lg font-semibold text-gray-100">Scoring Weights</h3>
        </div>
        <button
          onClick={handleReset}
          className="text-gray-400 hover:text-mint transition-colors"
          title="Reset to defaults"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>

      {/* Presets */}
      <div className="flex flex-wrap gap-2">
        {presets.map((preset) => (
          <button
            key={preset.name}
            onClick={() => applyPreset(preset)}
            className={`px-3 py-1.5 text-sm rounded-lg border transition-all duration-200 ${
              profit === preset.profit && volume === preset.volume
                ? 'border-mint bg-mint/10 text-mint'
                : 'border-dark-border text-gray-400 hover:border-mint/30 hover:text-gray-200'
            }`}
          >
            {preset.name}
          </button>
        ))}
      </div>

      {/* Sliders */}
      <div className="space-y-4">
        <div>
          <div className="flex justify-between text-sm mb-2">
            <label className="text-gray-300">Profit Weight</label>
            <span className="text-mint font-medium">{profit.toFixed(1)}</span>
          </div>
          <input
            type="range"
            min="0"
            max="3"
            step="0.1"
            value={profit}
            onChange={(e) => setProfit(parseFloat(e.target.value))}
            className="w-full h-2 bg-dark-border rounded-lg appearance-none cursor-pointer accent-mint"
          />
        </div>

        <div>
          <div className="flex justify-between text-sm mb-2">
            <label className="text-gray-300">Volume Weight</label>
            <span className="text-wf-blue font-medium">{volume.toFixed(1)}</span>
          </div>
          <input
            type="range"
            min="0"
            max="3"
            step="0.1"
            value={volume}
            onChange={(e) => setVolume(parseFloat(e.target.value))}
            className="w-full h-2 bg-dark-border rounded-lg appearance-none cursor-pointer accent-wf-blue"
          />
        </div>
      </div>

      {/* Apply Button */}
      <Button
        onClick={handleApply}
        loading={loading}
        className="w-full"
        disabled={profit === profitWeight && volume === volumeWeight}
      >
        Apply Weights
      </Button>
    </div>
  );
}
