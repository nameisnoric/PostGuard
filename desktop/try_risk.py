
from app.services.risk_engine import assess_posture

result = assess_posture(
    neck_extension=True,
    neck_side_bending=True,
    neck_rotation=True,
    trunk_level=3,
    sustained_seconds=65,
)

print(result)
