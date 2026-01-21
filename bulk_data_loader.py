# bulk_data_loader.py - Bulk Import System for Hospital Data

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import json

class DummyDatasetGenerator:
    """
    Generate realistic dummy datasets for disease surveillance
    Compatible with hospital data formats
    """
    
    def __init__(self):
        self.indian_cities = [
            ('Mumbai', 'Maharashtra', 19.0760, 72.8777),
            ('Delhi', 'Delhi', 28.7041, 77.1025),
            ('Bangalore', 'Karnataka', 12.9716, 77.5946),
            ('Hyderabad', 'Telangana', 17.3850, 78.4867),
            ('Chennai', 'Tamil Nadu', 13.0827, 80.2707),
            ('Kolkata', 'West Bengal', 22.5726, 88.3639),
            ('Pune', 'Maharashtra', 18.5204, 73.8567),
            ('Ahmedabad', 'Gujarat', 23.0225, 72.5714),
            ('Jaipur', 'Rajasthan', 26.9124, 75.7873),
            ('Lucknow', 'Uttar Pradesh', 26.8467, 80.9462),
            ('Surat', 'Gujarat', 21.1702, 72.8311),
            ('Kanpur', 'Uttar Pradesh', 26.4499, 80.3319),
            ('Nagpur', 'Maharashtra', 21.1458, 79.0882),
            ('Indore', 'Madhya Pradesh', 22.7196, 75.8577),
            ('Patna', 'Bihar', 25.5941, 85.1376),
            ('Bhopal', 'Madhya Pradesh', 23.2599, 77.4126),
            ('Ludhiana', 'Punjab', 30.9010, 75.8573),
            ('Agra', 'Uttar Pradesh', 27.1767, 78.0081),
            ('Vadodara', 'Gujarat', 22.3072, 73.1812),
            ('Coimbatore', 'Tamil Nadu', 11.0168, 76.9558)
        ]
        
        self.first_names = ['Aarav', 'Vivaan', 'Aditya', 'Vihaan', 'Arjun', 'Sai', 'Arnav', 'Ayaan', 
                           'Krishna', 'Ishaan', 'Priya', 'Ananya', 'Aanya', 'Diya', 'Aarohi', 'Sara',
                           'Pari', 'Kavya', 'Myra', 'Riya', 'Rajesh', 'Amit', 'Suresh', 'Vijay', 
                           'Ramesh', 'Deepak', 'Manoj', 'Santosh', 'Prakash', 'Ashok', 'Sunita',
                           'Kavita', 'Meera', 'Pooja', 'Rekha', 'Shalini', 'Vandana', 'Neha']
        
        self.last_names = ['Kumar', 'Sharma', 'Singh', 'Patel', 'Gupta', 'Reddy', 'Verma', 'Joshi',
                          'Rao', 'Nair', 'Iyer', 'Menon', 'Desai', 'Shah', 'Mehta', 'Agarwal',
                          'Jain', 'Bhat', 'Malhotra', 'Chopra']
    
    def generate_covid19_dataset(self, num_records=10000):
        """Generate COVID-19 patient dataset"""
        
        data = []
        start_date = datetime.now() - timedelta(days=365)
        
        for i in range(num_records):
            city_data = random.choice(self.indian_cities)
            city, state, base_lat, base_lon = city_data
            
            # Add random variation to coordinates (within 0.5 degrees ~50km)
            lat = base_lat + random.uniform(-0.5, 0.5)
            lon = base_lon + random.uniform(-0.5, 0.5)
            
            # Generate realistic date (more recent = more cases)
            days_ago = int(np.random.exponential(90))  # Exponential distribution
            diagnosis_date = start_date + timedelta(days=days_ago)
            
            # Age distribution (COVID affects all ages)
            age = int(np.random.beta(2, 5) * 100)  # Skewed towards younger
            
            # Vaccination reduces severity
            vaccination = random.choices(
                ['Unvaccinated', 'Partially Vaccinated', 'Fully Vaccinated', 'Booster'],
                weights=[0.2, 0.15, 0.45, 0.2]
            )[0]
            
            # Severity based on age and vaccination
            if vaccination in ['Fully Vaccinated', 'Booster']:
                severity = random.choices(
                    ['Mild', 'Moderate', 'Severe', 'Critical'],
                    weights=[0.7, 0.2, 0.08, 0.02]
                )[0]
            else:
                severity = random.choices(
                    ['Mild', 'Moderate', 'Severe', 'Critical'],
                    weights=[0.4, 0.35, 0.2, 0.05]
                )[0]
            
            # Status based on severity
            if severity == 'Critical':
                status = random.choices(['Active', 'Recovered', 'Deceased'], weights=[0.4, 0.4, 0.2])[0]
            elif severity == 'Severe':
                status = random.choices(['Active', 'Recovered', 'Deceased'], weights=[0.3, 0.65, 0.05])[0]
            else:
                status = random.choices(['Active', 'Recovered'], weights=[0.2, 0.8])[0]
            
            # Symptoms
            symptoms = []
            symptom_pool = ['Fever', 'Cough', 'Fatigue', 'Loss of Taste/Smell', 'Sore Throat', 
                           'Difficulty Breathing', 'Body Ache', 'Headache', 'Diarrhea']
            num_symptoms = random.randint(2, 6)
            symptoms = random.sample(symptom_pool, num_symptoms)
            
            record = {
                'patient_id': f'PAT_{i+1:06d}',
                'name': f"{random.choice(self.first_names)} {random.choice(self.last_names)}",
                'age': age,
                'gender': random.choice(['Male', 'Female', 'Other']),
                'contact': f'9{random.randint(100000000, 999999999)}',
                'address': f'{random.randint(1, 500)} Main Street',
                'city': city,
                'state': state,
                'country': 'India',
                'latitude': round(lat, 6),
                'longitude': round(lon, 6),
                'disease_type': 'COVID19',
                'diagnosis_date': diagnosis_date.strftime('%Y-%m-%d'),
                'severity': severity,
                'status': status,
                'vaccination_status': vaccination,
                'symptoms': '|'.join(symptoms),
                'test_type': random.choice(['RT-PCR', 'Rapid Antigen', 'Antibody']),
                'test_result': 'Positive',
                'ct_value': round(random.uniform(15, 35), 1) if random.random() > 0.3 else '',
                'oxygen_saturation': random.randint(85, 100),
                'comorbidities': '|'.join(random.sample(['Diabetes', 'Hypertension', 'Heart Disease', 'None'], 
                                                        k=random.randint(0, 2)))
            }
            
            data.append(record)
        
        df = pd.DataFrame(data)
        df.to_csv('covid19_dataset_10000.csv', index=False)
        print(f"✅ Generated COVID-19 dataset: covid19_dataset_10000.csv ({num_records} records)")
        return df
    
    def generate_cholera_dataset(self, num_records=10000):
        """Generate Cholera patient dataset"""
        
        data = []
        start_date = datetime.now() - timedelta(days=365)
        
        for i in range(num_records):
            city_data = random.choice(self.indian_cities)
            city, state, base_lat, base_lon = city_data
            
            lat = base_lat + random.uniform(-0.5, 0.5)
            lon = base_lon + random.uniform(-0.5, 0.5)
            
            days_ago = int(np.random.exponential(120))
            diagnosis_date = start_date + timedelta(days=days_ago)
            
            age = int(np.random.beta(2, 3) * 80)
            
            # Cholera severity
            severity = random.choices(
                ['Mild', 'Moderate', 'Severe', 'Critical'],
                weights=[0.35, 0.4, 0.2, 0.05]
            )[0]
            
            if severity in ['Severe', 'Critical']:
                status = random.choices(['Active', 'Recovered', 'Deceased'], weights=[0.3, 0.6, 0.1])[0]
            else:
                status = random.choices(['Active', 'Recovered'], weights=[0.25, 0.75])[0]
            
            record = {
                'patient_id': f'PAT_{i+1:06d}',
                'name': f"{random.choice(self.first_names)} {random.choice(self.last_names)}",
                'age': age,
                'gender': random.choice(['Male', 'Female']),
                'contact': f'9{random.randint(100000000, 999999999)}',
                'address': f'{random.randint(1, 500)} Street',
                'city': city,
                'state': state,
                'country': 'India',
                'latitude': round(lat, 6),
                'longitude': round(lon, 6),
                'disease_type': 'Cholera',
                'diagnosis_date': diagnosis_date.strftime('%Y-%m-%d'),
                'severity': severity,
                'status': status,
                'stool_frequency': random.randint(5, 30),
                'stool_type': random.choice(['Rice water', 'Watery', 'Loose']),
                'dehydration_level': random.choice(['None', 'Mild', 'Moderate', 'Severe']),
                'stool_culture': random.choices(['Positive', 'Negative'], weights=[0.85, 0.15])[0],
                'water_source': random.choice(['Municipal', 'Well', 'Pond', 'River', 'Bottled']),
                'rehydration_type': random.choice(['ORS', 'IV fluids', 'Both'])
            }
            
            data.append(record)
        
        df = pd.DataFrame(data)
        df.to_csv('cholera_dataset_10000.csv', index=False)
        print(f"✅ Generated Cholera dataset: cholera_dataset_10000.csv ({num_records} records)")
        return df
    
    def generate_hiv_dataset(self, num_records=10000):
        """Generate HIV/AIDS patient dataset"""
        
        data = []
        start_date = datetime.now() - timedelta(days=1825)  # 5 years
        
        for i in range(num_records):
            city_data = random.choice(self.indian_cities)
            city, state, base_lat, base_lon = city_data
            
            lat = base_lat + random.uniform(-0.5, 0.5)
            lon = base_lon + random.uniform(-0.5, 0.5)
            
            days_ago = random.randint(0, 1825)
            diagnosis_date = start_date + timedelta(days=days_ago)
            
            age = int(np.random.beta(3, 2) * 60 + 18)  # 18-78 years
            
            # HIV stage
            hiv_stage = random.choices(
                ['Stage 1', 'Stage 2', 'Stage 3'],
                weights=[0.5, 0.35, 0.15]
            )[0]
            
            # CD4 count based on stage
            if hiv_stage == 'Stage 1':
                cd4_count = random.randint(500, 1600)
                viral_load = random.randint(0, 50000)
            elif hiv_stage == 'Stage 2':
                cd4_count = random.randint(200, 499)
                viral_load = random.randint(50000, 200000)
            else:
                cd4_count = random.randint(0, 199)
                viral_load = random.randint(200000, 1000000)
            
            art_status = random.choices(
                ['On treatment', 'Not started', 'Stopped'],
                weights=[0.7, 0.2, 0.1]
            )[0]
            
            record = {
                'patient_id': f'PAT_{i+1:06d}',
                'name': f"{random.choice(self.first_names)} {random.choice(self.last_names)}",
                'age': age,
                'gender': random.choice(['Male', 'Female']),
                'contact': f'9{random.randint(100000000, 999999999)}',
                'address': f'{random.randint(1, 500)} Colony',
                'city': city,
                'state': state,
                'country': 'India',
                'latitude': round(lat, 6),
                'longitude': round(lon, 6),
                'disease_type': 'HIV',
                'diagnosis_date': diagnosis_date.strftime('%Y-%m-%d'),
                'severity': hiv_stage,
                'status': 'Active' if art_status == 'On treatment' else 'Untreated',
                'cd4_count': cd4_count,
                'viral_load': viral_load,
                'test_type': random.choice(['ELISA', 'Western Blot', 'PCR']),
                'test_result': 'Positive',
                'art_status': art_status,
                'art_regimen': 'TDF+3TC+EFV' if art_status == 'On treatment' else '',
                'transmission_route': random.choice(['Sexual', 'Blood', 'MTCT', 'Unknown'])
            }
            
            data.append(record)
        
        df = pd.DataFrame(data)
        df.to_csv('hiv_dataset_10000.csv', index=False)
        print(f"✅ Generated HIV/AIDS dataset: hiv_dataset_10000.csv ({num_records} records)")
        return df
    
    def generate_swineflu_dataset(self, num_records=10000):
        """Generate Swine Flu patient dataset"""
        
        data = []
        start_date = datetime.now() - timedelta(days=365)
        
        for i in range(num_records):
            city_data = random.choice(self.indian_cities)
            city, state, base_lat, base_lon = city_data
            
            lat = base_lat + random.uniform(-0.5, 0.5)
            lon = base_lon + random.uniform(-0.5, 0.5)
            
            days_ago = int(np.random.exponential(100))
            diagnosis_date = start_date + timedelta(days=days_ago)
            
            age = int(np.random.beta(2, 4) * 90)
            
            flu_vaccine = random.choices(['Yes', 'No'], weights=[0.4, 0.6])[0]
            
            if flu_vaccine == 'Yes':
                severity = random.choices(
                    ['Mild', 'Moderate', 'Severe', 'Critical'],
                    weights=[0.6, 0.3, 0.08, 0.02]
                )[0]
            else:
                severity = random.choices(
                    ['Mild', 'Moderate', 'Severe', 'Critical'],
                    weights=[0.35, 0.4, 0.2, 0.05]
                )[0]
            
            if severity in ['Severe', 'Critical']:
                status = random.choices(['Active', 'Recovered', 'Deceased'], weights=[0.35, 0.6, 0.05])[0]
            else:
                status = random.choices(['Active', 'Recovered'], weights=[0.3, 0.7])[0]
            
            record = {
                'patient_id': f'PAT_{i+1:06d}',
                'name': f"{random.choice(self.first_names)} {random.choice(self.last_names)}",
                'age': age,
                'gender': random.choice(['Male', 'Female']),
                'contact': f'9{random.randint(100000000, 999999999)}',
                'address': f'{random.randint(1, 500)} Road',
                'city': city,
                'state': state,
                'country': 'India',
                'latitude': round(lat, 6),
                'longitude': round(lon, 6),
                'disease_type': 'SwineFlu',
                'diagnosis_date': diagnosis_date.strftime('%Y-%m-%d'),
                'severity': severity,
                'status': status,
                'flu_vaccine': flu_vaccine,
                'test_type': random.choice(['RT-PCR', 'Rapid Influenza', 'Viral Culture']),
                'test_result': random.choice(['Positive for H1N1', 'Positive for H3N2']),
                'max_temperature': round(random.uniform(99, 105), 1),
                'oxygen_saturation': random.randint(88, 100),
                'hospitalization': random.choice(['Not hospitalized', 'Hospitalized', 'ICU']),
                'antiviral': random.choice(['Oseltamivir', 'Zanamivir', 'None']),
                'animal_contact': random.choices(['No', 'Yes'], weights=[0.8, 0.2])[0]
            }
            
            data.append(record)
        
        df = pd.DataFrame(data)
        df.to_csv('swineflu_dataset_10000.csv', index=False)
        print(f"✅ Generated Swine Flu dataset: swineflu_dataset_10000.csv ({num_records} records)")
        return df
    
    def generate_all_datasets(self):
        """Generate all disease datasets"""
        print("🔄 Generating dummy datasets for all diseases...")
        print("=" * 60)
        
        self.generate_covid19_dataset(10000)
        self.generate_cholera_dataset(10000)
        self.generate_hiv_dataset(10000)
        self.generate_swineflu_dataset(10000)
        
        print("=" * 60)
        print("✅ All datasets generated successfully!")
        print("\nFiles created:")
        print("  - covid19_dataset_10000.csv")
        print("  - cholera_dataset_10000.csv")
        print("  - hiv_dataset_10000.csv")
        print("  - swineflu_dataset_10000.csv")
        print("\nTotal records: 40,000")


if __name__ == '__main__':
    generator = DummyDatasetGenerator()
    generator.generate_all_datasets()