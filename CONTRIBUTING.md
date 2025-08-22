# Contributing to Warframe Market Set Profit Analyzer

Thank you for your interest in contributing! This project values **modular design**, **clean architecture**, and **maintainable code**. This guide will help you contribute effectively while maintaining the project's high standards.

## 🎯 Contribution Philosophy

### Modularity First
We prioritize **modular, composable code** that:
- **Single Responsibility**: Each function should have one clear purpose
- **Loose Coupling**: Components should interact through well-defined interfaces
- **High Cohesion**: Related functionality should be grouped together
- **Testable Design**: Code should be easily unit testable in isolation

### Code Quality Standards
- **Clear Function Names**: Functions should be self-documenting
- **Comprehensive Error Handling**: Graceful degradation over crashes
- **Performance Conscious**: Efficient algorithms and data structures
- **Cross-Platform Compatible**: Works on Windows, macOS, and Linux

## 🚀 Getting Started

### Prerequisites
- Python 3.7+ 
- Git
- Text editor or IDE of choice

### Development Setup
1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer.git
   cd Warframe-Market-Set-Profit-Analyzer
   ```

2. **Run the application to ensure it works**
   ```bash
   python main.py
   ```

3. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 🏗️ Architecture Guidelines

### Current Modular Structure

The application follows a **functional modular design** with clear separation of concerns:

```
Data Collection Layer
├── setup_venv()           # Environment management
├── RateLimiter            # API throttling
├── fetch_* functions      # API data retrieval
└── *_with_retry()         # Network reliability

Data Processing Layer  
├── calculate_profit_margins()    # Business logic
├── normalize_data()              # Data transformation
├── calculate_profitability_scores() # Scoring algorithms
└── calculate_hash()              # Cache validation

Presentation Layer
├── display_* functions    # Output formatting
├── get_user_weights()     # User interaction
└── main execution flow    # Orchestration

Storage Layer
├── load_cache()          # Data persistence
├── save_cache()          # Cache management
└── Cache invalidation    # Performance optimization
```

### Adding New Modules

When adding new functionality, follow these **modular design principles**:

#### ✅ DO: Create Focused, Composable Functions
```python
def calculate_market_trends(price_history, volume_history, days=7):
    """Calculate market trend indicators for a specific time period.
    
    Args:
        price_history: List of price data points
        volume_history: List of volume data points  
        days: Number of days to analyze (default: 7)
        
    Returns:
        dict: Trend indicators (direction, volatility, momentum)
    """
    # Single responsibility: trend calculation only
    # No side effects, easily testable
    # Clear input/output contract
```

#### ✅ DO: Use Dependency Injection
```python
def analyze_profitability(data_fetcher, calculator, weights):
    """Analyze profitability using injected dependencies.
    
    This allows easy testing and different implementations.
    """
    raw_data = data_fetcher.fetch_market_data()
    processed_data = calculator.calculate_margins(raw_data)
    return calculator.apply_weights(processed_data, weights)
```

#### ❌ DON'T: Create Monolithic Functions
```python
# AVOID: Function that does too many things
def analyze_everything_and_display():
    # Fetches data
    # Processes data  
    # Calculates scores
    # Displays results
    # Updates cache
    # Hard to test, modify, or reuse
```

#### ❌ DON'T: Use Global State
```python
# AVOID: Global variables that create hidden dependencies
global_cache = {}
global_api_client = None

def some_function():
    # Implicitly depends on global state
    # Hard to test and reason about
```

## 🔧 Development Areas

### High-Priority Areas for Modular Contributions

#### 1. **Data Analysis Modules**
Create new analysis modules that follow the existing pattern:

**Example: Market Volatility Analysis**
```python
def calculate_price_volatility(price_data, time_window_hours=24):
    """Calculate price volatility metrics."""
    # Focused on volatility calculation only
    # No API calls or display logic
    # Returns structured data for other modules to use

def detect_market_anomalies(volatility_data, threshold=2.0):
    """Detect unusual market behavior."""
    # Builds on volatility module
    # Single responsibility: anomaly detection
```

#### 2. **New Scoring Algorithms**
Extend the scoring system with modular components:

```python
def calculate_risk_score(profit_data, volume_data, volatility_data):
    """Calculate risk assessment scores."""
    # Uses output from other modules
    # Focused solely on risk calculation
    
def apply_trading_strategy_weights(scores, strategy_name):
    """Apply predefined trading strategy weights."""
    # Modular strategy application
    # Easy to add new strategies
```

#### 3. **Alternative Data Sources**
Create modular data fetchers:

```python
class WarframeMarketDataFetcher:
    """Current API data fetcher."""
    def fetch_pricing_data(self, item_slug):
        # Implementation for current API
        
class AlternativeDataFetcher:
    """Alternative data source with same interface."""
    def fetch_pricing_data(self, item_slug):
        # Different implementation, same interface
        # Allows easy switching between data sources
```

#### 4. **Export/Import Modules**
Add modular data export capabilities:

```python
def export_to_csv(analysis_data, filename):
    """Export analysis results to CSV format."""
    # Single purpose: CSV export
    # No dependencies on display or calculation logic

def export_to_json(analysis_data, filename):
    """Export analysis results to JSON format."""
    # Parallel module with same interface pattern
```

### Medium-Priority Areas

#### **Enhanced Caching Strategies**
```python
def create_cache_strategy(strategy_type="hash_based"):
    """Factory for different caching strategies."""
    # Modular approach to different caching methods
    # Easy to add new strategies (time-based, size-based, etc.)
