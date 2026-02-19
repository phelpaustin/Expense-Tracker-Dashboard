# performance.py
"""
Performance optimization utilities for the Expense Tracker.
Includes caching, batching, lazy loading, and performance monitoring.
"""
import streamlit as st
import pandas as pd
import time
from functools import wraps, lru_cache
from typing import Callable, Any, Optional, Dict
from datetime import datetime, timedelta
from error_handler import logger


# ============================================================
# PERFORMANCE MONITORING
# ============================================================
class PerformanceTimer:
    """Context manager for timing operations."""
    
    def __init__(self, operation_name: str, log_threshold: float = 1.0):
        """
        Args:
            operation_name: Name of operation being timed
            log_threshold: Only log if operation takes longer than this (seconds)
        """
        self.operation_name = operation_name
        self.log_threshold = log_threshold
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        elapsed = self.end_time - self.start_time
        
        if elapsed >= self.log_threshold:
            logger.warning(f"⏱️ {self.operation_name} took {elapsed:.2f}s")
        else:
            logger.debug(f"⏱️ {self.operation_name} took {elapsed:.3f}s")
    
    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time


def time_function(func: Callable) -> Callable:
    """Decorator to time function execution."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        with PerformanceTimer(f"Function {func.__name__}"):
            return func(*args, **kwargs)
    return wrapper


# ============================================================
# CACHING STRATEGIES
# ============================================================
class DataFrameCache:
    """Simple cache for DataFrames to avoid recomputation."""
    
    _cache: Dict[str, tuple] = {}  # key -> (data, timestamp)
    _cache_duration = timedelta(seconds=300)  # 5 minutes default
    
    @classmethod
    def get(cls, key: str) -> Optional[pd.DataFrame]:
        """Get cached DataFrame if not expired."""
        if key in cls._cache:
            data, timestamp = cls._cache[key]
            if datetime.now() - timestamp < cls._cache_duration:
                logger.debug(f"Cache hit: {key}")
                return data
            else:
                logger.debug(f"Cache expired: {key}")
                del cls._cache[key]
        return None
    
    @classmethod
    def set(cls, key: str, data: pd.DataFrame):
        """Cache DataFrame."""
        cls._cache[key] = (data.copy(), datetime.now())
        logger.debug(f"Cached: {key} ({len(data)} rows)")
    
    @classmethod
    def clear(cls, key: Optional[str] = None):
        """Clear cache (all or specific key)."""
        if key:
            if key in cls._cache:
                del cls._cache[key]
                logger.debug(f"Cleared cache: {key}")
        else:
            cls._cache.clear()
            logger.debug("Cleared all cache")
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """Get cache statistics."""
        total_size = sum(len(data) for data, _ in cls._cache.values())
        return {
            "cached_keys": len(cls._cache),
            "total_rows": total_size,
            "keys": list(cls._cache.keys())
        }


def cache_dataframe(ttl: int = 300):
    """
    Decorator to cache DataFrame results.
    
    Args:
        ttl: Time to live in seconds
    
    Usage:
        @cache_dataframe(ttl=600)
        def expensive_aggregation(df):
            return df.groupby('Category').sum()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and args
            cache_key = f"{func.__name__}_{hash(str(args))}"
            
            # Try to get from cache
            cached = DataFrameCache.get(cache_key)
            if cached is not None:
                return cached
            
            # Compute and cache
            result = func(*args, **kwargs)
            if isinstance(result, pd.DataFrame):
                DataFrameCache.set(cache_key, result)
            
            return result
        
        return wrapper
    return decorator


# ============================================================
# LAZY LOADING
# ============================================================
class LazyDataLoader:
    """Lazy load large datasets in chunks."""
    
    def __init__(self, data_source: Callable, chunk_size: int = 1000):
        """
        Args:
            data_source: Function that returns full dataset
            chunk_size: Number of rows per chunk
        """
        self.data_source = data_source
        self.chunk_size = chunk_size
        self._full_data = None
        self._loaded = False
    
    def get_chunk(self, start: int = 0, end: Optional[int] = None) -> pd.DataFrame:
        """Get a chunk of data."""
        if not self._loaded:
            self._full_data = self.data_source()
            self._loaded = True
        
        end = end or (start + self.chunk_size)
        return self._full_data.iloc[start:end]
    
    def get_all(self) -> pd.DataFrame:
        """Get full dataset."""
        if not self._loaded:
            self._full_data = self.data_source()
            self._loaded = True
        return self._full_data
    
    @property
    def total_rows(self) -> int:
        """Get total number of rows."""
        if not self._loaded:
            self._full_data = self.data_source()
            self._loaded = True
        return len(self._full_data)


