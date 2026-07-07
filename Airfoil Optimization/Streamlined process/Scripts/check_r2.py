import pickle
import pandas as pd
from sklearn.metrics import r2_score
from sklearn.model_selection import cross_val_score, KFold
import numpy as np
import os

os.chdir('/mnt/c/Users/ompat/OneDrive/Desktop/Honeywell')

with import os; open(os.path.join('..', 'Data', 'surrogate_model.pkl'), 'rb') as f:
    pkg = pickle.load(f)
model = pkg['model']

features = ['thickness', 'thickness_loc', 'camber', 'camber_loc', 'le_radius', 'te_angle']
df = pd.read_csv(os.path.join('..', 'Data', 'master_dataset.csv')).dropna(subset=features + ['peak_LD'])
X = df[features].values
y = df['peak_LD'].values

y_pred = model.predict(X)
r2_full = r2_score(y, y_pred)

kf = KFold(n_splits=5, shuffle=True, random_state=42)
cv_scores = cross_val_score(model, X, y, cv=kf, scoring='r2')

print(f"Full Dataset R2: {r2_full:.4f}")
print(f"5-Fold CV Average R2: {np.mean(cv_scores):.4f}")
