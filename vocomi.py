import pygame
import os
import samplebank
import myo as libmyo
import nuance_adaptor
import time
import sys
import random

# Edit me!
NBEATS = 8
BPM = 120
INPUT_DEVICE = 0


# High priority to get good audio timing
os.nice(20)

"""
Do before execution 
export DYLD_LIBRARY_PATH=$DYLD_LIBRARY_PATH:$(pwd)/myo-sdk/myo.framework
"""

# Our nuance worker
nuance = nuance_adaptor.Nuance('credentials.json', INPUT_DEVICE)

# Read a sentence with TTS. Keep an infinite local cache
sayings = {}

def say(what):
    if what in sayings:
        sayings[what].play()
        time.sleep(sayings[what].get_length())
    else:
        b = nuance.say(what, 44100)
        print(what)
        s = pygame.mixer.Sound(buffer=b)
        sayings[what] = s
        say(what)


class MyoListener(libmyo.DeviceListener):
    """
    MyoListener implementation. Return False from any function to
    stop the Hub.
    Only works with a single Myo
    """

    def __init__(self):
        super(MyoListener, self).__init__()
        self.pose = None

    def on_connect(self, myo, timestamp, firmware_version):
        self.myo = myo # That's why it only works with a single Myo
        myo.vibrate('short')
        myo.vibrate('short')

    def on_pose(self, myo, timestamp, pose):
        print(pose)
        self.pose = pose


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
    sounds = samplebank.load_samples(pygame.mixer)
    State.currentGroup = sounds['single']['random']
    time.sleep(1)
    say("Welcome to VoCoMi")
    """ Main loop """
    period = (60.0/BPM) * 1000
    try:
        while hub.running:
            #
            # LISTENING for instructions
            #
            if State.currentState == State.LISTENING:
                try:
                    say(random.choice([
                        "What would you like me to do?",
                        "What should we do next?"
                    ]))
                    intent = nuance.get_intent()
                    print(intent)
                    if not intent:
                        continue
                    elif intent['intent'] == 'Exit':
                        break
                    elif intent['intent'] == 'Clear':
                        print("clear score")
                        State.score = [[] for x in range(NBEATS)]
                        say("Your mix has been cleared.")
                    elif intent['intent'] == 'List_options':
                        print("list options")
                        if 'concepts' in intent and 'Instruments' in intent['concepts'] and intent['concepts']['Instruments'] in sounds['double'] :
                            options = list(sounds['double'][intent['concepts']['Instruments']].keys())
                        else:
                            options = list(sounds['single'].keys()) + list(sounds['double'].keys())
                        last_option = options[-1]
                        other_options = ','.join(options[:-1])
                        say("We currently have %s, and %s samples in our database." % (other_options, last_option))
                    elif intent['intent'] == 'Modify_instrument_track':
                        if 'concepts' not in intent or 'Instruments' not in intent['concepts']:
                            continue
                        instrument = intent['concepts']['Instruments']
                        if instrument in sounds['double']:
                            say("Please, be more specific. Which %s sample do you want?" % instrument)
                        else:
                            State.currentGroup = sounds['single'][instrument] # fill with selection
                            State.currentSample = random.randint(0, len(State.currentGroup)-1)
                            State.currentState = State.BROWSING
                            say("You can now browse the %d %s samples by waving your hand. How about this one?" % (len(State.currentGroup), instrument))
                            State.currentGroup[State.currentSample].play()
                    elif intent['intent'] == 'Select_drum_track':
                        if 'concepts' not in intent or 'Drum_track' not in intent['concepts'] or len(intent['concepts']['Drum_track']) == 0:
                            continue
                        instrument = intent['concepts']['Drum_track']
                        State.currentGroup = sounds['double']['drums'][instrument]
                        State.currentSample = random.randint(0, len(State.currentGroup)-1)
                        State.currentState = State.BROWSING
                        say("You can now browse the %d %s drum samples by waving your hand. How about this one?" % (len(State.currentGroup), instrument))
                        State.currentGroup[State.currentSample].play()
                    elif intent['intent'] == 'Select_voice_track':
                        if 'concepts' not in intent or 'Voice_track' not in intent['concepts'] or len(intent['concepts']['Voice_track']) == 0:
                            continue
                        instrument = intent['concepts']['Voice_track']
                        State.currentGroup = sounds['double']['voice'][instrument] # fill with selection
                        State.currentSample = random.randint(0, len(State.currentGroup)-1)
                        State.currentState = State.BROWSING
                        say("You can now browse the %d %s voice samples by waving your hand. How about this one?" % (len(State.currentGroup), instrument))
                        State.currentGroup[State.currentSample].play()
                    elif intent['intent'] == 'Set_and_modify':
                        if 'concepts' not in intent or 'Instruments' not in intent['concepts']:
                            continue
                        instrument = intent['concepts']['Instruments']
                        if instrument in sounds['single']:
                            State.currentGroup = sounds['single'][instrument]
                        elif instrument in sounds['double']:
                            if instrument == 'drums' and 'Drum_track' in intent['concepts'] and not intent['concepts']['Drum_track'] == {}:
                                State.currentGroup = sounds['double'][instrument][intent['concepts']['Drum_track']]
                                instrument = '%s drums' % intent['concepts']['Drum_track']
                            elif instrument == 'voice' and 'Voice_track' in intent['concepts']:
                                State.currentGroup = sounds['double'][instrument][intent['concepts']['Voice_track']]
                                instrument = '%s voice' % intent['concepts']['Voice_track']
                            else:
                                say("Please, be more specific. Which %s sample do you want?" % instrument)
                        else:
                            continue
                        State.currentSample = random.randint(0, len(State.currentGroup)-1)
                        State.currentState = State.BROWSING
                        say("You can now browse the %d %s samples by waving your hand. How about this one?" % (len(State.currentGroup), instrument))
                        State.currentGroup[State.currentSample].play()
                    elif intent['intent'] == 'Playback':
                        State.currentState = State.PLAYING
                    elif intent['intent'] == 'YesNo':
                        if 'concepts' not in intent or 'Instruments' not in intent['concepts']: 
                            say("No, sorry. Currently this instument is not in our database.")
                        elif 'Instruments' in intent['concepts']:
                            say("Yes")
                except:
                    say("Ups, something crashed.")
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