# ============================================================
# BATCH PROCESSING
# ============================================================
def process_in_batches(
    df: pd.DataFrame,
    batch_size: int,
    processor: Callable[[pd.DataFrame], pd.DataFrame],
    show_progress: bool = True
) -> pd.DataFrame:
    """
    Process large DataFrame in batches.
    
    Args:
        df: DataFrame to process
        batch_size: Rows per batch
        processor: Function to apply to each batch
        show_progress: Show progress bar
    
    Returns:
        Processed DataFrame
    """
    if df.empty:
        return df
    
    total_rows = len(df)
    num_batches = (total_rows + batch_size - 1) // batch_size
    
    results = []
    
    if show_progress:
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    for i in range(num_batches):
        start_idx = i * batch_size
        end_idx = min((i + 1) * batch_size, total_rows)
        
        batch = df.iloc[start_idx:end_idx]
        processed_batch = processor(batch)
        results.append(processed_batch)
        
        if show_progress:
            progress = (i + 1) / num_batches
            progress_bar.progress(progress)
            status_text.text(f"Processing batch {i + 1}/{num_batches}")
    
    if show_progress:
        progress_bar.empty()
        status_text.empty()
    
    return pd.concat(results, ignore_index=True)


# ============================================================
# DATAFRAME OPTIMIZATION
# ============================================================
def optimize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Optimize DataFrame memory usage.
    
    Converts:
    - float64 to float32 where possible
    - int64 to smaller int types
    - object columns to category where beneficial
    
    Args:
        df: DataFrame to optimize
    
    Returns:
        Optimized DataFrame
    """
    if df.empty:
        return df
    
    initial_memory = df.memory_usage(deep=True).sum() / 1024**2  # MB
    df_optimized = df.copy()
    
    for col in df_optimized.columns:
        col_type = df_optimized[col].dtype
        
        # Optimize floats
        if col_type == 'float64':
            df_optimized[col] = df_optimized[col].astype('float32')
        
        # Optimize integers
        elif col_type == 'int64':
            c_min = df_optimized[col].min()
            c_max = df_optimized[col].max()
            
            if c_min > -128 and c_max < 127:
                df_optimized[col] = df_optimized[col].astype('int8')
            elif c_min > -32768 and c_max < 32767:
                df_optimized[col] = df_optimized[col].astype('int16')
            elif c_min > -2147483648 and c_max < 2147483647:
                df_optimized[col] = df_optimized[col].astype('int32')
        
        # Optimize strings to category if cardinality is low
        elif col_type == 'object':
            num_unique = df_optimized[col].nunique()
            num_total = len(df_optimized[col])
            
            # Convert to category if < 50% unique values
            if num_unique / num_total < 0.5:
                df_optimized[col] = df_optimized[col].astype('category')
    
    final_memory = df_optimized.memory_usage(deep=True).sum() / 1024**2  # MB
    reduction = (1 - final_memory / initial_memory) * 100
    
    logger.info(f"Memory optimization: {initial_memory:.2f}MB → {final_memory:.2f}MB ({reduction:.1f}% reduction)")
    
    return df_optimized


# ============================================================
# QUERY OPTIMIZATION
# ============================================================
@cache_dataframe(ttl=300)
def optimized_groupby(df: pd.DataFrame, groupby_cols: list, agg_dict: dict) -> pd.DataFrame:
    """
    Optimized groupby operation with caching.
    
    Args:
        df: DataFrame to aggregate
        groupby_cols: Columns to group by
        agg_dict: Aggregation dictionary
    
    Returns:
        Aggregated DataFrame
    """
    with PerformanceTimer("GroupBy operation"):
        return df.groupby(groupby_cols).agg(agg_dict).reset_index()


def filter_efficiently(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """
    Apply multiple filters efficiently.
    
    Args:
        df: DataFrame to filter
        filters: Dictionary of column -> value(s) to filter
    
    Returns:
        Filtered DataFrame
    """
    if df.empty:
        return df
    
    with PerformanceTimer("Filtering operation"):
        mask = pd.Series([True] * len(df))
        
        for col, values in filters.items():
            if col not in df.columns:
                continue
            
            if isinstance(values, (list, tuple, set)):
                mask &= df[col].isin(values)
            else:
                mask &= df[col] == values
        
        return df[mask]


# ============================================================
# STREAMLIT OPTIMIZATION
# ============================================================
def reduce_rerun_frequency():
    """
    Prevent excessive reruns by debouncing.
    
    Usage:
        if st.button("Filter"):
            reduce_rerun_frequency()
            # ... filtering logic ...
            st.rerun()
    """
    # Add small delay to batch rapid clicks
    time.sleep(0.1)


@st.cache_data(ttl=60, show_spinner=False)
def cached_computation(data_hash: int, computation_func: Callable, *args, **kwargs):
    """
    Cache expensive computations with data version tracking.
    
    Args:
        data_hash: Hash of input data for cache invalidation
        computation_func: Function to compute
        *args, **kwargs: Arguments for computation_func
    
    Returns:
        Result of computation
    """
    return computation_func(*args, **kwargs)


def defer_computation(condition: bool, placeholder: Any = None):
    """
    Defer computation until needed.
    
    Args:
        condition: Whether to compute now
        placeholder: Value to return if deferred
    
    Returns:
        Placeholder if deferred, else None (compute)
    """
    if not condition:
        return placeholder
    return None


# ============================================================
# BULK OPERATIONS
# ============================================================
def bulk_insert(df_existing: pd.DataFrame, new_rows: list) -> pd.DataFrame:
    """
    Efficiently insert multiple rows at once.
    
    Args:
        df_existing: Existing DataFrame
        new_rows: List of dictionaries (rows to insert)
    
    Returns:
        DataFrame with new rows
    """
    with PerformanceTimer(f"Bulk insert {len(new_rows)} rows"):
        new_df = pd.DataFrame(new_rows)
        return pd.concat([df_existing, new_df], ignore_index=True)


def bulk_update(df: pd.DataFrame, updates: dict, condition: pd.Series) -> pd.DataFrame:
    """
    Efficiently update multiple rows at once.
    
    Args:
        df: DataFrame to update
        updates: Dictionary of column -> new_value
        condition: Boolean mask for rows to update
    
    Returns:
        Updated DataFrame
    """
    with PerformanceTimer(f"Bulk update {condition.sum()} rows"):
        df_updated = df.copy()
        for col, value in updates.items():
            df_updated.loc[condition, col] = value
        return df_updated


# ============================================================
# PERFORMANCE TIPS
# ============================================================
class PerformanceTips:
    """Performance optimization tips and best practices."""
    
    @staticmethod
    def show_tips():
        """Display performance tips in Streamlit."""
        with st.expander("⚡ Performance Tips"):
            st.markdown("""
            ### Optimize Your App
            
            1. **Use caching wisely**
               - Cache expensive computations with `@st.cache_data`
               - Clear cache when data changes
            
            2. **Minimize reruns**
               - Use session state instead of reruns
               - Batch UI updates
            
            3. **Optimize DataFrames**
               - Filter early, aggregate late
               - Use categorical types for low-cardinality columns
               - Consider using `optimize_dataframe()`
            
            4. **Lazy load data**
               - Load data only when needed
               - Use pagination for large datasets
            
            5. **Batch operations**
               - Insert/update multiple rows at once
               - Process in batches for large datasets
            """)
    
    @staticmethod
    def get_optimization_suggestions(df: pd.DataFrame) -> list:
        """Get optimization suggestions for DataFrame."""
        suggestions = []
        
        # Check size
        if len(df) > 10000:
            suggestions.append("Consider using pagination or lazy loading for large dataset")
        
        # Check memory usage
        memory_mb = df.memory_usage(deep=True).sum() / 1024**2
        if memory_mb > 100:
            suggestions.append(f"High memory usage ({memory_mb:.1f}MB). Try optimize_dataframe()")
        
        # Check data types
        for col in df.columns:
            if df[col].dtype == 'object':
                unique_ratio = df[col].nunique() / len(df)
                if unique_ratio < 0.5:
                    suggestions.append(f"Column '{col}' could be converted to category type")
        
        return suggestions


# ============================================================
# EXPORT
# ============================================================
__all__ = [
    # Timing
    "PerformanceTimer",
    "time_function",
    
    # Caching
    "DataFrameCache",
    "cache_dataframe",
    "cached_computation",
    
    # Lazy loading
    "LazyDataLoader",
    
    # Batch processing
    "process_in_batches",
    "bulk_insert",
    "bulk_update",
    
    # Optimization
    "optimize_dataframe",
    "optimized_groupby",
    "filter_efficiently",
    
    # Streamlit
    "reduce_rerun_frequency",
    "defer_computation",
    
    # Tips
    "PerformanceTips",
]