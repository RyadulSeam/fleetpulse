from __future__ import annotations

import numpy as np


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km (vectorised)."""
    r = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dl = p2 - p1, np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))
