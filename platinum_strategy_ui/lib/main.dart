import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'models/price_point.dart';
import 'services/data_service.dart';
import 'utils/analysis.dart';

void main() {
  runApp(const StrategyApp());
}

class StrategyApp extends StatelessWidget {
  const StrategyApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Platinum Strategy',
      theme: ThemeData.dark(),
      home: const StrategyScreen(),
    );
  }
}

class StrategyScreen extends StatefulWidget {
  const StrategyScreen({Key? key}) : super(key: key);

  @override
  State<StrategyScreen> createState() => _StrategyScreenState();
}

class _StrategyScreenState extends State<StrategyScreen> {
  final _service = DataService();
  List<PricePoint> _data = [];
  List<double> _ma = [];
  late Bands _bands;
  List<Signal> _signals = [];
  bool _stationary = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final data = await _service.loadPricePoints();
    final prices = data.map((e) => e.price).toList();
    final ma = simpleMovingAverage(prices, 14);
    final bands = calcBands(ma, prices, 2.0);
    final signals = detectSignals(prices, bands);
    final stationary = basicStationarityTest(prices);
    setState(() {
      _data = data;
      _ma = ma;
      _bands = bands;
      _signals = signals;
      _stationary = stationary;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Platinum Strategy')),
      body: _data.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : Padding(
              padding: const EdgeInsets.all(8.0),
              child: Column(
                children: [
                  Expanded(child: _buildChart()),
                  Text('Stationarity: ${_stationary ? 'Pass' : 'Fail'}'),
                ],
              ),
            ),
    );
  }

  Widget _buildChart() {
    final spots = <FlSpot>[];
    final maSpots = <FlSpot>[];
    final upperSpots = <FlSpot>[];
    final lowerSpots = <FlSpot>[];
    for (int i = 0; i < _data.length; i++) {
      spots.add(FlSpot(i.toDouble(), _data[i].price));
      maSpots.add(FlSpot(i.toDouble(), _ma[i]));
      upperSpots.add(FlSpot(i.toDouble(), _bands.upper[i]));
      lowerSpots.add(FlSpot(i.toDouble(), _bands.lower[i]));
    }
    return LineChart(LineChartData(
      lineBarsData: [
        LineChartBarData(spots: spots, color: Colors.blue),
        LineChartBarData(spots: maSpots, color: Colors.orange),
        LineChartBarData(spots: upperSpots, color: Colors.red),
        LineChartBarData(spots: lowerSpots, color: Colors.green),
      ],
      showingTooltipIndicators: [
        for (int i = 0; i < _signals.length; i++)
          if (_signals[i] != Signal.none) FlSpot(i.toDouble(), _data[i].price)
      ],
      titlesData: FlTitlesData(show: false),
      gridData: FlGridData(show: false),
    ));
  }
}
