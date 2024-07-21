import json
import paramiko
from concurrent.futures import ThreadPoolExecutor, as_completed


try:
	from .shemas import DeviceGate, Gate, ListGate
except ImportError:
	from shemas import DeviceGate, Gate, ListGate
from logging_datetime import logging

class Device:
	def __init__(self, path_data: str) -> None:
		self.path_data = path_data
		self.read_data_device()
		self.get_list_gate()
		
	def read_data_device(self):
		with open(self.path_data) as f:
			data = json.load(f)
			self.datagate = ListGate(**data)
		
	def get_list_gate(self) -> list:
		self.list_gate = [gate.name for gate in self.datagate.gate]

	def __getitem__(self, gate_search: str)-> list[DeviceGate]:
		for gate in self.datagate.gate:
			if gate.name == gate_search:
				return gate.devices
	
	@staticmethod            
	def ssh_login(name: str, host: str, username: str, password: str, command: str, timeout:int = 2):
		try:
			ssh = paramiko.SSHClient()
			ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			ssh.connect(host, username=username, password=password, timeout=timeout)
			stdin, stdout, stderr = ssh.exec_command(command)
			result = stdout.read().decode()
			ssh.close()
			date_time = result.split(',')[0]

			return name.upper(), date_time, None
		except Exception as e:
			return name.upper(), None, str(e)
	
	def handle_status(self, gate_id: str, max_threads: int = 5):
		results = []
		list_devices = self.__getitem__(gate_id)
		with ThreadPoolExecutor(max_threads) as executor:
			future_to_ssh = {
				executor.submit(self.ssh_login, cred.name, cred.ip, cred.username, cred.password, cred.command): cred.ip
				for cred in list_devices
			}
			for future in as_completed(future_to_ssh):
				host = future_to_ssh[future]
				try:
					host, result, error = future.result()
					if error:
						results.append([host, error])
					else:
						results.append([host, result])
				except Exception as e:
					results.append([host, e])
		return sorted(results)

	def handle_restart_ocr(self, gate_id:str, device:list, max_threads: int = 5):
		list_devices = self.__getitem__(gate_id)
		filter_restart = []
		for i in list_devices:
			if i.name.upper() in device:
				if i.name.lower() == 'trigger':
					i.restart = f"echo '{i.password}' | sudo -S systemctl restart trigger.service"
				else:
					i.restart = 'pm2 restart ocr'
				filter_restart.append(i)
		with ThreadPoolExecutor(max_threads) as executor:
			future_to_ssh = {
				executor.submit(self.ssh_login, cred.name, cred.ip, cred.username, cred.password, cred.restart, 10): cred.ip
				for cred in filter_restart
			}
			for future in as_completed(future_to_ssh):
				host = future_to_ssh[future]
				try:
					host, result, error = future.result()
					if error:
						logging.error(f'[Restart] Error: {e}')
					else:
						logging.info(f'[Restart] Success: {host}')
				except Exception as e:
					logging.error(f'[Restart] Error: {e}')

	def handle_reboot_ocr(self, gate_id:str, device:list, max_threads: int = 5):
		list_devices = self.__getitem__(gate_id)
		filter_reboot = []
		for i in list_devices:
			if i.name.upper() in device:
				i.reboot = f"echo '{i.password}' | sudo -S reboot now"
				filter_reboot.append(i)
		with ThreadPoolExecutor(max_threads) as executor:
			future_to_ssh = {
				executor.submit(self.ssh_login, cred.name, cred.ip, cred.username, cred.password, cred.reboot, 10): cred.ip
				for cred in filter_reboot
			}
			for future in as_completed(future_to_ssh):
				host = future_to_ssh[future]
				try:
					host, result, error = future.result()
					if error:
						logging.error(f'[Reboot] Error: {error}')
					else:
						logging.info(f'[Reboot] Success: {host}')
				except Exception as e:
					logging.error(f'[Reboot] Error: {e}')
				

		
		
if __name__ == '__main__':
	data_device = Device('helloworld/src/helloworld/resources/device.json')
	data_pergate = data_device.__getitem__('Gate 03')
	print(data_device.handle_restart_ocr('Gate 02', ['REAR']))