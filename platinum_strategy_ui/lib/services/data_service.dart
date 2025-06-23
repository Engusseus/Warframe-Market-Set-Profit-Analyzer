import 'dart:convert';
import 'package:flutter/services.dart';
import '../models/price_point.dart';

class DataService {
  Future<List<PricePoint>> loadPricePoints() async {
    final data = await rootBundle.loadString('assets/prices.json');
    final jsonList = json.decode(data)['prices'] as List<dynamic>;
    return jsonList
        .map((e) => PricePoint.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
