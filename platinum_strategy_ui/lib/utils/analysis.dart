import 'dart:math';
import '../models/price_point.dart';

List<double> simpleMovingAverage(List<double> values, int period) {
  final List<double> result = [];
  for (int i = 0; i < values.length; i++) {
    final start = max(0, i - period + 1);
    final subset = values.sublist(start, i + 1);
    final avg = subset.reduce((a, b) => a + b) / subset.length;
    result.add(avg);
  }
  return result;
}

class Bands {
  final List<double> upper;
  final List<double> lower;
  Bands(this.upper, this.lower);
}

Bands calcBands(List<double> ma, List<double> values, double stdevMul) {
  final List<double> upper = [];
  final List<double> lower = [];
  for (int i = 0; i < ma.length; i++) {
    final start = 0;
    final subset = values.sublist(start, i + 1);
    final mean = ma[i];
    final variance = subset
            .map((v) => pow(v - mean, 2))
            .reduce((a, b) => a + b) /
        subset.length;
    final dev = sqrt(variance);
    upper.add(mean + dev * stdevMul);
    lower.add(mean - dev * stdevMul);
  }
  return Bands(upper, lower);
}

enum Signal { none, buy, sell }

List<Signal> detectSignals(List<double> values, Bands bands) {
  final List<Signal> signals = [];
  for (int i = 0; i < values.length; i++) {
    final price = values[i];
    if (price < bands.lower[i]) {
      signals.add(Signal.buy);
    } else if (price > bands.upper[i]) {
      signals.add(Signal.sell);
    } else {
      signals.add(Signal.none);
    }
  }
  return signals;
}

bool basicStationarityTest(List<double> values) {
  if (values.length < 2) return false;
  final diffs = <double>[];
  for (int i = 1; i < values.length; i++) {
    diffs.add(values[i] - values[i - 1]);
  }
  final mean = diffs.reduce((a, b) => a + b) / diffs.length;
  final variance = diffs
          .map((v) => pow(v - mean, 2))
          .reduce((a, b) => a + b) /
      diffs.length;
  return variance < 1.0; // arbitrary threshold
}
