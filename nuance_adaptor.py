import json
import time
import pygame
import asyncio
from pprint import pprint
from nuance import NuanceClient

CONTEXT = 'Project766_App363'

class Nuance:

    def __init__(self, cred_file):
        with open(cred_file,'r') as f:
            cred = json.load(f)
        self.client = NuanceClient(cred)

    def say(self, what, sr=44100):
        return self.client.synthesize(what, sr)

    def get_intent(self, context=CONTEXT):
        r = self.client.understand(context)
        if not r:
            return None
        else:
            return self._parse_intent(r['payload']['interpretations'][0])

    def _parse_intent(self, raw):
        if 'concepts' not in raw:
            return None
        intent = raw['action']['intent']['value']
        concepts = {}
        for concept,value in raw['concepts'].items():
            concepts[concept] = value[0]['value']
        return {'intent': intent, 'concepts': concepts}


def main():
    mode = 'understand'
    n = Nuance('credentials.json')
    if mode == 'understand':
        r = n.get_intent(context)
        pprint(r)
    elif mode == 'synthesize':
        pygame.mixer.init(44100, channels=1)
        s = n.say("hi there hello hello we are at wearhacks doing a nuance application")
        pygame.mixer.Sound(buffer=s).play()
        time.sleep(len(s)/(sr*2))
        print('finished')
    else:
        print('mode not recognized')


if __name__ == '__main__':
    main()

