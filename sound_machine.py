import pygame
import os
import myo as libmyo
import time
import sys

os.nice(20)

class MyoListener(libmyo.DeviceListener):
    """
    MyoListener implementation. Return False from any function to
    stop the Hub.
    """

    def __init__(self):
        super(MyoListener, self).__init__()
        self.orientation = None
        self.pose = None
        self.emg_enabled = False
        self.locked = False
        self.rssi = None
        self.emg = None

    def on_connect(self, myo, timestamp, firmware_version):
        self.myo = myo
        myo.vibrate('short')
        myo.vibrate('short')
        myo.request_rssi()
        myo.request_battery_level()

    def on_rssi(self, myo, timestamp, rssi):
        self.rssi = rssi

    def on_pose(self, myo, timestamp, pose):
        print pose
        self.pose = pose

    def on_orientation_data(self, myo, timestamp, orientation):
        self.orientation = orientation

    def on_accelerometor_data(self, myo, timestamp, acceleration):
        pass

    def on_gyroscope_data(self, myo, timestamp, gyroscope):
        pass

    def on_emg_data(self, myo, timestamp, emg):
        self.emg = emg

    def on_unlock(self, myo, timestamp):
        self.locked = False

    def on_lock(self, myo, timestamp):
        self.locked = True

    def on_event(self, kind, event):
        """
        Called before any of the event callbacks.
        """

    def on_event_finished(self, kind, event):
        """
        Called after the respective event callbacks have been
        invoked. This method is *always* triggered, even if one of
        the callbacks requested the stop of the Hub.
        """

    def on_pair(self, myo, timestamp, firmware_version):
        """
        Called when a Myo armband is paired.
        """

    def on_unpair(self, myo, timestamp):
        """
        Called when a Myo armband is unpaired.
        """

    def on_disconnect(self, myo, timestamp):
        """
        Called when a Myo is disconnected.
        """

    def on_arm_sync(self, myo, timestamp, arm, x_direction, rotation,
                    warmup_state):
        """
        Called when a Myo armband and an arm is synced.
        """

    def on_arm_unsync(self, myo, timestamp):
        """
        Called when a Myo armband and an arm is unsynced.
        """

    def on_battery_level_received(self, myo, timestamp, level):
        """
        Called when the requested battery level received.
        """

    def on_warmup_completed(self, myo, timestamp, warmup_result):
        """
        Called when the warmup completed.
        """


_sound_library = {}
def play_sound(path):
    global _sound_library
    sound = _sound_library.get(path)
    if sound == None:
        canonicalized_path = path.replace('/', os.sep).replace('\\', os.sep)
        sound = pygame.mixer.Sound(canonicalized_path)
        _sound_library[path] = sound
    sound.play()


NBEATS = 8

class State():
    LISTENING = 0
    BROWSING = 1
    PLAYING = 2

    currentState = 2
    currentGroup = 0
    currentSample = 0
    currentBeat = 0
    lastTime = round(time.time() * 1000.0)
    score = [[] for x in range(NBEATS)]


def main():
    """ MYO init """
    libmyo.init()
    print("Connecting to Myo ... Use CTRL^C to exit.")
    hub = libmyo.Hub()
    hub.set_locking_policy(libmyo.LockingPolicy.none)
    myo = MyoListener()
    hub.run(1000, myo)
    """ Audio engine init """
    pygame.mixer.pre_init(44100)
    pygame.mixer.init()
    #play_sound('assets/voice.wav')
    sounds = [[
        pygame.mixer.Sound('assets/kick2.wav'),
        pygame.mixer.Sound('assets/pad.wav'),
        pygame.mixer.Sound('assets/candy.wav'),
        pygame.mixer.Sound('assets/guitar.wav'),
        pygame.mixer.Sound('assets/guitar_short.wav'),
        pygame.mixer.Sound('assets/guitar_distort.wav'),
        pygame.mixer.Sound('assets/dubstep.wav'),
    ]]
    #State.score[0].append(kick_sound)
    #State.score[1].append(kick_sound)
    #State.score[2].append(kick_sound)
    #State.score[3].append(kick_sound)
    #State.score[4].append(kick_sound)
    #State.score[5].append(kick_sound)
    #State.score[6].append(kick_sound)
    #State.score[7].append(kick_sound)
    """ Main loop """
    bpm = 280.0
    period = (60.0/bpm) * 1000
    try:
        while hub.running:
            if State.currentState == State.LISTENING:
                # get audio input, send to nuance, get sample
                # we can block if needed, probably
                gotIntent = False
                if gotIntent:
                    State.currentGroup = 0 # fill with selection
                    State.currentSample = 0
                    sounds[State.currentGroup][State.currentSample]
                    State.currentState = State.BROWSING
            elif State.currentState == State.BROWSING:
                if myo.pose == libmyo.Pose.wave_in:
                    myo.pose = None
                    print "next sample"
                    myo.myo.vibrate('short')
                    State.currentSample += 1
                    while State.currentSample >= len(sounds[State.currentGroup]):
                        State.currentSample -= len(sounds[State.currentGroup])
                    pygame.mixer.stop()
                    sounds[State.currentGroup][State.currentSample].play()
                elif myo.pose == libmyo.Pose.wave_out:
                    myo.pose = None
                    print "previous sample"
                    myo.myo.vibrate('short')
                    pygame.mixer.stop()
                    State.currentSample -= 1; # mod nSamples for current group
                    while State.currentSample < 0:
                        State.currentSample += len(sounds[State.currentGroup])
                    sounds[State.currentGroup][State.currentSample].play()
                elif myo.pose == libmyo.Pose.fist:
                    myo.pose = None
                    print "start playback"
                    State.currentBeat = 0
                    myo.myo.vibrate('long')
                    pygame.mixer.stop()
                    State.currentState = State.PLAYING
                else:
                    pass
            elif State.currentState == State.PLAYING:
                currentTime = int(time.time() * 1000.0)
                delta = currentTime - State.lastTime;
                if delta > period:
                    for s in State.score[State.currentBeat]:
                        s.play()
                    State.lastTime = currentTime
                    State.currentBeat += 1
                    if State.currentBeat == NBEATS:
                        State.currentBeat = 0
                """Check play gesture"""
                if myo.pose == libmyo.Pose.fingers_spread:
                    myo.pose = None
                    print "add note"
                    myo.myo.vibrate('short')
                    s = sounds[State.currentGroup][State.currentSample]
                    State.score[State.currentBeat].append(s)
                elif myo.pose == libmyo.Pose.double_tap:
                    myo.pose = None
                    print "play note"
                    myo.myo.vibrate('short')
                    sounds[State.currentGroup][State.currentSample].play()
                elif myo.pose == libmyo.Pose.fist:
                    myo.pose = None
                    print "switch note"
                    myo.myo.vibrate('long')
                    sounds[State.currentGroup][State.currentSample].play()
                    pygame.mixer.stop()
                    State.currentState = State.BROWSING
                else:
                    pass
            else:
                pass
    finally:
        print("Shutting down...")
        hub.shutdown()
        pygame.quit()


if __name__ == "__main__":
    main()

