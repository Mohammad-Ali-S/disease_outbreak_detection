import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
from .distance_metrics import DistanceMetrics
from statsmodels.tsa.holtwinters import ExponentialSmoothing

class OutbreakMiner:
    def __init__(self, hospitals_df, visits_df):
        """
        hospitals_df: DataFrame with ['hospital_key', 'latitude', 'longitude']
        visits_df: DataFrame with ['hospital_key', 'date_key', 'flu_positive_count']
        """
        self.hospitals = hospitals_df
        # Pivot visits to get time series matrix: Rows=Date, Cols=Hospital
        self.time_series = visits_df.pivot(index='date_key', columns='hospital_key', values='flu_positive_count').fillna(0)
        
        # Ensure all hospitals are columns (fill missing with 0)
        all_keys = self.hospitals['hospital_key'].values
        self.time_series = self.time_series.reindex(columns=all_keys, fill_value=0)
        
        # Normalize time series (Zero mean, Unit variance) as per paper
        std = self.time_series.std()
        std = std.fillna(1) # Handle NaNs (e.g. single data point)
        std = std.replace(0, 1) # Avoid division by zero for constant series
        self.normalized_ts = (self.time_series - self.time_series.mean()) / std
        self.normalized_ts = self.normalized_ts.fillna(0) # Handle remaining edge cases

    def predict_hospital_visits(self, hospital_id, horizon=7):
        """
        Predict future visits for a specific hospital using Exponential Smoothing.
        Returns [{'date': 'YYYY-MM-DD', 'predicted': float}]
        """
        try:
            if hospital_id not in self.time_series.columns:
                return []
            
            series = self.time_series[hospital_id]
            # Need at least a few points
            if len(series) < 3:
                 # Fallback: simple average
                 mean_val = series.mean()
                 last_date = series.index[-1]
                 result = []
                 for i in range(1, horizon + 1):
                     next_date = (last_date + pd.Timedelta(days=i)).strftime('%Y-%m-%d')
                     result.append({'date': next_date, 'predicted': max(0, mean_val)})
                 return result

            # Fit Holt-Winters (Exponential Smoothing) with trend
            # Use 'add' trend if possible, fallback to simple if data is sparse
            model = ExponentialSmoothing(series.astype(float), trend='add', seasonal=None).fit()
            forecast = model.forecast(horizon)
            
            result = []
            start_date = series.index[-1]
            for i, val in enumerate(forecast):
                next_date = (start_date + pd.Timedelta(days=i+1)).strftime('%Y-%m-%d')
                result.append({'date': next_date, 'predicted': max(0, round(val, 1))})
                
            return result
        except Exception as e:
            print(f"Prediction Error for {hospital_id}: {e}")
            return []


    def compute_distance_matrix(self, metric='spatial'):
        """
        Compute NxN distance matrix for hospitals.
        Metric: 'spatial', 'dtw', 'cor', 'acf'
        """
        keys = self.hospitals['hospital_key'].values
        n = len(keys)
        dist_matrix = np.zeros((n, n))
        
        # Use simple loops for clarity, optimize later if needed
        for i in range(n):
            for j in range(i + 1, n):
                h1 = keys[i]
                h2 = keys[j]
                
                if metric == 'spatial':
                    row1 = self.hospitals[self.hospitals['hospital_key'] == h1].iloc[0]
                    row2 = self.hospitals[self.hospitals['hospital_key'] == h2].iloc[0]
                    c1 = (row1['latitude'], row1['longitude'])
                    c2 = (row2['latitude'], row2['longitude'])
                    d = DistanceMetrics.spatial_distance(c1, c2)
                else:
                    ts1 = self.normalized_ts[h1].values
                    ts2 = self.normalized_ts[h2].values
                    
                    if metric == 'dtw':
                        d = DistanceMetrics.temporal_dtw(ts1, ts2)
                    elif metric == 'cor':
                        d = DistanceMetrics.temporal_correlation(ts1, ts2)
                    elif metric == 'acf':
                        d = DistanceMetrics.temporal_acf(ts1, ts2)
                    else:
                        d = DistanceMetrics.temporal_euclidean(ts1, ts2)
                
                dist_matrix[i, j] = d
                dist_matrix[j, i] = d
                
        return dist_matrix

    def perform_clustering(self, dist_matrix, threshold=0.05):
        """
        Hierarchical clustering using calculating linkage.
        Returns dictionary mapping cluster_id -> list of hospital_keys.
        """
        # Condensed distance matrix for scipy
        condensed_dist = squareform(dist_matrix)
        
        # Average linkage as implied by paper Eq 1
        Z = linkage(condensed_dist, method='average')
        
        # Cut tree by distance threshold (e.g. 0.05 degrees ~ 5.5km)
        labels = fcluster(Z, t=threshold, criterion='distance')
        
        clusters = {}
        keys = self.hospitals['hospital_key'].values
        for hospital_key, label in zip(keys, labels):
            if int(label) not in clusters:
                clusters[int(label)] = []
            clusters[int(label)].append(int(hospital_key))
            
        return clusters

    def calculate_cluster_series(self, clusters):
        """
        Average time series for each cluster.
        Returns DataFrame with columns=cluster_id
        """
        cluster_series = pd.DataFrame(index=self.normalized_ts.index)
        
        for cid, hospital_keys in clusters.items():
            # Average the normalized series of member hospitals
            cluster_series[cid] = self.normalized_ts[hospital_keys].mean(axis=1)
            
        return cluster_series

    def predict_spread(self, cluster_series, max_lag=14):
        """
        Calculate Direction and Magnitude between clusters.
        Returns a list of 'edges' representing the network.
        """
        clusters = cluster_series.columns
        edges = []
        
        for i in range(len(clusters)):
            for j in range(len(clusters)):
                if i == j: continue
                
                c1 = clusters[i]
                c2 = clusters[j]
                
                s1 = cluster_series[c1]
                s2 = cluster_series[c2]
                
                # Cross Correlation function
                # We want to find lag 'l' where s1(t+l) ~ s2(t)
                # If l > 0, s1 leads s2 (s1 happens first)
                
                corrs = []
                lags = range(-max_lag, max_lag + 1)
                for l in lags:
                    if l < 0:
                        # s1 shifted back
                        c = s1.iloc[:l].corr(s2.iloc[-l:]) # Alignment might be tricky, using numpy cross corr is safer
                    elif l > 0:
                        c = s1.iloc[l:].corr(s2.iloc[:-l])
                    else:
                        c = s1.corr(s2)
                    corrs.append(c if not np.isnan(c) else 0)
                
                # Find optimal lag (Magnitude)
                best_idx = np.argmax(corrs)
                best_lag = lags[best_idx]
                max_corr = corrs[best_idx]
                
                # Equation 17-19 (Momentum) - Simplified logic
                # If best_lag > 0 (s1 needs to be shifted forward to match s2), s2 is AHEAD of s1?
                # Paper: "negative value for m_CC' indicates ... outbreak in C precedes C'"
                # Let's simple use best_lag:
                # If s1.shift(-l) matches s2, it means s1 happened 'l' days ago.
                
                if max_corr > 0.5: # Threshold for significant connection
                     edges.append({
                        'source': int(c1) if best_lag > 0 else int(c2),
                        'target': int(c2) if best_lag > 0 else int(c1),
                        'lag': abs(best_lag),
                        'strength': float(max_corr),
                        'type': 'precedes'
                    })
        
        return edges
