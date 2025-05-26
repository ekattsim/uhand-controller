import asyncio
from bleak import BleakClient, BleakScanner
import struct

# The address/system ID of the Robotic Glove BLE device.
DEVICE_ADDRESS = "24A528A5-46FC-C425-02D5-E59445D692C3"

# The Service UUID where the communication characteristics reside.
UART_SERVICE_UUID = "FFF0"

# The Characteristic UUID to *write* commands to the device (RX).
# This characteristic should have 'write' or 'write without response' properties.
WRITE_CHARACTERISTIC_UUID = "0000FFE1-0000-1000-8000-00805F9B34FB"

# --- Asynchronous RoboticGloveController Class ---
class RoboticGloveController:
    def __init__(self, device_address: str):
        self.device_address = device_address
        self.client: BleakClient = None
        self.is_connected = False
        self.write_char_object = None

    async def connect(self):
        """
        Connects to the BLE device.
        """
        if self.is_connected and self.client:
            print("Already connected.")
            return True

        print(f"Attempting to connect to {self.device_address}...")
        try:
            self.client = BleakClient(self.device_address)
            await self.client.connect()
            self.is_connected = True
            print(f"Connected to {self.device_address}.")

            # --- Find Characteristic Object ---
            found_service = None
            for service in self.client.services:
                # Compare UUIDs case-insensitively, and handle potential 16-bit vs 128-bit forms
                if str(service.uuid).upper() == UART_SERVICE_UUID.upper() or \
                   (len(UART_SERVICE_UUID) == 4 and str(service.uuid).upper() == f"0000{UART_SERVICE_UUID.upper()}-0000-1000-8000-00805F9B34FB"):
                    found_service = service
                    print(f"Found target service: {service.uuid} (Handle: {service.handle})")
                    break

            if not found_service:
                print(f"ERROR: Could not find service with UUID {UART_SERVICE_UUID}.")
                await self.client.disconnect()
                self.is_connected = False
                return False

            # Iterate through characteristics within the found service
            for char in found_service.characteristics:
                if str(char.uuid).upper() == WRITE_CHARACTERISTIC_UUID.upper():
                    self.write_char_object = char
                    print(f"Found write characteristic object: {self.write_char_object.uuid} (Handle: {self.write_char_object.handle})")
                    break # Found it, no need to search further

            if self.write_char_object is None:
                print(f"ERROR: Could not find write characteristic with UUID {WRITE_CHARACTERISTIC_UUID} "
                      f"and 'write' or 'write without response' properties within service {UART_SERVICE_UUID}.")
                await self.client.disconnect()
                self.is_connected = False
                return False

            return True

        except Exception as e:
            print(f"Error connecting to BLE device {self.device_address}: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        """
        Disconnects from the BLE device.
        """
        if self.is_connected and self.client:
            try:
                await self.client.disconnect()
                self.is_connected = False
                print("Disconnected from BLE device.")
            except Exception as e:
                print(f"Error disconnecting: {e}")
        else:
            print("Not connected.")

    async def _send_command(self, command_char: str, value: int):
        """
        Sends a command to the Arduino over BLE.
        :param command_char: The single character command (e.g., 'A', 'R').
        :param value: The integer value to send (e.g., servo angle, color component).
        """
        if not self.is_connected or not self.client:
            print("Not connected to BLE device. Cannot send command.")
            return

        # Ensure value is an integer
        value_int = int(value)

        # Format the command string per default protocol
        command_string = f"{command_char}{value_int}$"
        command_bytes = command_string.encode('utf-8')

        try:
            # Write to the characteristic. Use write_gatt_char for sending data.
            # 'response=True' means it expects a confirmation from the device (slower but reliable).
            # 'response=False' means 'write without response' (faster, less reliable).
            # Choose based on device's characteristic properties and needs.
            await self.client.write_gatt_char(self.write_char_object, command_bytes, response=False)
            print(f"Sent (BLE): {command_string}")
        except Exception as e:
            print(f"Error sending command '{command_string}' over BLE: {e}")

    async def set_servo_angle(self, servo_index: int, angle: int):
        """
        Sets the angle for a specific servo.
        :param servo_index: The index of the servo (0-5).
        :param angle: The desired angle (0-180 degrees).
        """
        if not 0 <= servo_index <= 5:
            print("Servo index must be between 0 and 5.")
            return
        if not 0 <= angle <= 180:
            print("Angle must be between 0 and 180 degrees.")
            return

        command_char = chr(ord('A') + servo_index)
        await self._send_command(command_char, angle)

    async def set_all_servos_angle(self, angle: int):
        """
        Sets all servos to a specific angle.
        :param angle: The desired angle (0-180 degrees).
        """
        for i in range(6):
            await self.set_servo_angle(i, angle)
        print(f"Set all servos to {angle} degrees.")

    async def set_rgb_led(self, r: int, g: int, b: int):
        """
        Sets the RGB LED color.
        :param r: Red component (0-255).
        :param g: Green component (0-255).
        :param b: Blue component (0-255).
        """
        if not all(0 <= val <= 255 for val in [r, g, b]):
            print("RGB color components must be between 0 and 255.")
            return

        await self._send_command('G', r)
        await self._send_command('H', g)
        await self._send_command('I', b)
        # Assuming 'J' still triggers FastLED.show(), but BLE might not need a dummy value
        await self._send_command('J', 0)

    async def play_buzzer_tone(self):
        """Plays a short tone on the buzzer."""
        await self._send_command('Z', 1)

    async def stop_buzzer_tone(self):
        """Stops any active tone on the buzzer."""
        await self._send_command('Z', 0)

    # --- Helper for discovering devices ---
    @staticmethod
    async def discover_devices_async(name):
        print("Scanning for BLE devices...")
        device = await BleakScanner.find_device_by_name(name, timeout=10.0) # Scan for 10 seconds

        if not device:
            print(f"No BLE device with name {name} found.")
            return

        print(f"Device {name} found.")
        return device


# --- Main execution block (Asyncio) ---
async def main():
    # First, run discovery to find device directly
    print("--- Discovering BLE Devices ---")
    device = await RoboticGloveController.discover_devices_async("Hiwonder")
    print("\n--- Discovery Complete ---")

    controller = RoboticGloveController(device) if device else RoboticGloveController(DEVICE_ADDRESS)

    if await controller.connect():
        try:
            print("\n--- Testing Servo Control ---")
            await controller.set_servo_angle(0, 45) # Move servo 0 to 45 degrees
            await asyncio.sleep(1)
            await controller.set_servo_angle(1, 135) # Move servo 1 to 135 degrees
            await asyncio.sleep(1)
            await controller.set_all_servos_angle(90) # Return all servos to center
            await asyncio.sleep(2)

            # print("\n--- Testing RGB LED Control ---")
            # await controller.set_rgb_led(255, 0, 0) # Red
            # await asyncio.sleep(2)
            # await controller.set_rgb_led(0, 255, 0) # Green
            # await asyncio.sleep(2)
            # await controller.set_rgb_led(0, 0, 255) # Blue
            # await asyncio.sleep(2)
            # await controller.set_rgb_led(0, 0, 0) # Off
            # await asyncio.sleep(1)
            # await controller.set_rgb_led(200, 200, 200) # White
            # await asyncio.sleep(2)

            # print("\n--- Testing Buzzer Control ---")
            # await controller.play_buzzer_tone()
            # await asyncio.sleep(3)
            # await controller.stop_buzzer_tone()
            # await asyncio.sleep(1)

        except KeyboardInterrupt:
            print("\nExiting program.")
        finally:
            await controller.disconnect()
    else:
        print("Could not connect to Robotic Glove. Exiting.")

if __name__ == "__main__":
    asyncio.run(main())
