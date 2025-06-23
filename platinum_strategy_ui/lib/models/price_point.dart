class PricePoint {
  final DateTime date;
  final double price;

  PricePoint(this.date, this.price);

  factory PricePoint.fromJson(Map<String, dynamic> json) {
    return PricePoint(DateTime.parse(json['date'] as String),
        (json['price'] as num).toDouble());
  }
}
