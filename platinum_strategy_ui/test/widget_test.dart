import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:platinum_strategy_ui/main.dart';

void main() {
  testWidgets('renders chart', (tester) async {
    await tester.pumpWidget(const StrategyApp());
    await tester.pump(); // wait for async data
    expect(find.byType(StrategyScreen), findsOneWidget);
  });
}
