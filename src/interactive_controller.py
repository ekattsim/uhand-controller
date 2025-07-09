import asyncio
from glove_controller import RoboticGloveController, DEVICE_ADDRESS


async def main():
    print("--- Discovering BLE Devices ---")
    device = await RoboticGloveController.discover_devices_async("Hiwonder")
    print("\n--- Discovery Complete ---")

    controller = RoboticGloveController(device) if device else RoboticGloveController(DEVICE_ADDRESS)

    if await controller.connect():
        try:
            print("\n--- Interactive Mode ---")
            print("Type a command character and value (e.g., A90), or 'q' to quit.")
            while True:
                user_input = input("Command: ").strip()

                if user_input.lower() == 'q':
                    break

                await controller._send_command(user_input)

                await asyncio.sleep(0.05)
                message = await controller.read_data()

                print(f"Received (BLE): {message}")

        except KeyboardInterrupt:
            print("\nExiting program.")
        finally:
            await controller.disconnect()
    else:
        print("Could not connect to Robotic Glove. Exiting.")

if __name__ == "__main__":
    asyncio.run(main())
