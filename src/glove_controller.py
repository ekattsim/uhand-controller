from bleak import BleakClient, BleakScanner

# The address/system ID of the Robotic Glove BLE device.
DEVICE_ADDRESS = "24A528A5-46FC-C425-02D5-E59445D692C3"

# The Service UUID where the communication characteristics reside.
UART_SERVICE_UUID = "FFF0"

# The Characteristic UUID to *write* commands to the device (RX).
# This characteristic should have 'write' or 'write without response' properties.
WRITE_CHARACTERISTIC_UUID = "0000FFE1-0000-1000-8000-00805F9B34FB"

# The Characteristic UUID to *read* data from the device (TX).
READ_CHARACTERISTIC_UUID = "0000FFE1-0000-1000-8000-00805F9B34FB"


# Asynchronous RoboticGloveController Class
class RoboticGloveController:
    def __init__(self, device_address: str):
        self.device_address = device_address
        self.client: BleakClient = None
        self.is_connected = False
        self.write_char_object = None
        self.read_char_object = None

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

            # Find service using UART_SERVICE_UUID
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

                if str(char.uuid).upper() == READ_CHARACTERISTIC_UUID.upper():
                    self.read_char_object = char
                    print(f"Found read characteristic object: {self.read_char_object.uuid} (Handle: {self.read_char_object.handle})")

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

    async def read_data(self):
        """
        Reads data from the read characteristic.
        """
        if not self.is_connected or not self.read_char_object:
            print("Cannot read: Not connected or read characteristic not found.")
            return

        try:
            data = await self.client.read_gatt_char(self.read_char_object)
            # or parse/struct unpack if needed
            decoded = data.decode("utf-8", errors="ignore")
            return decoded
        except Exception as e:
            print(f"Error reading from characteristic: {e}")
            return None

    async def _send_command(self, user_input: str):
        """
        Sends a command to the Arduino over BLE.
        """
        if not self.is_connected or not self.client:
            print("Not connected to BLE device. Cannot send command.")
            return

        if not user_input.endswith("$"):
            user_input += "$"

        try:
            # Write to the characteristic. Use write_gatt_char for sending data.
            # 'response=True' means it expects a confirmation from the device (slower but reliable).
            # 'response=False' means 'write without response' (faster, less reliable).
            await self.client.write_gatt_char(self.write_char_object,
                                              user_input.encode("utf-8"),
                                              response=False)

        except Exception as e:
            print(f"Error sending command '{user_input}' over BLE: {e}")

    async def set_all_servos_batch(self, angles: list[int]):
        """
        Sets all servos in a single, efficient batch command, as suggested.
        Expects a list of 5 angles [Thumb, Index, Middle, Ring, Little].
        Constructs a command like "A90$B30$C0$D45$E180$"
        """
        if len(angles) != 5:
            print(f"ERROR: set_all_servos_batch requires a list of 5 angles. Got {len(angles)}.")
            return

        servo_chars = ['A', 'B', 'C', 'D', 'E']
        command_parts = []
        for i, angle in enumerate(angles):
            clamped_angle = max(0, min(180, angle))
            command_parts.append(f"{servo_chars[i]}{clamped_angle}$")

        final_command = "".join(command_parts)
        print(final_command)
        await self._send_command(final_command)

    async def set_servo_angle(self, servo_index: int, angle: int):
        """
        Sets the angle for a specific servo.
        :param servo_index: The index of the servo (0-4 for Thumb to Little).
        :param angle: The desired angle (0-180 degrees).
        """
        if not 0 <= servo_index <= 5:
            print(f"ERROR: Servo index {servo_index} must be between 0 and 5.")
            return
        if not 0 <= angle <= 180:
            print(f"WARNING: Angle {angle} is outside 0-180. Clamping.")
            angle = max(0, min(180, angle))

        # The command character 'A' corresponds to servo 0, 'B' to 1, etc.
        command_char = chr(ord('A') + servo_index)
        # The command is the character followed by the angle, e.g., "A90" or "C180".
        command_string = f"{command_char}{angle}"
        await self._send_command(command_string)

    async def set_all_servos_angle(self, angle: int):
        """
        Sets all finger servos to a specific angle.
        :param angle: The desired angle (0-180 degrees).
        """
        for i in range(5):
            await self.set_servo_angle(i, angle)
            print(f"Set all servos to {angle} degrees.")

    @staticmethod
    async def discover_devices_async(name):
        """
        Helper function for discovering devices
        """
        print("Scanning for BLE devices...")
        # Scan for 5 seconds
        device = await BleakScanner.find_device_by_name(name, timeout=5.0)

        if not device:
            print(f"No BLE device with name {name} found.")
            return

        print(f"Device {name} found.")
        return device
