import time
import random
import threading
import queue
import librosa
import pygame
import cozmo
import anki_vector
import asyncio

_orig_gather = asyncio.gather
def _patched_gather(*args, **kwargs):
    kwargs.pop('loop', None)
    return _orig_gather(*args, **kwargs)
asyncio.gather = _patched_gather

_orig_sleep = asyncio.sleep
def _patched_sleep(*args, **kwargs):
    kwargs.pop('loop', None)
    return _orig_sleep(*args, **kwargs)
asyncio.sleep = _patched_sleep

_orig_wait = asyncio.wait
def _patched_wait(*args, **kwargs):
    kwargs.pop('loop', None)
    return _orig_wait(*args, **kwargs)
asyncio.wait = _patched_wait

_orig_wait_for = asyncio.wait_for
def _patched_wait_for(*args, **kwargs):
    kwargs.pop('loop', None)
    return _orig_wait_for(*args, **kwargs)
asyncio.wait_for = _patched_wait_for

cozmo_magenta = cozmo.lights.Light(cozmo.lights.Color(rgb=(255, 0, 255)))
cozmo_cyan = cozmo.lights.Light(cozmo.lights.Color(rgb=(0, 255, 255)))

COZMO_COLORS = [
    cozmo.lights.red_light, 
    cozmo.lights.green_light, 
    cozmo.lights.blue_light, 
    cozmo_magenta, 
    cozmo_cyan
]

VECTOR_COLORS = [
    anki_vector.lights.red_light, 
    anki_vector.lights.green_light, 
    anki_vector.lights.blue_light, 
    anki_vector.lights.magenta_light, 
    anki_vector.lights.cyan_light
]

SONG_PATH = "song.flac"

vector_command_queue = queue.Queue()

DANCE_MOVES = [
    "step_left",   
    "step_right", 
    "head_bop",  
    "back_it_up"
]

def vector_worker():
    """Runs completely isolated in a background thread."""
    try:
        with anki_vector.Robot() as vec_robot:
            print("✅ Vector connected!")
            
            if vec_robot.status.is_on_charger:
                print("  - Vector is on his charger! Driving off so he can move...")
                vec_robot.behavior.drive_off_charger()
            
            try:
                vec_robot.world.connect_cube()
                vec_cube = vec_robot.world.connected_light_cube
                if vec_cube:
                    print("  - Vector cube found and synced.")
                else:
                    print("  - Vector cube not found. (Make sure it has a battery)")
            except Exception as e:
                print(f"  - Vector cube warning: {e}")
                vec_cube = None

            while True:
                cmd = vector_command_queue.get()
                
                if cmd["action"] == "quit":
                    break
                    
                elif cmd["action"] == "stop":
                    #If a new beat is already queued, skip stopping
                    if not vector_command_queue.empty():
                        continue 
                        
                    try:
                        # Only stop motors if it's safe
                        if not vec_robot.status.is_picked_up and not vec_robot.status.is_cliff_detected:
                            vec_robot.motors.set_wheel_motors(0, 0)
                            vec_robot.motors.set_lift_motor(0)
                            vec_robot.motors.set_head_motor(0)
                        if vec_cube:
                            vec_cube.set_lights_off()
                    except Exception:
                        pass
                        
                elif cmd["action"] == "move":
                    move_type = cmd["type"]
                    color_idx = cmd["color"]
                    
                    try:
                        # Skip motors if picked up or on a cliff to prevent thread freezing
                        is_safe = not vec_robot.status.is_picked_up and not vec_robot.status.is_cliff_detected
                        
                        if is_safe:
                            if move_type == "step_left":
                                vec_robot.motors.set_wheel_motors(-200, 200)
                                vec_robot.motors.set_lift_motor(5.0)
                            elif move_type == "step_right":
                                vec_robot.motors.set_wheel_motors(200, -200)
                                vec_robot.motors.set_lift_motor(-5.0)
                            elif move_type == "head_bop":
                                vec_robot.motors.set_wheel_motors(150, 150)
                                vec_robot.motors.set_head_motor(-5.0)
                            elif move_type == "back_it_up":
                                vec_robot.motors.set_wheel_motors(-150, -150)
                                vec_robot.motors.set_head_motor(5.0)
                                
                        # Always flash the cube regardless of cliffs/picked up status
                        if vec_cube:
                            vec_cube.set_lights(VECTOR_COLORS[color_idx])
                    except Exception:
                        pass
    except Exception as e:
        print(f"❌ Vector background thread encountered an error: {e}")


