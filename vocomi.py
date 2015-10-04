import pygame
import os
import myo as libmyo
import nuance_adaptor; nuance = nuance_adaptor.Nuance('credentials.json'); nuance.log = True
import time
import sys
import random

os.nice(20)


sayings = {}
def say(what):
    if what in sayings:
        sayings['what'].play()
        time.sleep(sayings['what'].get_length())
    else:
        b = nuance.say(what, 44100)
        s = pygame.mixer.Sound(buffer=b)
        sayings['what'] = s
        s.play()
        time.sleep(s.get_length())


class MyoListener(libmyo.DeviceListener):
    """
    MyoListener implementation. Return False from any function to
    stop the Hub.
    Only works with a single Myo
    """

    def __init__(self):
        super(MyoListener, self).__init__()
        self.pose = None
        self.locked = False

    def on_connect(self, myo, timestamp, firmware_version):
        self.myo = myo
        myo.vibrate('short')
        myo.vibrate('short')

    def on_pose(self, myo, timestamp, pose):
        print(pose)
        self.pose = pose


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

    currentState = 0
    currentGroup = []
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
    pygame.mixer.init(44100, channels=1)
    sounds = {
        'random': [
            pygame.mixer.Sound('assets/samples/random/pad.wav'),
            pygame.mixer.Sound('assets/samples/random/candy.wav'),
            pygame.mixer.Sound('assets/samples/random/dubstep.wav')
        ],
        'guitar': [
            pygame.mixer.Sound('assets/samples/guitar/guitar.wav'),
            pygame.mixer.Sound('assets/samples/guitar/guitar_short.wav'),
            pygame.mixer.Sound('assets/samples/guitar/guitar_distort.wav')
        ],
        'drums': [
            pygame.mixer.Sound('assets/samples/drum/kick/kick2.wav'),
            pygame.mixer.Sound('assets/samples/drum/kick/kick.wav')
        ]
    }
    State.currentGroup = sounds['random']
    time.sleep(1)
    say("Welcome to VoCoMi")
    """ Main loop """
    bpm = 280.0
    period = (60.0/bpm) * 1000
    try:
        while hub.running:
            #
            # LISTENING for instructions
            #
            if State.currentState == State.LISTENING:
                #try:
                    say("What would you like me to do?")
                    intent = nuance.get_intent()
                    if not intent:
                        continue
                    elif intent['intent'] == 'Exit':
                        break
                    elif intent['intent'] == 'Clear':
                        print("clear score")
                        State.score = [[] for x in range(NBEATS)]
                        say("Your mix has been cleared. What should we do next?")
                    elif intent['intent'] == 'List_options':
                        print("list options")
                        #if 'Instruments' in intent['concepts']:
                        #    options = sounds[intent['concepts']['Instruments']].keys()
                        #else:
                        options = list(sounds.keys())
                        last_option = options[-1]
                        other_options = ','.join(options[:-1])
                        say("We currently have %s and %s samples in our database." % (other_options, last_option))
                    elif intent['intent'] == 'Modify_instrument_track':
                        #say("Please, be more specific. Which %s sample do you want?" % intent['concepts']['Instruments'])
                        if 'Instruments' not in intent['concepts']:
                            pass
                        instrument = intent['concepts']['Instruments']
                        State.currentGroup = sounds[instrument] # fill with selection
                        State.currentSample = random.randint(0, len(State.currentGroup)-1)
                        State.currentState = State.BROWSING
                        say("You can now browse %s samples by waving your hand. How about this one?" % instrument)
                        State.currentGroup[State.currentSample].play()
                    elif intent['intent'] == 'Select_drum_track':
                        pass
                    elif intent['intent'] == 'Select_guitar_chord':
                        pass
                    elif intent['intent'] == 'Select_voice_track':
                        pass
                    elif intent['intent'] == 'Set_and_modify':
                        pass
                #except:
                #    pass
            #
            # BROWSE sounds
            #
            elif State.currentState == State.BROWSING:
                if myo.pose == libmyo.Pose.wave_in:
                    myo.pose = None
                    print("next sample")
                    myo.myo.vibrate('short')
                    State.currentSample += 1
                    while State.currentSample >= len(State.currentGroup):
                        State.currentSample -= len(State.currentGroup)
                    pygame.mixer.stop()
                    State.currentGroup[State.currentSample].play()
                elif myo.pose == libmyo.Pose.wave_out:
                    myo.pose = None
                    print("previous sample")
                    myo.myo.vibrate('short')
                    pygame.mixer.stop()
                    State.currentSample -= 1; # mod nSamples for current group
                    while State.currentSample < 0:
                        State.currentSample += len(State.currentGroup)
                    State.currentGroup[State.currentSample].play()
                elif myo.pose == libmyo.Pose.fist:
                    myo.pose = None
                    print("start playback")
                    State.currentBeat = 0
                    myo.myo.vibrate('medium')
                    pygame.mixer.stop()
                    State.currentState = State.PLAYING
                else:
                    pass
            #
            # PLAY stuff
            #
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
                    print("add note")
                    myo.myo.vibrate('short')
                    s = State.currentGroup[State.currentSample]
                    State.score[State.currentBeat].append(s)
                elif myo.pose == libmyo.Pose.double_tap:
                    myo.pose = None
                    print("play note")
                    myo.myo.vibrate('short')
                    State.currentGroup[State.currentSample].play()
                elif myo.pose == libmyo.Pose.fist:
                    myo.pose = None
                    print("switch note")
                    myo.myo.vibrate('medium')
                    State.currentGroup[State.currentSample].play()
                    pygame.mixer.stop()
                    State.currentState = State.LISTENING
                else:
                    pass
            else:
                pass
    finally:
        print("Shutting down...")
        say("Thank you for using our demo. Vocomi is powered by Nuance speech technologies and the Myo armband.")
        hub.shutdown()
        pygame.quit()


if __name__ == "__main__":
    main()

