"""
Tools OCR
"""

import os
import json
import ping3
import threading
from pathlib import Path
from pydantic import ValidationError
from logging_datetime import SetupLogger, logging

import toga
from toga import Button, paths
from toga.style import Pack
from toga.constants import CENTER, COLUMN, ROW, Direction, RIGHT
import concurrent.futures

from .devices import Device
from .shemas import ListGate


class OCRTool(toga.App):
    async def upload_config(self, *args, **kwargs):
        file_path = await self.main_window.open_file_dialog('Upload Config', file_types=['json'])

        # Update the label with the selected file path
        if file_path:
            with open(file_path, 'r') as file:
                data = json.load(file)
            try:
                ListGate(**data)
                with open(os.path.join(self.config_path, 'config.json'), 'w') as file:
                    json.dump(data, file, indent=4)
                    
                logging.info(f'[Config] Update Config : {data}')
                self.load_config()
                self.refresh_data_gate()
                
            except ValidationError as e:
                logging.error('[Config] Error Config : {e}')
                self.main_window.error_dialog('Error Config', str(e))
                
    def refresh_data_gate(self):
        self.label_device.data.clear()
        for device in self.list_gate:
            self.label_device.data.append(device)
    
    def load_config(self):
        config_path_name = os.path.join(self.config_path, 'config.json')
        if Path(config_path_name).is_file():
            self.data_device = Device(config_path_name)
            self.list_gate = self.data_device.list_gate
        else:
            self.list_gate = []
        
    def setup_path(self):
        self.home_path = f'{paths.Path.home()}'
        self.app_base_dir = os.path.join(self.home_path, 'OCRTool')
        self.config_path = os.path.join(self.app_base_dir, 'Config')
        self.log_path = os.path.join(self.app_base_dir, 'Logger')
        # create path
        Path(self.config_path).mkdir(parents=True, exist_ok=True)
        Path(self.log_path).mkdir(parents=True, exist_ok=True)
        
    def startup(self):
        """Construct and show the Toga application.

        Usually, you would add your application to a main content box.
        We then create a main window (with a name matching the app), and
        show the main window.
        """
        self.setup_path()
        # setup logger
        SetupLogger(self.log_path)
        self.previous_size_log = 0
        # read database
        self.load_config()
            
        self.things = toga.Group("Config")
        self.cmd0 = toga.Command(
            self.upload_config,
            text="Config Json",
            tooltip="Upload Config",
            group=self.things,
        )
            
        self.split = toga.SplitContainer(direction=Direction.VERTICAL)
        self.left_container = toga.Box(style=Pack(padding=(10, 10)))
        self.right_container = toga.Box(style=Pack(direction=COLUMN, padding=(0, 5)))
        
        # Add view content device
        self.label_device = toga.Table(
            ['List Gate'], 
            on_select=self.on_select_handler_gate,
            style=Pack(text_align=CENTER, flex=1, font_weight='bold'),
        )
        # self.label_device.focus()
        for device in self.list_gate:
            self.label_device.data.append(device)
        self.left_container.add(self.label_device)
        
        # Create a label in the right container to display the selected device name
        self.selected_device_label = toga.Label(
            '', 
            style=Pack(padding=(10, 10), text_align=CENTER, font_weight='bold', font_size=18)
        )
        self.show_selected_device = toga.Table(
            headings=['Device', 'Uptime'],
            style=Pack(padding=(0, 5), flex=2),
        )
        
        # Add button Action
        self.button_split = toga.Box(style=Pack(padding=(5,5), direction=ROW))
        action_restart = Button('Restart OCR', on_press=self.action_restart_ocr, style=Pack(background_color='#DAA520', padding=(2,10,2,2)))
        action_reboot = Button('Reboot Jetson', on_press=self.reboot_device,style=Pack(background_color='#A52A2A', padding=(2,2,2,2)))
        self.button_split.add(action_restart)
        self.button_split.add(action_reboot)
        
        # Add streaming log TextInput widget
        self.log_output = toga.MultilineTextInput(
            readonly=True,
            style=Pack(flex=1, padding=(5, 5))
        )
        
        self.right_container.add(self.selected_device_label)
        self.right_container.add(self.show_selected_device)
        self.right_container.add(self.button_split)
        self.right_container.add(self.log_output)
        
        self.split.content = [(self.left_container, 2), (self.right_container, 4)]
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.split
        self.main_window.show()
        self.commands.add(self.cmd0)
        self.main_window.toolbar.add(self.cmd0)
        
        if not self.list_gate:
            self.main_window.error_dialog('Error Config', 'Config not found, please upload config')
        
        self.schedule_refresh()
        self.schedule_log_update()
        self.schedule_check_ping()

    def on_select_handler_gate(self, widget, **kwargs):
        row = self.label_device.selection 
        self.show_selected_device.data.clear()
        if row is not None:
            self.selected_device_label.text = f'{row.list_gate}'  
            result_device = self.data_device.handle_status(row.list_gate)
            
            for device in result_device:
                if 'up' in device[1]:
                    device[0] = toga.Switch(device[0])
                else: 
                    device[0] = toga.Switch(device[0], enabled=False)
                    self.beep()
                self.show_selected_device.data.append(device)
    
    def schedule_refresh(self):
        self.loop.call_later(60, self.refresh_data)

    def refresh_data(self):
        self.on_select_handler_gate(self.label_device)
        self.schedule_refresh()
        
    def schedule_log_update(self):
        self.loop.call_later(5, self.update_log)    
        
    def update_log(self):
        path_log = os.path.join(self.log_path, 'logging.log')
        # while True:
            # Check if the file has grown
        try:
            curr_size = Path(path_log).stat().st_size
            if curr_size > self.previous_size_log:
                with open(path_log, 'r') as file:
                    file.seek(self.previous_size_log)
                    data = file.readlines()
                    data = data[:50]
                    if data:
                        self.log_output.value += ''.join(data)
                        self.log_output.scroll_to_bottom()
                self.previous_size_log = curr_size
        except FileNotFoundError:
            self.log_output.value += "Log file not found.\n"

            # await asyncio.sleep(1)
        self.schedule_log_update()
        
    async def action_restart_ocr(self, widget, **kwargs):
        gate = self.selected_device_label.text
        device_restart = []
        for i in self.show_selected_device.data._data:
            if i.device.value == True:
                device_restart.append(i.device.text)
                
        is_restart = await self.main_window.question_dialog(
            'Restart OCR',
            message='\n'.join(device_restart),
        )
        if is_restart:
            if device_restart:
                threading.Thread(
                    target=self.data_device.handle_restart_ocr,
                    args=(
                        gate, 
                        device_restart,
                        len(device_restart)
                    )
                ).start()
                logging.info(f"[Restart] OCR : {gate} | {device_restart}")
            else: 
                self.main_window.info_dialog('Device', 'No Selected Device')
        
    async def reboot_device(self, widget, **kwargs):
        gate = self.selected_device_label.text
        device_restart = []
        for i in self.show_selected_device.data._data:
            if i.device.value == True:
                device_restart.append(i.device.text)
                
        is_reboot = await self.main_window.question_dialog(
            'Reboot OCR',
            message='\n'.join(device_restart),
        )
        if is_reboot:
            if device_restart:
                threading.Thread(
                    target=self.data_device.handle_reboot_ocr,
                    args=(
                        gate, 
                        device_restart,
                        len(device_restart)
                    )
                ).start()
                logging.info(f"[Reboot] OCR : {gate} | {device_restart}")
            else:
                self.main_window.info_dialog('Device', 'No Selected Device')
                
    def schedule_check_ping(self):
        self.loop.call_later(60, self.ping_device)    
        
    def ping_device(self) -> None:
        gates = self.data_device.datagate.gate
        for gate in gates:
            name_gate = gate.name
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(self.exec_ping, i.ip, name_gate, i.name) for i in gate.devices]
                for future in concurrent.futures.as_completed(futures):
                    gate, device, succes = future.result()
                    if not succes:
                        logging.error(f'[PING] Timeout : {gate} {device}')
                        self.beep()
        self.schedule_check_ping()
                
    def exec_ping(self, ip, gate, device):
        try:
            response_time = ping3.ping(ip, timeout=1)  # Timeout set to 1 second
            if response_time is None:
                return gate, device, False
            return gate, device, True
        except Exception as e:
            return gate, device, False


def main():
    return OCRTool(
		formal_name='OCR Tool',
		app_id='com.alimustofa.ocrtool',
		app_name='OCR Tool',
		icon='resources/icon'
	)
