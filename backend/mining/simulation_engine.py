import numpy as np
import pandas as pd

class SimulationEngine:
    def __init__(self, current_infected, current_recovered, population=1000000):
        self.S = population - current_infected - current_recovered
        self.I = current_infected
        self.R = current_recovered
        self.N = population

    def run_sir_projection(self, days=30, intervention_factor=0.0):
        """
        Run SIR model.
        intervention_factor (0.0 to 1.0): Reduces Beta (Transmission).
        Returns list of daily {day, infected, recovered}
        """
        # Baseline Parameters (approximate for flu/covid-like)
        beta_baseline = 0.3  # Contact rate
        gamma = 0.1          # Recovery rate (1/10 days)
        
        # Apply intervention
        # If factor is 1.0 (lockdown), beta drops drastically
        beta = beta_baseline * (1.0 - (intervention_factor * 0.7)) # Cannot reduce to 0 effectively
        
        S, I, R = self.S, self.I, self.R
        
        results = []
        for d in range(days):
            # Differential Equations
            dS = -beta * S * I / self.N
            dI = (beta * S * I / self.N) - (gamma * I)
            dR = gamma * I
            
            S += dS
            I += dI
            R += dR
            
            # Clamp
            I = max(0, I)
            
            results.append({
                "day": d + 1,
                "infected": int(I),
                "recovered": int(R),
                "susceptible": int(S)
            })
            
        return results
