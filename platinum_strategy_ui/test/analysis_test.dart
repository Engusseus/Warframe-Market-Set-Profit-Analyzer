import 'package:flutter_test/flutter_test.dart';
import 'package:platinum_strategy_ui/utils/analysis.dart';

void main() {
  test('moving average and bands', () {
    final prices = [1.0, 2.0, 3.0, 4.0];
    final ma = simpleMovingAverage(prices, 2);
    expect(ma.last, 3.5);
    final bands = calcBands(ma, prices, 1.0);
    expect(bands.upper.length, prices.length);
  });

  test('signal detection', () {
    final prices = [1.0, 5.0, 1.0];
    final ma = simpleMovingAverage(prices, 3);
    final bands = calcBands(ma, prices, 1.0);
    final signals = detectSignals(prices, bands);
    expect(signals.first, Signal.buy);
  });

  test('stationarity test', () {
    final prices = [1.0, 1.1, 0.9, 1.05, 1.0];
    expect(basicStationarityTest(prices), isTrue);
  });
}
