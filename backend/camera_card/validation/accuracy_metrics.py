import math
from collections import defaultdict


def absolute_error(detected, ground_truth):
    return abs(float(detected) - float(ground_truth))


def _mean(values):
    values = list(values)
    return None if not values else sum(values) / len(values)


def mae(records):
    errors = [float(r['absolute_error']) for r in records if r.get('absolute_error') is not None]
    return _mean(errors)


def rmse(records):
    errors = [float(r['detected_median']) - float(r['ground_truth']) for r in records
              if r.get('detected_median') is not None and r.get('ground_truth') is not None]
    if not errors:
        return None
    return math.sqrt(sum(e * e for e in errors) / len(errors))


def summarize_by_feature(records):
    grouped = defaultdict(list)
    for record in records:
        grouped[record['feature']].append(record)
    return {
        feature: {
            'count': len(items),
            'mae': mae(items),
            'rmse': rmse(items),
        }
        for feature, items in grouped.items()
    }
