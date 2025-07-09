import asyncio
import pandas as pd
from glove_controller import RoboticGloveController, DEVICE_ADDRESS

# configuration
CSV_FILE = 'test1-copy.csv'
SAMPLE_RATE = 1

TIME_COLUMN = ('Unnamed: 0_level_0', 'delta time (s)')
FINGER_COLUMNS = [
    ('Glove 1 Scaled', 'Thumb'),
    ('Glove 1 Scaled', 'Index'),
    ('Glove 1 Scaled', 'Middle'),
    ('Glove 1 Scaled', 'Ring'),
    ('Glove 1 Scaled', 'Little')
]


async def main():
    """
    Main function to load CSV data and control the glove.
    """
    print(f"Loading glove recording from: {CSV_FILE}")
    print(f"Movement commands will be sent every {SAMPLE_RATE} samples.")

    try:
        df = pd.read_csv(CSV_FILE, header=[1, 2])
    except Exception as e:
        print(f"ERROR: Could not read or parse the CSV file: {e}")
        return

    print("CSV data loaded successfully.")

    glove = RoboticGloveController(DEVICE_ADDRESS)

    try:
        await glove.connect()
        if not glove.is_connected:
            print("Failed to connect to the glove. Exiting.")
            return

        print("\n--- Starting Glove Replay ---")
        input("Press Enter to begin the movement sequence...")

        time_to_wait = 0.0
        total_elapsed_time = 0.0

        for index, row in df.iterrows():
            # accumulate the time from every sample for accurate playback speed
            delta_time = row[TIME_COLUMN]
            time_to_wait += delta_time
            total_elapsed_time += delta_time

            # The first sample (index 0) will always be sent.
            if index % SAMPLE_RATE == 0:
                angles = []
                for col_name_tuple in FINGER_COLUMNS:
                    scaled_value = row[col_name_tuple]
                    angle = int(scaled_value * 180)
                    angles.append(max(0, min(180, angle)))

                # Send the batch command with the angles from the current (Nth) sample
                await glove.set_all_servos_batch(angles)

                # Update and display status
                angles_str = ", ".join(map(str, angles))
                print(f"Time: {total_elapsed_time:6.2f}s | Angles: [{angles_str}] | Waiting: {time_to_wait:.4f}s ({SAMPLE_RATE} samples)")

                # Wait for the accumulated time of the last N samples
                await asyncio.sleep(time_to_wait)

                # Reset the timer for the next batch of samples
                time_to_wait = 0.0

        print("\n--- Replay Finished ---")
        print("Resetting servos to open position (0 degrees).")
        await glove.set_all_servos_batch([0, 0, 0, 0, 0])

    except asyncio.CancelledError:
        print("\nReplay cancelled (Ctrl+C).")
    except Exception as e:
        print(f"\nAn error occurred during replay: {e}")
    finally:
        if glove and glove.is_connected:
            print("Disconnecting from glove...")
            await glove.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated.")
