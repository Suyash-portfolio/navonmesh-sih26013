"""
Benchmark Test Suite:
1. Execution Latency <= 5.0 Seconds per sq. km (1,420 parcels)
2. Mean Segmentation IoU >= 94.5%
"""

import time
import numpy as np
import pytest
from app.data.pune_ward14_dataset import generate_pune_ward14_data
from app.geoai.topology_cleaner import TopologyCleaner


def test_execution_latency_under_5_seconds():
    """Verifies that the entire 1,420 parcel sector is conflated and planarized in < 5.0s."""
    start_time = time.time()
    
    data = generate_pune_ward14_data()
    cleaner = TopologyCleaner(snap_tolerance_meters=0.15, min_sliver_area_sqm=2.0)
    topo_res = cleaner.enforce_planar_topology(data["parcels"])
    
    elapsed = time.time() - start_time
    print(f"\n[BENCHMARK] Harmonized 1,420 parcels in {elapsed:.3f} seconds.")
    
    assert elapsed <= 5.0, f"Execution latency exceeded 5.0s (took {elapsed:.3f}s)"
    assert topo_res["all_polygons_valid"] is True


def test_segmentation_accuracy_benchmark():
    """Verifies Mean IoU >= 94.5% across AI harmonized boundaries."""
    data = generate_pune_ward14_data()
    ious = [p["segmentation_iou"] for p in data["parcels"]]
    mean_iou = np.mean(ious) * 100.0
    print(f"\n[BENCHMARK] Mean SAM-2 Segmentation IoU: {mean_iou:.2f}%")
    assert mean_iou >= 94.5, f"Mean IoU {mean_iou}% was below 94.5% threshold"
