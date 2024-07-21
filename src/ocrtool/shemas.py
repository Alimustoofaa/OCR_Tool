from typing import Optional
from pydantic import BaseModel

class DeviceGate(BaseModel):
	name : str
	ip : str
	username : str
	password: str
	command: Optional[str] = 'uptime'
	restart: Optional[str] = ''
	reboot: Optional[str] = ''
	
class Gate(BaseModel):
	name : str
	devices : list[DeviceGate]
	
class ListGate(BaseModel):
   gate : list[Gate]