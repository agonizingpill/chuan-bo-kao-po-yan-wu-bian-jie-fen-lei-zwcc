import hashlib
import json
from functools import lru_cache

import numpy as np
import sklearn
from sklearn.metrics import balanced_accuracy_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

SEED = 1074
BAND = 0.30
FEATURES = ('eta_offset_min', 'tide_reserve_min', 'wind_kn', 'tug_wait_min')
PARAMETERS = {'kernel': 'rbf', 'C': 1.7, 'gamma': 'scale', 'random_state': SEED}


def snapshot_digest(features):
    return hashlib.sha256(json.dumps(features, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def history(rng, pairs):
    # Independent mirrored records around a borderline operating point.
    center = np.array([18, 25, 14, 12])
    offset = rng.uniform(-1, 1, (pairs, 4)) * [18, 24, 14, 12]
    noise = rng.normal(0.0, 2.8, pairs)
    score = offset @ [1.0, -0.62, 0.75, 0.85] + 3.2 * np.tanh(offset[:, 0] / 10) + noise
    priority = (score > 0).astype(int)
    return np.vstack([center + offset, center - offset]), np.concatenate([priority, 1 - priority])


@lru_cache(maxsize=1)
def fit():
    rng = np.random.default_rng(SEED)
    train_x, train_y = history(rng, 360)
    validation_x, validation_y = history(rng, 120)
    model = make_pipeline(StandardScaler(), SVC(**PARAMETERS))
    model.fit(train_x, train_y)
    metrics = {
        'train_rows': len(train_y),
        'validation_rows': len(validation_y),
        'balanced_accuracy': round(float(balanced_accuracy_score(validation_y, model.predict(validation_x))), 4),
        'validation_margin_rate': round(float(np.mean(np.abs(model.decision_function(validation_x)) <= BAND)), 4),
        'support_vectors': int(model[-1].n_support_.sum()),
    }
    return model, metrics


def classify(features, expected_digest):
    if set(features) != set(FEATURES) or snapshot_digest(features) != expected_digest:
        raise ValueError('冻结输入不完整或摘要不一致')
    row = np.array([[features[key] for key in FEATURES]], dtype=float)
    if not np.isfinite(row).all():
        raise ValueError('冻结输入包含不可计算的数值')
    model, metrics = fit()
    score = float(model.decision_function(row)[0])
    return {
        'score': score, 'band': BAND, 'needs_review': abs(score) <= BAND,
        'prediction': 'priority' if score > 0 else 'routine',
        'seed': SEED, 'input_digest': expected_digest, 'parameters': PARAMETERS,
        'metrics': metrics, 'sklearn': sklearn.__version__,
    }
