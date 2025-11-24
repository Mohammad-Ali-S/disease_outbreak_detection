"""
Disease Outbreak Detection System (DODS)
Based on: Feature-based Time Series Classification and ML for Outbreak Prediction
Reference: Gao et al. (2025) - PLOS Computational Biology

System Features:
- Multi-disease surveillance (COVID-19, Cholera, HIV/AIDS, Swine Flu)
- Real-time outbreak prediction using ensemble ML models
- Geospatial cluster analysis and visualization
- Time series forecasting with feature extraction
- Administrative and user interfaces
- Data warehousing and ETL pipeline
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import json
import os
from functools import wraps
import io
import warnings
warnings.filterwarnings('ignore')

# ML and Data Processing Libraries
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, IsolationForest
from sklearn.svm import SVC
from sklearn.cluster import DBSCAN, KMeans
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

# Time Series Analysis
from scipy import stats
from scipy.signal import find_peaks

# Initialize Flask App
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///disease_outbreak.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ========================= DATABASE MODELS =========================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')  # admin or user
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Patient(db.Model):
    __tablename__ = 'patients'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    contact = db.Column(db.String(15))
    address = db.Column(db.String(200))
    city = db.Column(db.String(50))
    state = db.Column(db.String(50))
    country = db.Column(db.String(50), default='India')
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    registered_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    disease_records = db.relationship('DiseaseRecord', backref='patient', lazy=True, cascade='all, delete-orphan')


class DiseaseRecord(db.Model):
    __tablename__ = 'disease_records'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    disease_type = db.Column(db.String(50), nullable=False)  # COVID19, Cholera, HIV, SwineFlu
    diagnosis_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='Active')  # Active, Recovered, Deceased
    severity = db.Column(db.String(20))  # Mild, Moderate, Severe, Critical
    
    # Disease-specific data (JSON)
    symptoms = db.Column(db.Text)  # JSON string
    test_results = db.Column(db.Text)  # JSON string
    treatment = db.Column(db.Text)  # JSON string
    notes = db.Column(db.Text)
    
    # Epidemiological data
    travel_history = db.Column(db.Text)  # JSON string
    contact_history = db.Column(db.Text)  # JSON string
    vaccination_status = db.Column(db.String(50))
    
    # Outbreak tracking
    cluster_id = db.Column(db.Integer)  # For spatial clustering
    outbreak_risk_score = db.Column(db.Float)  # ML prediction score
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OutbreakAlert(db.Model):
    __tablename__ = 'outbreak_alerts'
    id = db.Column(db.Integer, primary_key=True)
    disease_type = db.Column(db.String(50), nullable=False)
    alert_level = db.Column(db.String(20))  # Low, Medium, High, Critical
    location = db.Column(db.String(100))
    affected_area = db.Column(db.String(200))
    predicted_cases = db.Column(db.Integer)
    confidence_score = db.Column(db.Float)
    alert_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Active')  # Active, Resolved
    description = db.Column(db.Text)


class DataWarehouse(db.Model):
    __tablename__ = 'data_warehouse'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    disease_type = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(100))
    
    # Aggregated metrics
    total_cases = db.Column(db.Integer, default=0)
    new_cases = db.Column(db.Integer, default=0)
    active_cases = db.Column(db.Integer, default=0)
    recovered_cases = db.Column(db.Integer, default=0)
    death_cases = db.Column(db.Integer, default=0)
    
    # ML features
    growth_rate = db.Column(db.Float)
    reproduction_number = db.Column(db.Float)  # R0
    doubling_time = db.Column(db.Float)
    outbreak_probability = db.Column(db.Float)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ========================= ML MODELS & PROCESSORS =========================

class OutbreakPredictor:
    """
    Ensemble ML model for outbreak prediction
    Based on feature-based time series classification
    """
    
    def __init__(self):
        self.models = {
            'random_forest': RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10),
            'gradient_boost': GradientBoostingClassifier(n_estimators=100, random_state=42, max_depth=5),
            'svm': SVC(kernel='rbf', probability=True, random_state=42, gamma='scale')
        }
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = []
    
    def extract_time_series_features(self, time_series_data):
        """
        Extract statistical features from time series for classification
        """
        if len(time_series_data) < 7:
            return None
        
        # Convert to numpy array
        ts = np.array(time_series_data, dtype=float)
        
        features = {}
        
        # Basic statistics
        features['mean'] = float(np.mean(ts))
        features['std'] = float(np.std(ts))
        features['variance'] = float(np.var(ts))
        features['median'] = float(np.median(ts))
        features['max'] = float(np.max(ts))
        features['min'] = float(np.min(ts))
        features['range'] = features['max'] - features['min']
        
        # Trend features
        x = np.arange(len(ts))
        try:
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, ts)
            features['trend_slope'] = float(slope)
            features['trend_r2'] = float(r_value**2)
        except:
            features['trend_slope'] = 0.0
            features['trend_r2'] = 0.0
        
        # Growth rate
        if features['mean'] > 0:
            recent_mean = np.mean(ts[-3:])
            features['growth_rate'] = float((recent_mean - features['mean']) / features['mean'])
        else:
            features['growth_rate'] = 0.0
        
        # Autocorrelation
        try:
            if len(ts) > 2:
                features['autocorr_lag1'] = float(pd.Series(ts).autocorr(lag=1))
            else:
                features['autocorr_lag1'] = 0.0
        except:
            features['autocorr_lag1'] = 0.0
        
        # Replace NaN with 0
        if np.isnan(features['autocorr_lag1']):
            features['autocorr_lag1'] = 0.0
        
        # Peak detection
        try:
            peaks, _ = find_peaks(ts)
            features['num_peaks'] = int(len(peaks))
        except:
            features['num_peaks'] = 0
        
        # Volatility
        if len(ts) > 1:
            returns = np.diff(ts) / (ts[:-1] + 1e-10)
            features['volatility'] = float(np.std(returns))
        else:
            features['volatility'] = 0.0
        
        # Skewness and Kurtosis
        try:
            features['skewness'] = float(stats.skew(ts))
            features['kurtosis'] = float(stats.kurtosis(ts))
        except:
            features['skewness'] = 0.0
            features['kurtosis'] = 0.0
        
        # Recent acceleration
        if len(ts) >= 5:
            recent = ts[-5:]
            early = ts[:5] if len(ts) >= 10 else ts[:len(ts)//2]
            features['acceleration'] = float(np.mean(recent) - np.mean(early))
        else:
            features['acceleration'] = 0.0
        
        return features
    
    def calculate_reproduction_number(self, cases, generation_time=5):
        """Calculate basic reproduction number (R0)"""
        if len(cases) < generation_time * 2:
            return 1.0
        
        try:
            cases_array = np.array(cases, dtype=float)
            recent_cases = float(np.sum(cases_array[-generation_time:]))
            previous_cases = float(np.sum(cases_array[-2*generation_time:-generation_time]))
            
            if previous_cases > 0:
                return float(recent_cases / previous_cases)
            return 1.0
        except:
            return 1.0
    
    def predict_outbreak_probability(self, disease_type, location, days=14):
        """
        Predict outbreak probability for next 'days' period
        """
        # Get historical data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        
        historical_data = DataWarehouse.query.filter(
            DataWarehouse.disease_type == disease_type,
            DataWarehouse.location == location,
            DataWarehouse.date >= start_date.date(),
            DataWarehouse.date <= end_date.date()
        ).order_by(DataWarehouse.date).all()
        
        if len(historical_data) < 14:
            return {
                'probability': 0.5,
                'confidence': 0.3,
                'alert_level': 'Unknown',
                'predicted_cases': 0,
                'r0': 1.0,
                'growth_rate': 0.0,
                'trend_slope': 0.0
            }
        
        # Extract time series
        cases_series = [float(d.new_cases) for d in historical_data]
        
        # Extract features
        features = self.extract_time_series_features(cases_series)
        if features is None:
            return {
                'probability': 0.5,
                'confidence': 0.3,
                'alert_level': 'Unknown',
                'predicted_cases': 0,
                'r0': 1.0,
                'growth_rate': 0.0,
                'trend_slope': 0.0
            }
        
        # Calculate R0
        r0 = self.calculate_reproduction_number(cases_series)
        features['r0'] = float(r0)
        
        # Rule-based prediction (since we don't have labeled training data initially)
        risk_score = 0.0
        
        # High growth rate
        if features['growth_rate'] > 0.2:
            risk_score += 0.3
        
        # Increasing trend
        if features['trend_slope'] > 0:
            risk_score += 0.2
        
        # High R0
        if r0 > 1.5:
            risk_score += 0.3
        elif r0 > 1.0:
            risk_score += 0.1
        
        # Recent acceleration
        if features['acceleration'] > 0:
            risk_score += 0.2
        
        avg_probability = min(risk_score, 1.0)
        confidence = 0.7
        
        # Determine alert level
        if avg_probability >= 0.8:
            alert_level = 'Critical'
        elif avg_probability >= 0.6:
            alert_level = 'High'
        elif avg_probability >= 0.4:
            alert_level = 'Medium'
        else:
            alert_level = 'Low'
        
        # Predict future cases
        if len(cases_series) >= 7:
            recent_mean = np.mean(cases_series[-7:])
            predicted_cases = int(recent_mean * (1 + features['growth_rate']) * r0)
        else:
            predicted_cases = int(np.mean(cases_series) * 1.1)
        
        predicted_cases = max(0, predicted_cases)
        
        return {
            'probability': round(float(avg_probability), 3),
            'confidence': round(float(confidence), 3),
            'alert_level': alert_level,
            'predicted_cases': predicted_cases,
            'r0': round(float(r0), 2),
            'growth_rate': round(float(features['growth_rate']), 3),
            'trend_slope': round(float(features['trend_slope']), 3)
        }


class SpatialClusterAnalyzer:
    """
    Geospatial clustering for outbreak detection
    Uses DBSCAN for density-based clustering
    """
    
    def __init__(self, eps_km=5, min_samples=3):
        self.eps_km = eps_km
        self.min_samples = min_samples
    
    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points on Earth"""
        R = 6371  # Earth's radius in kilometers
        
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        
        return R * c
    
    def detect_clusters(self, disease_type, days=30):
        """
        Detect spatial clusters of disease cases
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get recent cases with location data
        records = db.session.query(
            DiseaseRecord, Patient
        ).join(
            Patient, DiseaseRecord.patient_id == Patient.id
        ).filter(
            DiseaseRecord.disease_type == disease_type,
            DiseaseRecord.diagnosis_date >= start_date,
            Patient.latitude.isnot(None),
            Patient.longitude.isnot(None)
        ).all()
        
        if len(records) < self.min_samples:
            return {
                'clusters': [],
                'total_clusters': 0,
                'hotspots': [],
                'noise_points': 0
            }
        
        # Extract coordinates
        coords = []
        case_ids = []
        for record, patient in records:
            coords.append([patient.latitude, patient.longitude])
            case_ids.append(record.id)
        
        coords = np.array(coords)
        
        # Convert km to radians for DBSCAN
        eps_rad = self.eps_km / 6371.0
        
        # Perform clustering
        clustering = DBSCAN(
            eps=eps_rad,
            min_samples=self.min_samples,
            metric='haversine'
        ).fit(np.radians(coords))
        
        labels = clustering.labels_
        
        # Analyze clusters
        unique_labels = set(labels)
        clusters = []
        
        for label in unique_labels:
            if label == -1:  # Noise points
                continue
            
            cluster_mask = labels == label
            cluster_coords = coords[cluster_mask]
            cluster_case_ids = [case_ids[i] for i, mask in enumerate(cluster_mask) if mask]
            
            # Calculate cluster center
            center_lat = float(np.mean(cluster_coords[:, 0]))
            center_lon = float(np.mean(cluster_coords[:, 1]))
            
            # Calculate cluster radius
            distances = [
                self.haversine_distance(center_lat, center_lon, lat, lon)
                for lat, lon in cluster_coords
            ]
            max_radius = float(max(distances)) if distances else 0.0
            
            clusters.append({
                'cluster_id': int(label),
                'center': {'lat': center_lat, 'lon': center_lon},
                'radius_km': max_radius,
                'case_count': len(cluster_case_ids),
                'case_ids': cluster_case_ids,
                'risk_level': 'High' if len(cluster_case_ids) > 10 else 'Medium'
            })
        
        # Update cluster IDs in database
        for cluster in clusters:
            for case_id in cluster['case_ids']:
                record = DiseaseRecord.query.get(case_id)
                if record:
                    record.cluster_id = cluster['cluster_id']
        
        db.session.commit()
        
        # Identify hotspots
        hotspots = sorted(clusters, key=lambda x: x['case_count'], reverse=True)[:5]
        
        return {
            'clusters': clusters,
            'total_clusters': len(clusters),
            'hotspots': hotspots,
            'noise_points': int(np.sum(labels == -1))
        }


class DataWarehouseETL:
    """
    Extract, Transform, Load pipeline for data warehousing
    """
    
    def extract_daily_metrics(self, disease_type, location, date):
        """Extract daily metrics for a specific disease and location"""
        
        total = DiseaseRecord.query.join(Patient).filter(
            DiseaseRecord.disease_type == disease_type,
            Patient.city == location,
            db.func.date(DiseaseRecord.diagnosis_date) <= date
        ).count()
        
        new_cases = DiseaseRecord.query.join(Patient).filter(
            DiseaseRecord.disease_type == disease_type,
            Patient.city == location,
            db.func.date(DiseaseRecord.diagnosis_date) == date
        ).count()
        
        active = DiseaseRecord.query.join(Patient).filter(
            DiseaseRecord.disease_type == disease_type,
            Patient.city == location,
            DiseaseRecord.status == 'Active',
            db.func.date(DiseaseRecord.diagnosis_date) <= date
        ).count()
        
        recovered = DiseaseRecord.query.join(Patient).filter(
            DiseaseRecord.disease_type == disease_type,
            Patient.city == location,
            DiseaseRecord.status == 'Recovered',
            db.func.date(DiseaseRecord.diagnosis_date) <= date
        ).count()
        
        deaths = DiseaseRecord.query.join(Patient).filter(
            DiseaseRecord.disease_type == disease_type,
            Patient.city == location,
            DiseaseRecord.status == 'Deceased',
            db.func.date(DiseaseRecord.diagnosis_date) <= date
        ).count()
        
        return {
            'total_cases': total,
            'new_cases': new_cases,
            'active_cases': active,
            'recovered_cases': recovered,
            'death_cases': deaths
        }
    
    def calculate_growth_rate(self, disease_type, location, date, window=7):
        """Calculate growth rate over specified window"""
        
        start_date = date - timedelta(days=window)
        
        current_period = DataWarehouse.query.filter(
            DataWarehouse.disease_type == disease_type,
            DataWarehouse.location == location,
            DataWarehouse.date > date - timedelta(days=window//2),
            DataWarehouse.date <= date
        ).all()
        
        previous_period = DataWarehouse.query.filter(
            DataWarehouse.disease_type == disease_type,
            DataWarehouse.location == location,
            DataWarehouse.date > start_date,
            DataWarehouse.date <= date - timedelta(days=window//2)
        ).all()
        
        current_avg = np.mean([d.new_cases for d in current_period]) if current_period else 0
        previous_avg = np.mean([d.new_cases for d in previous_period]) if previous_period else 0
        
        if previous_avg > 0:
            growth_rate = (current_avg - previous_avg) / previous_avg
        else:
            growth_rate = 0.0
        
        return float(growth_rate)
    
    def run_etl(self, start_date=None, end_date=None):
        """Run full ETL pipeline"""
        
        if start_date is None:
            start_date = datetime.now().date() - timedelta(days=90)
        if end_date is None:
            end_date = datetime.now().date()
        
        # Get unique locations
        locations = db.session.query(Patient.city).distinct().all()
        locations = [loc[0] for loc in locations if loc[0]]
        
        if not locations:
            print("No locations found. Adding sample data...")
            return
        
        diseases = ['COVID19', 'Cholera', 'HIV', 'SwineFlu']
        
        current_date = start_date
        records_added = 0
        
        while current_date <= end_date:
            for disease in diseases:
                for location in locations:
                    # Check if record exists
                    existing = DataWarehouse.query.filter(
                        DataWarehouse.date == current_date,
                        DataWarehouse.disease_type == disease,
                        DataWarehouse.location == location
                    ).first()
                    
                    if existing:
                        continue
                    
                    # Extract metrics
                    metrics = self.extract_daily_metrics(disease, location, current_date)
                    
                    # Calculate growth rate
                    growth_rate = self.calculate_growth_rate(disease, location, current_date)
                    
                    # Create warehouse record
                    warehouse_record = DataWarehouse(
                        date=current_date,
                        disease_type=disease,
                        location=location,
                        total_cases=metrics['total_cases'],
                        new_cases=metrics['new_cases'],
                        active_cases=metrics['active_cases'],
                        recovered_cases=metrics['recovered_cases'],
                        death_cases=metrics['death_cases'],
                        growth_rate=growth_rate
                    )
                    
                    db.session.add(warehouse_record)
                    records_added += 1
            
            current_date += timedelta(days=1)
        
        db.session.commit()
        print(f"ETL pipeline completed: {records_added} records added")
        return records_added


# Initialize ML models globally
outbreak_predictor = OutbreakPredictor()
spatial_analyzer = SpatialClusterAnalyzer()
etl_processor = DataWarehouseETL()

# ========================= HELPER FUNCTIONS =========================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def generate_patient_id():
    """Generate unique patient ID"""
    last_patient = Patient.query.order_by(Patient.id.desc()).first()
    if last_patient:
        last_num = int(last_patient.patient_id.split('_')[1])
        return f"PAT_{last_num + 1:06d}"
    return "PAT_000001"

def geocode_address(city, state, country):
    """
    Simple geocoding for Indian cities
    """
    city_coords = {
        'Pune': (18.5204, 73.8567),
        'Mumbai': (19.0760, 72.8777),
        'Delhi': (28.7041, 77.1025),
        'Bangalore': (12.9716, 77.5946),
        'Hyderabad': (17.3850, 78.4867),
        'Chennai': (13.0827, 80.2707),
        'Kolkata': (22.5726, 88.3639),
        'Ahmedabad': (23.0225, 72.5714),
        'Jaipur': (26.9124, 75.7873),
        'Lucknow': (26.8467, 80.9462),
        'Nagpur': (21.1458, 79.0882),
        'Indore': (22.7196, 75.8577),
        'Patna': (25.5941, 85.1376),
        'Bhopal': (23.2599, 77.4126)
    }
    
    return city_coords.get(city, (20.5937, 78.9629))


# ========================= ROUTES - AUTHENTICATION =========================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        user = User.query.filter_by(username=data['username']).first()
        
        if user and user.check_password(data['password']):
            login_user(user)
            return jsonify({
                'success': True,
                'role': user.role,
                'redirect': '/admin/dashboard' if user.role == 'admin' else '/user/dashboard'
            })
        
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'success': False, 'message': 'Username already exists'}), 400
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'success': False, 'message': 'Email already exists'}), 400
        
        user = User(
            username=data['username'],
            email=data['email'],
            role=data.get('role', 'user')
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Registration successful'})
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# ========================= ROUTES - ADMIN PANEL =========================

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    total_patients = Patient.query.count()
    total_cases = DiseaseRecord.query.count()
    active_alerts = OutbreakAlert.query.filter_by(status='Active').count()
    
    disease_stats = db.session.query(
        DiseaseRecord.disease_type,
        db.func.count(DiseaseRecord.id).label('count')
    ).group_by(DiseaseRecord.disease_type).all()
    
    stats = {
        'total_patients': total_patients,
        'total_cases': total_cases,
        'active_alerts': active_alerts,
        'disease_breakdown': {d[0]: d[1] for d in disease_stats}
    }
    
    return render_template('admin_dashboard.html', stats=stats)


@app.route('/admin/patients')
@login_required
@admin_required
def admin_patients():
    patients = Patient.query.order_by(Patient.registered_date.desc()).all()
    return render_template('admin_patients.html', patients=patients)


@app.route('/admin/analytics')
@login_required
@admin_required
def admin_analytics():
    return render_template('admin_analytics.html')


@app.route('/admin/alerts')
@login_required
@admin_required
def admin_alerts():
    alerts = OutbreakAlert.query.order_by(OutbreakAlert.alert_date.desc()).all()
    return render_template('admin_alerts.html', alerts=alerts)


@app.route('/user/analytics')
@login_required
def user_analytics():
    """User can view analytics"""
    return render_template('admin_analytics.html')


@app.route('/user/reports')
@login_required
def user_reports():
    """User can view their submitted reports"""
    # Get all disease records
    recent_cases = DiseaseRecord.query.order_by(
        DiseaseRecord.diagnosis_date.desc()
    ).limit(50).all()
    
    return render_template('user_dashboard.html', recent_cases=recent_cases)


@app.route('/admin/bulk-import', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_bulk_import():
    """Bulk import patients from CSV"""
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                return jsonify({'success': False, 'message': 'No file uploaded'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'message': 'No file selected'}), 400
            
            if not file.filename.endswith('.csv'):
                return jsonify({'success': False, 'message': 'Only CSV files are allowed'}), 400
            
            # Read CSV
            df = pd.read_csv(file)
            
            patients_added = 0
            records_added = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    # Check if patient exists
                    patient_id = row.get('patient_id', f'PAT_{index+1:06d}')
                    existing_patient = Patient.query.filter_by(patient_id=patient_id).first()
                    
                    if not existing_patient:
                        # Create new patient
                        patient = Patient(
                            patient_id=patient_id,
                            name=str(row['name']),
                            age=int(row['age']),
                            gender=str(row['gender']),
                            contact=str(row.get('contact', '')),
                            address=str(row.get('address', '')),
                            city=str(row['city']),
                            state=str(row['state']),
                            country=str(row.get('country', 'India')),
                            latitude=float(row['latitude']),
                            longitude=float(row['longitude'])
                        )
                        db.session.add(patient)
                        db.session.flush()
                        patients_added += 1
                    else:
                        patient = existing_patient
                    
                    # Create disease record
                    disease_record = DiseaseRecord(
                        patient_id=patient.id,
                        disease_type=str(row['disease_type']),
                        diagnosis_date=datetime.strptime(str(row['diagnosis_date']), '%Y-%m-%d'),
                        status=str(row.get('status', 'Active')),
                        severity=str(row.get('severity', 'Moderate')),
                        symptoms=json.dumps({'imported': True, 'data': str(row.get('symptoms', ''))}),
                        test_results=json.dumps({k: str(v) for k, v in row.items() if 'test' in k.lower() or k in ['cd4_count', 'viral_load', 'ct_value', 'oxygen_saturation']}),
                        vaccination_status=str(row.get('vaccination_status', row.get('flu_vaccine', ''))),
                        notes=f"Bulk imported on {datetime.now().strftime('%Y-%m-%d')}"
                    )
                    
                    db.session.add(disease_record)
                    records_added += 1
                    
                    # Commit every 100 records
                    if (index + 1) % 100 == 0:
                        db.session.commit()
                        
                except Exception as e:
                    errors.append(f"Row {index + 1}: {str(e)}")
                    continue
            
            db.session.commit()
            
            # Run ETL after import
            etl_processor.run_etl()
            
            return jsonify({
                'success': True,
                'message': f'Import completed!',
                'patients_added': patients_added,
                'records_added': records_added,
                'errors': errors[:10]  # Show first 10 errors only
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
    
    return render_template('admin_bulk_import.html')


@app.route('/admin/train-model', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_train_model():
    """Train ML models on uploaded data"""
    if request.method == 'POST':
        try:
            disease_type = request.form.get('disease_type')
            
            # Get training data from warehouse
            training_data = DataWarehouse.query.filter_by(disease_type=disease_type).all()
            
            if len(training_data) < 50:
                return jsonify({'success': False, 'message': 'Insufficient data for training (minimum 50 records required)'}), 400
            
            # Extract features
            X = []
            y = []
            
            for record in training_data:
                features = {
                    'new_cases': record.new_cases,
                    'active_cases': record.active_cases,
                    'growth_rate': record.growth_rate or 0,
                    'total_cases': record.total_cases
                }
                
                # Label: 1 if outbreak (high growth), 0 otherwise
                label = 1 if (record.growth_rate or 0) > 0.15 else 0
                
                X.append(list(features.values()))
                y.append(label)
            
            X = np.array(X)
            y = np.array(y)
            
            # Train models
            X_scaled = outbreak_predictor.scaler.fit_transform(X)
            
            results = {}
            for model_name, model in outbreak_predictor.models.items():
                try:
                    model.fit(X_scaled, y)
                    accuracy = model.score(X_scaled, y)
                    results[model_name] = round(accuracy * 100, 2)
                except:
                    results[model_name] = 0
            
            outbreak_predictor.is_trained = True
            
            return jsonify({
                'success': True,
                'message': 'Models trained successfully!',
                'results': results,
                'training_samples': len(X)
            })
            
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
    
    return render_template('admin_train_model.html')


@app.route('/admin/data-warehouse')
@login_required
@admin_required
def admin_warehouse():
    return render_template('admin_warehouse.html')


# ========================= ROUTES - USER PANEL =========================

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    recent_cases = DiseaseRecord.query.order_by(
        DiseaseRecord.diagnosis_date.desc()
    ).limit(10).all()
    
    return render_template('user_dashboard.html', recent_cases=recent_cases)


@app.route('/user/add-patient', methods=['GET', 'POST'])
@login_required
def add_patient():
    if request.method == 'POST':
        data = request.get_json()
        
        patient_id = generate_patient_id()
        lat, lon = geocode_address(data['city'], data['state'], data.get('country', 'India'))
        
        patient = Patient(
            patient_id=patient_id,
            name=data['name'],
            age=data['age'],
            gender=data['gender'],
            contact=data.get('contact'),
            address=data.get('address'),
            city=data['city'],
            state=data['state'],
            country=data.get('country', 'India'),
            latitude=lat,
            longitude=lon
        )
        
        db.session.add(patient)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'patient_id': patient_id,
            'id': patient.id
        })
    
    return render_template('add_patient.html')


@app.route('/user/add-disease-record/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def add_disease_record(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    if request.method == 'POST':
        data = request.get_json()
        
        disease_record = DiseaseRecord(
            patient_id=patient.id,
            disease_type=data['disease_type'],
            diagnosis_date=datetime.strptime(data['diagnosis_date'], '%Y-%m-%d'),
            status=data.get('status', 'Active'),
            severity=data.get('severity'),
            symptoms=json.dumps(data.get('symptoms', {})),
            test_results=json.dumps(data.get('test_results', {})),
            treatment=json.dumps(data.get('treatment', {})),
            notes=data.get('notes'),
            travel_history=json.dumps(data.get('travel_history', {})),
            contact_history=json.dumps(data.get('contact_history', {})),
            vaccination_status=data.get('vaccination_status')
        )
        
        db.session.add(disease_record)
        db.session.commit()
        
        # Run outbreak prediction
        prediction = outbreak_predictor.predict_outbreak_probability(
            data['disease_type'],
            patient.city
        )
        
        disease_record.outbreak_risk_score = prediction['probability']
        db.session.commit()
        
        # Check if alert should be created
        if prediction['alert_level'] in ['High', 'Critical']:
            alert = OutbreakAlert(
                disease_type=data['disease_type'],
                alert_level=prediction['alert_level'],
                location=patient.city,
                affected_area=f"{patient.city}, {patient.state}",
                predicted_cases=prediction['predicted_cases'],
                confidence_score=prediction['confidence'],
                description=f"Outbreak risk detected: {prediction['alert_level']} probability"
            )
            db.session.add(alert)
            db.session.commit()
        
        return jsonify({
            'success': True,
            'record_id': disease_record.id,
            'risk_prediction': prediction
        })
    
    return render_template('add_disease_record.html', patient=patient)


@app.route('/user/disease-forms/<disease_type>')
@login_required
def disease_form(disease_type):
    # Get patient_id from query parameter or session
    patient_id = request.args.get('patient_id')
    
    if not patient_id:
        # Try to get from session
        patient_id = session.get('current_patient_id')
    
    if not patient_id:
        # Redirect back to add patient page
        return redirect(url_for('add_patient'))
    
    # Store in session for form submission
    session['current_patient_id'] = patient_id
    
    # Verify patient exists
    patient = Patient.query.get(patient_id)
    if not patient:
        return redirect(url_for('add_patient'))
    
    return render_template(f'forms/{disease_type.lower()}_form.html', patient=patient)


# ========================= API ROUTES - DATA & ANALYTICS =========================

@app.route('/api/dashboard-stats')
@login_required
def api_dashboard_stats():
    """Get real-time dashboard statistics"""
    
    try:
        total_patients = Patient.query.count()
        total_cases = DiseaseRecord.query.count()
        active_cases = DiseaseRecord.query.filter_by(status='Active').count()
        
        # Get disease statistics with proper handling
        disease_breakdown = []
        diseases = ['COVID19', 'Cholera', 'HIV', 'SwineFlu']
        
        for disease in diseases:
            total = DiseaseRecord.query.filter_by(disease_type=disease).count()
            if total > 0:  # Only include diseases with cases
                active = DiseaseRecord.query.filter_by(
                    disease_type=disease, 
                    status='Active'
                ).count()
                
                recovered = DiseaseRecord.query.filter_by(
                    disease_type=disease, 
                    status='Recovered'
                ).count()
                
                deaths = DiseaseRecord.query.filter_by(
                    disease_type=disease, 
                    status='Deceased'
                ).count()
                
                disease_breakdown.append({
                    'disease': disease,
                    'total': total,
                    'active': active,
                    'recovered': recovered,
                    'deaths': deaths
                })
        
        # Recent trends (last 30 days)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        # Get all cases in date range
        cases_by_date = {}
        all_cases = DiseaseRecord.query.filter(
            DiseaseRecord.diagnosis_date >= thirty_days_ago
        ).all()
        
        for case in all_cases:
            date_key = case.diagnosis_date.date().strftime('%Y-%m-%d')
            cases_by_date[date_key] = cases_by_date.get(date_key, 0) + 1
        
        # Convert to sorted list
        trend_data = [
            {'date': date, 'count': count} 
            for date, count in sorted(cases_by_date.items())
        ]
        
        return jsonify({
            'total_patients': total_patients,
            'total_cases': total_cases,
            'active_cases': active_cases,
            'disease_breakdown': disease_breakdown,
            'trend_data': trend_data
        })
        
    except Exception as e:
        print(f"Error in dashboard stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'total_patients': 0,
            'total_cases': 0,
            'active_cases': 0,
            'disease_breakdown': [],
            'trend_data': []
        }), 200  # Return 200 with error info instead of 500


@app.route('/api/geospatial-data/<disease_type>')
@login_required
def api_geospatial_data(disease_type):
    """Get geospatial data for mapping with detailed patient info"""
    
    days = request.args.get('days', 30, type=int)
    start_date = datetime.now() - timedelta(days=days)
    
    cases = db.session.query(
        Patient.id.label('patient_id'),
        Patient.patient_id.label('patient_code'),
        Patient.name,
        Patient.latitude,
        Patient.longitude,
        Patient.city,
        Patient.state,
        Patient.age,
        Patient.gender,
        DiseaseRecord.id.label('record_id'),
        DiseaseRecord.diagnosis_date,
        DiseaseRecord.severity,
        DiseaseRecord.status,
        DiseaseRecord.cluster_id,
        DiseaseRecord.outbreak_risk_score
    ).join(
        DiseaseRecord, Patient.id == DiseaseRecord.patient_id
    ).filter(
        DiseaseRecord.disease_type == disease_type,
        DiseaseRecord.diagnosis_date >= start_date,
        Patient.latitude.isnot(None)
    ).all()
    
    markers = []
    for case in cases:
        markers.append({
            'patient_id': case.patient_id,
            'patient_code': case.patient_code,
            'name': case.name,
            'age': case.age,
            'gender': case.gender,
            'lat': case.latitude,
            'lng': case.longitude,
            'city': case.city,
            'state': case.state,
            'date': case.diagnosis_date.strftime('%Y-%m-%d'),
            'severity': case.severity,
            'status': case.status,
            'cluster_id': case.cluster_id,
            'risk_score': round(case.outbreak_risk_score * 100, 1) if case.outbreak_risk_score else None
        })
    
    clusters = spatial_analyzer.detect_clusters(disease_type, days)
    
    return jsonify({
        'markers': markers,
        'clusters': clusters['clusters'],
        'hotspots': clusters['hotspots'],
        'total_cases': len(markers)
    })


@app.route('/api/time-series/<disease_type>')
@login_required
def api_time_series(disease_type):
    """Get time series data for visualization"""
    
    days = request.args.get('days', 90, type=int)
    location = request.args.get('location', None)
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    query = DataWarehouse.query.filter(
        DataWarehouse.disease_type == disease_type,
        DataWarehouse.date >= start_date,
        DataWarehouse.date <= end_date
    )
    
    if location:
        query = query.filter(DataWarehouse.location == location)
    
    data = query.order_by(DataWarehouse.date).all()
    
    if not location:
        date_aggregates = {}
        for record in data:
            date_str = str(record.date)
            if date_str not in date_aggregates:
                date_aggregates[date_str] = {
                    'date': date_str,
                    'total_cases': 0,
                    'new_cases': 0,
                    'active_cases': 0,
                    'recovered_cases': 0,
                    'death_cases': 0
                }
            
            date_aggregates[date_str]['total_cases'] += record.total_cases
            date_aggregates[date_str]['new_cases'] += record.new_cases
            date_aggregates[date_str]['active_cases'] += record.active_cases
            date_aggregates[date_str]['recovered_cases'] += record.recovered_cases
            date_aggregates[date_str]['death_cases'] += record.death_cases
        
        time_series = list(date_aggregates.values())
    else:
        time_series = [{
            'date': str(record.date),
            'total_cases': record.total_cases,
            'new_cases': record.new_cases,
            'active_cases': record.active_cases,
            'recovered_cases': record.recovered_cases,
            'death_cases': record.death_cases,
            'growth_rate': record.growth_rate,
            'r0': record.reproduction_number
        } for record in data]
    
    return jsonify({
        'disease_type': disease_type,
        'location': location,
        'time_series': time_series
    })


@app.route('/api/outbreak-prediction/<disease_type>')
@login_required
def api_outbreak_prediction(disease_type):
    """Get outbreak predictions for a disease"""
    
    location = request.args.get('location', None)
    
    if not location:
        locations = db.session.query(Patient.city).distinct().all()
        predictions = []
        
        for loc in locations:
            if loc[0]:
                pred = outbreak_predictor.predict_outbreak_probability(
                    disease_type, loc[0]
                )
                pred['location'] = loc[0]
                predictions.append(pred)
        
        predictions.sort(key=lambda x: x['probability'], reverse=True)
        
        return jsonify({
            'disease_type': disease_type,
            'predictions': predictions
        })
    else:
        prediction = outbreak_predictor.predict_outbreak_probability(
            disease_type, location
        )
        prediction['location'] = location
        
        return jsonify({
            'disease_type': disease_type,
            'prediction': prediction
        })


@app.route('/api/frequency-analysis/<disease_type>')
@login_required
def api_frequency_analysis(disease_type):
    """Analyze disease frequency patterns"""
    
    days = request.args.get('days', 90, type=int)
    start_date = datetime.now() - timedelta(days=days)
    
    daily_freq = db.session.query(
        db.func.date(DiseaseRecord.diagnosis_date).label('date'),
        db.func.count(DiseaseRecord.id).label('count')
    ).filter(
        DiseaseRecord.disease_type == disease_type,
        DiseaseRecord.diagnosis_date >= start_date
    ).group_by(db.func.date(DiseaseRecord.diagnosis_date)).all()
    
    age_dist = db.session.query(
        db.case(
            (Patient.age < 18, '0-17'),
            (Patient.age < 35, '18-34'),
            (Patient.age < 50, '35-49'),
            (Patient.age < 65, '50-64'),
            else_='65+'
        ).label('age_group'),
        db.func.count(DiseaseRecord.id).label('count')
    ).join(
        Patient, DiseaseRecord.patient_id == Patient.id
    ).filter(
        DiseaseRecord.disease_type == disease_type
    ).group_by('age_group').all()
    
    gender_dist = db.session.query(
        Patient.gender,
        db.func.count(DiseaseRecord.id).label('count')
    ).join(
        Patient, DiseaseRecord.patient_id == Patient.id
    ).filter(
        DiseaseRecord.disease_type == disease_type
    ).group_by(Patient.gender).all()
    
    severity_dist = db.session.query(
        DiseaseRecord.severity,
        db.func.count(DiseaseRecord.id).label('count')
    ).filter(
        DiseaseRecord.disease_type == disease_type,
        DiseaseRecord.severity.isnot(None)
    ).group_by(DiseaseRecord.severity).all()
    
    location_freq = db.session.query(
        Patient.city,
        db.func.count(DiseaseRecord.id).label('count')
    ).join(
        Patient, DiseaseRecord.patient_id == Patient.id
    ).filter(
        DiseaseRecord.disease_type == disease_type
    ).group_by(Patient.city).order_by(db.desc('count')).limit(10).all()
    
    return jsonify({
        'daily_frequency': [{'date': str(d[0]), 'count': d[1]} for d in daily_freq],
        'age_distribution': [{'age_group': a[0], 'count': a[1]} for a in age_dist],
        'gender_distribution': [{'gender': g[0], 'count': g[1]} for g in gender_dist],
        'severity_distribution': [{'severity': s[0], 'count': s[1]} for s in severity_dist],
        'location_hotspots': [{'city': l[0], 'count': l[1]} for l in location_freq]
    })


@app.route('/api/cluster-analysis/<disease_type>')
@login_required
def api_cluster_analysis(disease_type):
    """Get detailed cluster analysis"""
    
    days = request.args.get('days', 30, type=int)
    clusters = spatial_analyzer.detect_clusters(disease_type, days)
    
    detailed_clusters = []
    for cluster in clusters['clusters']:
        case_records = DiseaseRecord.query.filter(
            DiseaseRecord.id.in_(cluster['case_ids'])
        ).all()
        
        severities = [r.severity for r in case_records if r.severity]
        statuses = [r.status for r in case_records]
        
        cluster_detail = {
            'cluster_id': cluster['cluster_id'],
            'center': cluster['center'],
            'radius_km': cluster['radius_km'],
            'case_count': cluster['case_count'],
            'risk_level': cluster['risk_level'],
            'severity_breakdown': {
                'Mild': severities.count('Mild'),
                'Moderate': severities.count('Moderate'),
                'Severe': severities.count('Severe'),
                'Critical': severities.count('Critical')
            },
            'status_breakdown': {
                'Active': statuses.count('Active'),
                'Recovered': statuses.count('Recovered'),
                'Deceased': statuses.count('Deceased')
            }
        }
        
        detailed_clusters.append(cluster_detail)
    
    return jsonify({
        'disease_type': disease_type,
        'total_clusters': clusters['total_clusters'],
        'clusters': detailed_clusters,
        'hotspots': clusters['hotspots']
    })


@app.route('/api/data-warehouse/run-etl', methods=['POST'])
@login_required
@admin_required
def api_run_etl():
    """Run ETL pipeline to update data warehouse"""
    
    try:
        data = request.get_json() or {}
        start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d').date() if data.get('start_date') else None
        end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d').date() if data.get('end_date') else None
        
        records_added = etl_processor.run_etl(start_date, end_date)
        
        return jsonify({
            'success': True,
            'message': f'ETL pipeline completed successfully. {records_added} records processed.'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/data-warehouse/summary')
@login_required
@admin_required
def api_warehouse_summary():
    """Get data warehouse summary statistics"""
    
    total_records = DataWarehouse.query.count()
    
    date_range = db.session.query(
        db.func.min(DataWarehouse.date).label('min_date'),
        db.func.max(DataWarehouse.date).label('max_date')
    ).first()
    
    disease_counts = db.session.query(
        DataWarehouse.disease_type,
        db.func.count(DataWarehouse.id).label('count')
    ).group_by(DataWarehouse.disease_type).all()
    
    location_counts = db.session.query(
        DataWarehouse.location,
        db.func.count(DataWarehouse.id).label('count')
    ).group_by(DataWarehouse.location).all()
    
    return jsonify({
        'total_records': total_records,
        'date_range': {
            'start': str(date_range[0]) if date_range[0] else None,
            'end': str(date_range[1]) if date_range[1] else None
        },
        'disease_counts': {d[0]: d[1] for d in disease_counts},
        'location_counts': {l[0]: l[1] for l in location_counts}
    })


@app.route('/api/ml-insights/<disease_type>')
@login_required
def api_ml_insights(disease_type):
    """Get ML-powered insights for a disease"""
    
    location = request.args.get('location', None)
    
    insights = {
        'disease_type': disease_type,
        'location': location,
        'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    if location:
        prediction = outbreak_predictor.predict_outbreak_probability(disease_type, location)
        insights['outbreak_prediction'] = prediction
    
    clusters = spatial_analyzer.detect_clusters(disease_type, 30)
    insights['cluster_analysis'] = {
        'total_clusters': clusters['total_clusters'],
        'top_hotspots': clusters['hotspots'][:3]
    }
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=60)
    
    ts_data = DataWarehouse.query.filter(
        DataWarehouse.disease_type == disease_type,
        DataWarehouse.date >= start_date
    )
    
    if location:
        ts_data = ts_data.filter(DataWarehouse.location == location)
    
    ts_data = ts_data.order_by(DataWarehouse.date).all()
    
    if len(ts_data) >= 14:
        cases_series = [d.new_cases for d in ts_data]
        features = outbreak_predictor.extract_time_series_features(cases_series)
        
        if features:
            insights['time_series_patterns'] = {
                'trend': 'Increasing' if features['trend_slope'] > 0 else 'Decreasing',
                'volatility': 'High' if features['volatility'] > 0.5 else 'Moderate' if features['volatility'] > 0.2 else 'Low',
                'growth_rate': round(features['growth_rate'] * 100, 2),
                'peaks_detected': features['num_peaks']
            }
    
    if location and ts_data:
        recent_r0 = outbreak_predictor.calculate_reproduction_number([d.new_cases for d in ts_data])
        
        risk_level = 'Low'
        if recent_r0 > 2.0:
            risk_level = 'Critical'
        elif recent_r0 > 1.5:
            risk_level = 'High'
        elif recent_r0 > 1.0:
            risk_level = 'Moderate'
        
        insights['risk_assessment'] = {
            'reproduction_number': round(recent_r0, 2),
            'risk_level': risk_level,
            'recommendation': 'Immediate intervention required' if risk_level in ['Critical', 'High'] else 'Continue monitoring'
        }
    
    return jsonify(insights)


@app.route('/api/patient-details/<int:patient_id>')
@login_required
def api_patient_details(patient_id):
    """Get detailed patient information with disease records"""
    
    try:
        patient = Patient.query.get(patient_id)
        
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        
        disease_records = []
        for record in patient.disease_records:
            disease_records.append({
                'id': record.id,
                'disease_type': record.disease_type,
                'diagnosis_date': record.diagnosis_date.strftime('%Y-%m-%d'),
                'status': record.status,
                'severity': record.severity,
                'risk_score': record.outbreak_risk_score,
                'cluster_id': record.cluster_id
            })
        
        return jsonify({
            'patient_id': patient.patient_id,
            'name': patient.name,
            'age': patient.age,
            'gender': patient.gender,
            'contact': patient.contact,
            'address': patient.address,
            'city': patient.city,
            'state': patient.state,
            'country': patient.country,
            'latitude': patient.latitude,
            'longitude': patient.longitude,
            'registered_date': patient.registered_date.strftime('%Y-%m-%d'),
            'disease_records': disease_records
        })
        
    except Exception as e:
        print(f"Error getting patient details: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete-patient/<int:patient_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_patient(patient_id):
    """Delete a patient and all associated records"""
    
    try:
        patient = Patient.query.get(patient_id)
        
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        
        # Delete patient (cascade will delete disease records)
        db.session.delete(patient)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Patient {patient.patient_id} deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting patient: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/export-data/<format>')
@login_required
@admin_required
def api_export_data(format):
    """Export data in various formats"""
    
    disease_type = request.args.get('disease_type', None)
    start_date = request.args.get('start_date', None)
    end_date = request.args.get('end_date', None)
    
    query = db.session.query(DiseaseRecord, Patient).join(Patient)
    
    if disease_type:
        query = query.filter(DiseaseRecord.disease_type == disease_type)
    if start_date:
        query = query.filter(DiseaseRecord.diagnosis_date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(DiseaseRecord.diagnosis_date <= datetime.strptime(end_date, '%Y-%m-%d'))
    
    records = query.all()
    
    data = []
    for record, patient in records:
        data.append({
            'Patient ID': patient.patient_id,
            'Name': patient.name,
            'Age': patient.age,
            'Gender': patient.gender,
            'City': patient.city,
            'State': patient.state,
            'Disease': record.disease_type,
            'Diagnosis Date': record.diagnosis_date.strftime('%Y-%m-%d'),
            'Status': record.status,
            'Severity': record.severity,
            'Cluster ID': record.cluster_id,
            'Risk Score': record.outbreak_risk_score
        })
    
    df = pd.DataFrame(data)
    
    if format == 'csv':
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'disease_data_{datetime.now().strftime("%Y%m%d")}.csv'
        )
    
    elif format == 'json':
        return jsonify(data)
    
    else:
        return jsonify({'error': 'Unsupported format'}), 400


# ========================= DATABASE INITIALIZATION =========================

def create_sample_data():
    """Create sample data for demonstration"""
    
    # Sample cities for data generation
    cities = ['Pune', 'Mumbai', 'Delhi', 'Bangalore', 'Hyderabad']
    diseases = ['COVID19', 'Cholera', 'HIV', 'SwineFlu']
    
    # Create sample patients
    for i in range(20):
        city = np.random.choice(cities)
        lat, lon = geocode_address(city, 'Maharashtra', 'India')
        
        patient = Patient(
            patient_id=f"PAT_{i+1:06d}",
            name=f"Patient {i+1}",
            age=np.random.randint(1, 80),
            gender=np.random.choice(['Male', 'Female']),
            contact=f"98765{i+1:05d}",
            address=f"Address {i+1}",
            city=city,
            state='Maharashtra',
            country='India',
            latitude=lat + np.random.uniform(-0.1, 0.1),
            longitude=lon + np.random.uniform(-0.1, 0.1),
            registered_date=datetime.now() - timedelta(days=np.random.randint(1, 90))
        )
        db.session.add(patient)
    
    db.session.commit()
    
    # Create sample disease records
    patients = Patient.query.all()
    for patient in patients[:15]:  # Create records for first 15 patients
        disease = np.random.choice(diseases)
        
        record = DiseaseRecord(
            patient_id=patient.id,
            disease_type=disease,
            diagnosis_date=datetime.now() - timedelta(days=np.random.randint(1, 60)),
            status=np.random.choice(['Active', 'Recovered', 'Deceased'], p=[0.6, 0.35, 0.05]),
            severity=np.random.choice(['Mild', 'Moderate', 'Severe', 'Critical'], p=[0.4, 0.3, 0.2, 0.1]),
            symptoms=json.dumps({'fever': True, 'cough': True}),
            test_results=json.dumps({'result': 'Positive'}),
            vaccination_status='Vaccinated'
        )
        db.session.add(record)
    
    db.session.commit()
    print("Sample data created successfully!")


def init_database():
    """Initialize database with default data"""
    
    with app.app_context():
        db.create_all()
        
        # Create admin user if doesn't exist
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@dods.com',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
        
        # Create regular user
        user = User.query.filter_by(username='user').first()
        if not user:
            user = User(
                username='user',
                email='user@dods.com',
                role='user'
            )
            user.set_password('user123')
            db.session.add(user)
        
        db.session.commit()
        
        # Create sample data if no patients exist
        if Patient.query.count() == 0:
            print("Creating sample data...")
            create_sample_data()
            
            # Run ETL to populate warehouse
            print("Running initial ETL...")
            etl_processor.run_etl()
        
        print("Database initialized successfully!")
        print("\nDefault credentials:")
        print("Admin: admin / admin123")
        print("User: user / user123")


# ========================= MAIN =========================

if __name__ == '__main__':
    init_database()
    print("\nStarting Disease Outbreak Detection System...")
    print("Access the application at: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)