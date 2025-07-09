# Sample Output

Below is a sample of the CSV output format produced by the Warframe Market Set Profit Analyzer.
If you choose the `xlsx` format, you'll get the same information in an Excel file:

| Set Name | Profit | Set Selling Price | Part Costs Total | Volume (48h) | Score | Part Prices |
|----------|--------|-------------------|------------------|--------------|-------|-------------|
| Saryn Prime Set | 120.5 | 200.0 | 79.5 | 35 | 0.8923 | Saryn Prime Blueprint (x1): 25.0; Saryn Prime Chassis (x1): 15.5; Saryn Prime Systems (x1): 20.0; Saryn Prime Neuroptics (x1): 19.0 |
| Gara Prime Set | 85.0 | 150.0 | 65.0 | 42 | 0.8754 | Gara Prime Blueprint (x1): 15.0; Gara Prime Chassis (x1): 15.0; Gara Prime Systems (x1): 20.0; Gara Prime Neuroptics (x1): 15.0 |
| Mesa Prime Set | 95.0 | 130.0 | 35.0 | 28 | 0.7821 | Mesa Prime Blueprint (x1): 10.0; Mesa Prime Chassis (x1): 10.0; Mesa Prime Systems (x1): 5.0; Mesa Prime Neuroptics (x1): 10.0 |
| Aksomati Prime Set | 35.0 | 75.0 | 40.0 | 25 | 0.5632 | Aksomati Prime Blueprint (x1): 10.0; Aksomati Prime Barrel (x2): 8.0; Aksomati Prime Receiver (x2): 7.0 |

_Note: This is example data and does not reflect actual in-game pricing._

## Understanding the Output

- **Set Name**: The name of the Prime Set or other tradable set
- **Profit**: The difference between the set selling price and the total cost of all parts
- **Set Selling Price**: Average price of the 2 lowest set sell listings from online players
- **Part Costs Total**: Total cost to purchase all required parts at average prices
- **Volume (48h)**: Number of sets traded in the last 48 hours
- **Score**: Combined normalized score of profit and volume (higher is better)
- **Part Prices**: Breakdown of each part's price and quantity needed

The results are sorted by Score in descending order, showing the most profitable and frequently traded items at the top.