def main_dance_loop(coz_robot: cozmo.robot.Robot):
    """The central runtime managed by Cozmo. It handles audio and directs Vector."""
    print("🤖 Cozmo connected!")
    
    print("\n🔌 Connecting to Vector via Wirepod (Background Thread)...")
    v_thread = threading.Thread(target=vector_worker, daemon=True)
    v_thread.start()
    
    time.sleep(5) 
    
    print("\n🔍 Looking for Cozmo's cubes...")
    coz_cubes = list(coz_robot.world.light_cubes.values())
    if coz_cubes:
        print(f"  - {len(coz_cubes)} Cozmo cubes) found and synced.")
    else:
        print("  - No Cozmo cubes found.")

    print("\n🎵 Analyzing FLAC audio for beats... (This may take a moment)")
    try:
        y, sr = librosa.load(SONG_PATH)
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beats, sr=sr)
        
        bpm = tempo[0] if isinstance(tempo, (list, tuple, type(y))) else tempo
        print(f"✅ Found {len(beat_times)} beats. Estimated tempo: {bpm:.2f} BPM.")
    except FileNotFoundError:
        print(f"\n❌ Error: Could not find '{SONG_PATH}'.")
        return

    pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=4096)
    pygame.mixer.init()
    pygame.mixer.music.set_volume(1.0) 
    
    try:
        pygame.mixer.music.load(SONG_PATH)
    except pygame.error as e:
        print(f"\n❌ Pygame Audio Error: {e}")
        return

    print("\n🚀 Starting the Rave!")
    time.sleep(1) 
    pygame.mixer.music.play()
    time.sleep(0.5) 
    start_time = time.time()

    for i, beat_time in enumerate(beat_times):
        
        current_playback_time = time.time() - start_time
        time_to_wait = beat_time - current_playback_time

        if time_to_wait > 0:
            time.sleep(time_to_wait)

        if i < len(beat_times) - 1:
            time_to_next_beat = beat_times[i+1] - beat_times[i]
            move_duration = min(0.7, time_to_next_beat * 0.90)
        else:
            move_duration = 0.5

        # Generate choreo
        move_type = DANCE_MOVES[i % len(DANCE_MOVES)] 
        
        while not vector_command_queue.empty():
            try:
                vector_command_queue.get_nowait()
            except queue.Empty:
                break
                
        vector_command_queue.put({
            "action": "move", 
            "type": move_type, 
            "color": random.randint(0, len(VECTOR_COLORS) - 1)
        })
        
        try:
            if move_type == "step_left":
                coz_robot.drive_wheels(-200, 200)
                coz_robot.move_lift(5.0)
            elif move_type == "step_right":
                coz_robot.drive_wheels(200, -200)
                coz_robot.move_lift(-5.0)
            elif move_type == "head_bop":
                coz_robot.drive_wheels(150, 150)
                coz_robot.move_head(-5.0)
            elif move_type == "back_it_up":
                coz_robot.drive_wheels(-150, -150)
                coz_robot.move_head(5.0)

            for cube in coz_cubes:
                cube.set_lights(COZMO_COLORS[random.randint(0, len(COZMO_COLORS) - 1)])
        except Exception:
            pass

        # Stop both robots based on the dynamic duration
        def stop_bots():
            vector_command_queue.put({"action": "stop"})
            try:
                coz_robot.drive_wheels(0, 0)
                coz_robot.move_lift(0)
                coz_robot.move_head(0)
                for cube in coz_cubes:
                    cube.set_lights_off()
            except Exception:
                pass
                
        threading.Timer(move_duration, stop_bots).start()

    while pygame.mixer.music.get_busy():
        time.sleep(1)

    print("\nParty's over.")
    vector_command_queue.put({"action": "quit"})
    time.sleep(1)

if __name__ == '__main__':
    try:
        cozmo.run_program(main_dance_loop)
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        vector_command_queue.put({"action": "quit"})