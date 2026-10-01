from datetime import datetime

from pydantic import BaseModel, ConfigDict

class CameraCreate(BaseModel):
    device_id: str
    camera_name: str
    resolution_width: int
    resolution_height: int
    reprojection_error: float | None = None


class CameraResponse(BaseModel):
    camera_id: int
    user_id: int
    device_id: str
    camera_name: str
    resolution_width: int
    resolution_height: int
    reprojection_error: float | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)