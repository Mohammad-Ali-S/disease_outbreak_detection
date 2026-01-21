import numpy as np
from scipy.spatial.distance import euclidean
from scipy.stats import pearsonr
import statsmodels.api as sm
from fastdtw import fastdtw

class DistanceMetrics:
    """Implementations of distance measures from the paper."""
    
    @staticmethod
    def spatial_distance(coord1, coord2):
        """
        Euclidean distance between two spatial coordinates (lat, lon).
        Coord format: (lat, lon)
        """
        return euclidean(coord1, coord2)

    @staticmethod
    def temporal_correlation(series1, series2):
        """
        Correlation-based distance: sqrt(2 * (1 - PearsonCorr))
        """
        # Pearson returns (corr, p-value)
        corr, _ = pearsonr(series1, series2)
        # Handle cases where correlation is NaN (e.g., constant series)
        if np.isnan(corr):
            corr = 0
        return np.sqrt(2 * (1 - corr))

    @staticmethod
    def temporal_dtw(series1, series2):
        """
        Dynamic Time Warping distance.
        Uses fastdtw for efficiency.
        """
        # fastdtw expects 1-D arrays for univariate time series
        # We reshape to (-1, 1) so that fastdtw passes (1,) vectors to euclidean
        # instead of scalars, preventing "Input vector should be 1-D" error.
        s1 = np.array(series1).flatten().reshape(-1, 1)
        s2 = np.array(series2).flatten().reshape(-1, 1)
        print(f"DEBUG DTW: s1 shape={s1.shape}, s2 shape={s2.shape}")
        if len(s1) == 0 or len(s2) == 0:
             print("DEBUG DTW: Empty series found!")
             return 0.0
        distance, path = fastdtw(s1, s2, dist=euclidean)
        return distance

    @staticmethod
    def temporal_acf(series1, series2, lags=None):
        """
        Autocorrelation-based distance.
        Calculates distance between ACF vectors.
        """
        if lags is None:
            lags = min(len(series1), len(series2)) // 2
            
        acf1 = sm.tsa.acf(series1, nlags=lags, fft=True)
        acf2 = sm.tsa.acf(series2, nlags=lags, fft=True)
        
        return euclidean(acf1, acf2)

    @staticmethod
    def temporal_euclidean(series1, series2):
        """Standard Euclidean distance between time series."""
        if len(series1) != len(series2):
            # Truncate to shorter length for simple Euclidean
            min_len = min(len(series1), len(series2))
            series1 = series1[:min_len]
            series2 = series2[:min_len]
            
        return euclidean(series1, series2)