```

#### **Configuration Management**
```python
def load_configuration(config_source="file"):
    """Load configuration from various sources."""
    # Modular configuration loading
    # Support for files, environment variables, CLI args
```

#### **Testing Framework Integration**
Create modular test utilities:
```python
def create_mock_api_data(set_count=10, part_count_per_set=3):
    """Generate realistic test data for development."""
    # Helps other contributors test their modules
```

## 📝 Code Standards

### Function Design Guidelines

#### Required Function Documentation
```python
def your_function(param1, param2, optional_param=None):
    """Brief description of what the function does.
    
    Args:
        param1 (type): Description of param1
        param2 (type): Description of param2  
        optional_param (type, optional): Description. Defaults to None.
        
    Returns:
        type: Description of return value
        
    Raises:
        SpecificException: Description of when this is raised
    """
```

#### Error Handling Pattern
```python
def robust_function(data):
    """Follow the established error handling pattern."""
    if not data:
        print("Warning: No data provided, using defaults")
        return get_default_data()
    
    try:
        result = process_data(data)
        return result
    except SpecificException as e:
        print(f"Error processing data: {e}")
        return None  # or appropriate fallback
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
```

#### Performance Considerations
```python
def efficient_function(large_dataset):
    """Follow performance patterns used in the codebase."""
    # Use lookup dictionaries for O(1) access
    lookup = {item['id']: item for item in large_dataset}
    
    # Process in batches if needed
    batch_size = 100
    for i in range(0, len(large_dataset), batch_size):
        batch = large_dataset[i:i + batch_size]
        process_batch(batch)
```

### Testing Your Modules

#### Manual Testing Checklist
- [ ] Function works with expected inputs
- [ ] Function handles empty/None inputs gracefully  
- [ ] Function handles malformed data appropriately
- [ ] Function respects rate limiting (if making API calls)
- [ ] Function follows existing error handling patterns
- [ ] Function integrates properly with existing codebase

#### Integration Testing
```python
# Test your module with the existing system
def test_integration():
    # Use existing data fetching
    cache = load_cache()
    
    # Test your module
    result = your_new_function(cache['detailed_sets'])
    
    # Verify it works with existing display functions
    display_your_results(result)
```

## 📤 Submission Guidelines

### Pull Request Process

1. **Create Focused PRs**: One feature or fix per pull request
2. **Modular Changes**: Changes should enhance modularity, not reduce it
3. **Backward Compatibility**: Don't break existing functionality
4. **Documentation**: Update relevant documentation
5. **Testing**: Test your changes thoroughly

### PR Template
```markdown
## Description
Brief description of changes and why they're needed.

## Type of Change
- [ ] New modular feature
- [ ] Enhancement to existing module  
- [ ] Bug fix
- [ ] Documentation update
- [ ] Performance improvement

## Modularity Impact
- [ ] Improves code modularity
- [ ] Maintains existing modularity  
- [ ] No impact on modularity
- [ ] Requires discussion about design

## Testing
- [ ] Manual testing completed
- [ ] Integration testing completed
- [ ] No breaking changes to existing functionality

## Checklist
- [ ] Code follows project style guidelines
- [ ] Function documentation is complete
- [ ] Error handling follows project patterns
- [ ] Changes are backwards compatible
```

### Code Review Focus Areas

Reviewers will specifically look for:
- **Modularity**: Is the code properly modular and reusable?
- **Single Responsibility**: Does each function have one clear purpose?
- **Error Handling**: Does it follow the project's graceful degradation pattern?
- **Performance**: Are there any performance regressions?
- **Integration**: Does it work well with existing modules?

## 🎖️ Recognition

Contributors who follow these modularity guidelines and make quality contributions will be:
- Listed in project acknowledgments
- Given credit in relevant documentation
- Considered for collaborator status for significant contributions

## 💬 Getting Help

### Before You Start
- Review the `CLAUDE.md` file for technical architecture details
- Look at existing functions as examples of modular design
- Check existing issues for related work

### Communication Channels
- **GitHub Issues**: Technical questions, feature discussions
- **GitHub Discussions**: General questions, architecture discussions  
- **Pull Request Comments**: Code-specific questions

### Mentorship for New Contributors
If you're new to modular design or this codebase:
1. Start with small, focused contributions
2. Ask questions in issues before starting work
3. Reference existing modular patterns in the codebase
4. Don't hesitate to ask for design feedback early

## 🌟 Example Contributions

### Good Modular Contribution Example
```python
# NEW MODULE: market_trends.py

def calculate_price_trend(price_history, days=7):
    """Calculate price trend over specified days."""
    # Focused, single-responsibility function
    # Easy to test and reuse

def detect_trend_changes(trends, sensitivity=0.1):
    """Detect significant trend changes."""
    # Builds on previous function
    # Composable design

def format_trend_display(trends):
    """Format trends for display."""
    # Separate presentation logic
    # Follows existing display patterns
```

### Integration Example
```python
# In main.py - integrate the new module
from market_trends import calculate_price_trend, format_trend_display

# In analysis section:
if price_history_available:
    trends = calculate_price_trend(price_history)
    display_trends = format_trend_display(trends)
    print(display_trends)
```

---

**Thank you for contributing to a more modular, maintainable codebase!** 🚀

Your efforts help make this tool better for the entire Warframe trading community.