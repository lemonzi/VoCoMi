import base64
import binascii
import datetime
import email.utils
import hashlib
import hmac
import json
import os
import pprint
import struct
import sys
import urllib.parse
import uuid
import wave

import asyncio

import aiohttp
from aiohttp import websocket

import pyaudio
import speex

WS_KEY = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WebsocketConnection:
    MSG_JSON = 1
    MSG_AUDIO = 2

    @asyncio.coroutine
    def connect(self, url, app_id, app_key, use_plaintext=True):
        date = datetime.datetime.utcnow()
        sec_key = base64.b64encode(os.urandom(16))

        if use_plaintext:
            params = {'app_id': app_id, 'algorithm': 'key', 'app_key': binascii.hexlify(app_key)}
        else:
            datestr = date.replace(microsecond=0).isoformat()
            params = {
                'date': datestr,
                'app_id': app_id,
                'algorithm': 'HMAC-SHA-256',
                'signature': hmac.new(app_key,datestr.encode('ascii')+b' '+app_id.encode('utf-8'),hashlib.sha256).hexdigest()
            }

        response = yield from aiohttp.request(
            'get', url + '?' + urllib.parse.urlencode(params),
            headers={
                'UPGRADE': 'WebSocket',
                'CONNECTION': 'Upgrade',
                'SEC-WEBSOCKET-VERSION': '13',
                'SEC-WEBSOCKET-KEY': sec_key.decode(),
            })

        if response.status == 401 and not use_plaintext:
            if 'Date' in response.headers:
                server_date = email.utils.parsedate_to_datetime(response.headers['Date'])
                if server_date.tzinfo is not None:
                    server_date = (server_date - server_date.utcoffset()).replace(tzinfo=None)
            else:
                server_date = yield from response.read()
                server_date = datetime.datetime.strptime(server_date[:19].decode('ascii'), "%Y-%m-%dT%H:%M:%S")

            # Use delta on future requests
            date_delta = server_date - date

            print("Retrying authorization (delta=%s)" % date_delta)

            datestr = (date+date_delta).replace(microsecond=0).isoformat()
            params = {
                'date': datestr,
                'algorithm': 'HMAC-SHA-256',
                'app_id': app_id,
                'signature': hmac.new(app_key,datestr.encode('ascii')+b' '+app_id.encode('utf-8'),hashlib.sha256).hexdigest()
            }

            response = yield from aiohttp.request(
                'get', url + '?' + urllib.parse.urlencode(params),
                headers={
                    'UPGRADE': 'WebSocket',
                    'CONNECTION': 'Upgrade',
                    'SEC-WEBSOCKET-VERSION': '13',
                    'SEC-WEBSOCKET-KEY': sec_key.decode(),
                })

        if response.status != 101:
            info = "%s %s\n" % (response.status, response.reason)
            for (k,v) in response.headers.items():
                info += '%s: %s\n' % (k,v)
            info += '\n%s' % (yield from response.read()).decode('utf-8')

            if response.status == 401:
                raise RuntimeError("Authorization failure:\n%s" % info)
            elif response.status >= 500 and response.status < 600:
                raise RuntimeError("Server error:\n%s" %  info)
            elif response.headers.get('upgrade', '').lower() != 'websocket':
                raise ValueError("Handshake error - Invalid upgrade header")
            elif response.headers.get('connection', '').lower() != 'upgrade':
                raise ValueError("Handshake error - Invalid connection header")
            else:
                raise ValueError("Handshake error: Invalid response status:\n%s" % info)

        key = response.headers.get('sec-websocket-accept', '').encode()
        match = base64.b64encode(hashlib.sha1(sec_key + WS_KEY).digest())
        if key != match:
            raise ValueError("Handshake error - Invalid challenge response")

        # switch to websocket protocol
        self.connection = response.connection
        self.stream = self.connection.reader.set_parser(websocket.WebSocketParser)
        self.writer = websocket.WebSocketWriter(self.connection.writer)
        self.response = response

    @asyncio.coroutine
    def receive(self):
        wsmsg = yield from self.stream.read()
        if wsmsg.tp == 1:
            return (self.MSG_JSON, json.loads(wsmsg.data))
        else:
            return (self.MSG_AUDIO, wsmsg.data)

    def send_message(self, msg):
        _log(msg,sending=True)
        self.writer.send(json.dumps(msg))

    def send_audio(self, audio):
        self.writer.send(audio, binary=True)

    def close(self):
        self.writer.close()
        self.response.close()
        self.connection.close()


def _log(obj,sending=False):
    return
    print('>>>>' if sending else '<<<<')
    print('%s' % datetime.datetime.now())
    pprint.pprint(obj)
    print()


@asyncio.coroutine
def _do_understand_text(loop, url, app_id, app_key, context_tag, text_to_understand, use_speex=None):

    if use_speex is True and speex is None:
        print('ERROR: Speex encoding specified but python-speex module unavailable')
        return

    if use_speex is not False and speex is not None:
        audio_type = 'audio/x-speex;mode=wb'
    else:
        audio_type = 'audio/L16;rate=16000'

    client = WebsocketConnection()
    yield from client.connect(url, app_id, app_key)

    client.send_message({
        'message': 'connect',
        'device_id': '55555500000000000000000000000000',
        'codec': audio_type
    })

    tp, msg = yield from client.receive()
    _log(msg) # Should be a connected message

    client.send_message({
        'message': 'query_begin',
        'transaction_id': 123,

        'command': 'NDSP_APP_CMD',
        'language': 'eng-USA',
        'context_tag': context_tag,
    })

    client.send_message({
        'message': 'query_parameter',
        'transaction_id': 123,

        'parameter_name': 'REQUEST_INFO',
        'parameter_type': 'dictionary',

        'dictionary': {
            'application_data': {
                'text_input': text_to_understand,
            }
        }
    })

    client.send_message({
        'message': 'query_end',
        'transaction_id': 123,
    })

    while True:
        tp, msg = yield from client.receive()
        _log(msg)
        if msg['message'] == 'query_end':
            break

    client.close()


@asyncio.coroutine
def _do_audio(loop, url, app_id, app_key, context_tag=None, reco_model=None, recorder=None):

    rate = recorder.rate
    resampler = None

    if rate >= 16000:
        if rate != 16000:
            resampler = speex.SpeexResampler(1, rate, 16000)
        audio_type = 'audio/x-speex;mode=wb'
    else:
        if rate != 8000:
            resampler = speex.SpeexResampler(1, rate, 8000)
        audio_type = 'audio/x-speex;mode=nb'

    client = WebsocketConnection()
    yield from client.connect(url, app_id, app_key)

    client.send_message({
        'message': 'connect',
        'device_id': '55555500000000000000000000000000',
        'codec': audio_type
    })

    tp, msg = yield from client.receive()
    _log(msg) # Should be a connected message

    if context_tag is not None:
        client.send_message({
            'message': 'query_begin',
            'transaction_id': 123,
            'command': 'NDSP_ASR_APP_CMD',
            'language': 'eng-USA',
            'context_tag': context_tag,
        })
    else:
        client.send_message({
            'message': 'query_begin',
            'transaction_id': 123,
            'command': 'NVC_ASR_CMD', #'NDSP_ASR_APP_CMD',
            'language': 'eng-USA',
            'recognition_type': reco_model,
        })

    client.send_message({
        'message': 'query_parameter',
        'transaction_id': 123,
        'parameter_name': 'AUDIO_INFO',
        'parameter_type': 'audio',
        'audio_id': 456
    })

    client.send_message({
        'message': 'query_end',
        'transaction_id': 123,
    })

    client.send_message({
        'message': 'audio',
        'audio_id': 456,
    })

    if audio_type == 'audio/x-speex;mode=wb':
        encoder = speex.WBEncoder()
    else:
        encoder = speex.NBEncoder()

    def _cb():
        keyevent.set()
        sys.stdin.readline()

    keyevent = asyncio.Event()
    sys.stdin.flush()
    loop.add_reader(sys.stdin, _cb)

    keytask = asyncio.async(keyevent.wait())
    audiotask = asyncio.async(recorder.dequeue())
    receivetask = asyncio.async(client.receive())

    audio = b''
    rawaudio = b''

    print('Recording, press any key to stop...')

    while not keytask.done():
        while len(rawaudio) > 320*recorder.channels*2:
            count = len(rawaudio)
            if count > 320*4*recorder.channels*2:
                count = 320*4*recorder.channels*2

            procsamples = b''
            if recorder.channels > 1:
                for i in range(0, count, 2*recorder.channels):
                    procsamples += rawaudio[i:i+1]
            else:
                procsamples = rawaudio[:count]

            rawaudio = rawaudio[count:]

            if resampler:
                audio += resampler.process(procsamples)
            else:
                audio += procsamples

        while len(audio) > encoder.frame_size*2:
            coded = encoder.encode(audio[:encoder.frame_size*2])
            client.send_audio(coded)
            audio = audio[encoder.frame_size*2:]

        yield from asyncio.wait((keytask, audiotask, receivetask),
                                return_when=asyncio.FIRST_COMPLETED,
                                loop=loop)

        if audiotask.done():
            more_audio = audiotask.result()
            rawaudio += more_audio
            audiotask = asyncio.async(recorder.dequeue())

        result = None
        if receivetask.done():
            tp,msg = receivetask.result()
            _log(msg)

            if msg['message'] == 'query_response' and msg['final_response'] == 1:
                result = msg['nlu_interpretation_results']

            if msg['message'] == 'query_end':
                client.close()
                return result

            receivetask = asyncio.async(client.receive())

    loop.remove_reader(sys.stdin)

    client.send_message({
        'message': 'audio_end',
        'audio_id': 456,
    })

    result = None
    while True:
        yield from asyncio.wait((receivetask,), loop=loop)
        tp, msg = receivetask.result()
        _log(msg)

        if msg['message'] == 'query_response' and msg['final_response'] == 1:
            result = msg['nlu_interpretation_results']

        if msg['message'] == 'query_end':
            break

        receivetask = asyncio.async(client.receive())

    client.close()
    return result


def _do_synthesis(loop, url, app_id, app_key, input_text, sr=16000, use_speex=None):

    if use_speex is True and speex is None:
        print('ERROR: Speex encoding specified but python-speex module unavailable')
        return

    if use_speex is not False and speex is not None:
        audio_type = 'audio/x-speex;mode=wb'
    else:
        audio_type = 'audio/L16;rate=%d' % sr

    client = WebsocketConnection()
    a = yield from client.connect(url, app_id, app_key)

    client.send_message({
        'message': 'connect',
        'device_id': '55555500000000000000000000000000',
        'codec': audio_type,
    })

    tp, msg = yield from client.receive()
    _log(msg) # Should be a connected message

    # synthesize
    client.send_message({
        'message': 'query_begin',
        'transaction_id': 123,

        'command': 'NMDP_TTS_CMD',
        'language': 'eng-USA',
        #'tts_voice': 'ava',
    })

    client.send_message({
        'message': 'query_parameter',
        'transaction_id': 123,

        'parameter_name': 'TEXT_TO_READ',
        'parameter_type': 'dictionary',
        'dictionary': {
            'audio_id': 789,
            'tts_input': input_text,
            'tts_type': 'text'
        }
    })

    client.send_message({
        'message': 'query_end',
        'transaction_id': 123,
    })

    if audio_type.split(';')[0] == 'audio/L16':
        decoder = None
    elif audio_type == 'audio/x-speex;mode=wb':
        decoder = speex.WBDecoder()
    else:
        print('ERROR: Need to implement decoding of %s!' % audio_type)

    pcm = b""
    if speex:
        resampler = speex.SpeexResampler(1, 16000, sr)
    while True:
        tp,msg = yield from client.receive()

        if tp == client.MSG_JSON:
            _log(msg)
            if msg['message'] == 'query_end':
                break
        else:
            _log('Got %d bytes of audio' % len(msg))
            if decoder is not None:
                tpcm = decoder.decode(msg)
                pcm = pcm + resampler.process(tpcm)
            else:
                pcm = pcm + msg

    client.close()
    return pcm


def _list_all(audio):
    for i in range(audio.get_device_count()):
        print(audio.get_device_info_by_index(i))


def _pick_recording_parameters(audio, dev_index):
    rates = [16000, 32000, 48000, 96000, 192000, 22050, 44100, 88200, 8000, 11025]
    channels = [1, 2]

    info = audio.get_device_info_by_index(dev_index)
    rates.append(info['defaultSampleRate'])
    channels.append(info['maxInputChannels'])

    for r in rates:
        for c in channels:
            if audio.is_format_supported(r, input_device=dev_index, input_channels=c, input_format=pyaudio.paInt16):
                return (r, c)

    return (None, None)


def _save_wave(output_file, pcm):
    f = wave.open(output_file, 'wb') 
    f.setparams((1, 2, 16000, 0, 'NONE', 'NONE')) 
    try:
        f.writeframes(pcm) 
    except Exception as e:
        _log(e)
    finally:
        f.close() 


class Recorder:
    def __init__(self, rate, channels, loop=None):
        self.rate = rate
        self.channels = channels
        self.audio_queue = []
        self.queue_event = asyncio.Event(loop=loop)
        if loop:
            self.loop = loop
        else:
            self.loop = asyncio.get_event_loop()

    def enqueue(self, audio):
        self.audio_queue.append(audio)
        self.queue_event.set()

    @asyncio.coroutine
    def dequeue(self):
        while True:
            self.queue_event.clear()
            if len(self.audio_queue):
                return self.audio_queue.pop(0)
            yield from self.queue_event.wait()

    def callback(self, in_data, frame_count, time_info, status_flags):
        self.loop.call_soon_threadsafe(self.enqueue, in_data)
        return (None, pyaudio.paContinue)


class NuanceClient:
    url = 'https://httpapi.labs.nuance.com/v1'

    def __init__(self, credentials, input_dev_idx=0, loop=None):
        self.credentials = credentials
        if not loop:
            self.loop = asyncio.get_event_loop()
        else:
            self.loop = loop

        self.input_dev_idx = input_dev_idx
        self.audio = pyaudio.PyAudio()
        (self.rate, self.channels) = _pick_recording_parameters(self.audio, self.input_dev_idx)

        if self.rate is None or self.channels is None:
            print("Couldn't find recording parameters")
            return

        self.recorder = Recorder(self.rate, self.channels)

    def understand(self, context_tag):
        recstream = self.audio.open(
            self.rate, 
            self.channels, 
            pyaudio.paInt16,
            input=True, 
            input_device_index=self.input_dev_idx, 
            stream_callback=self.recorder.callback)
        result = self.loop.run_until_complete(_do_audio(
            self.loop, 
            NuanceClient.url,
            self.credentials['app_id'],
            binascii.unhexlify(self.credentials['app_key']),
            context_tag=context_tag,
            recorder=self.recorder))
        recstream.close()
        return result

    def understand_text(self, context_tag, text):
        self.loop.run_until_complete(_do_understand_text(
            self.loop, 
            NuanceClient.url,
            self.credentials['app_id'],
            binascii.unhexlify(self.credentials['app_key']),
            context_tag=context_tag,
            text_to_understand=text))
        
    def recognize(self, reco_model):
        recstream = self.audio.open(
            self.rate, 
            self.channels, 
            pyaudio.paInt16, 
            input=True, 
            input_device_index=self.input_dev_idx, 
            stream_callback=self.recorder.callback)
        self.loop.run_until_complete(_do_audio(
            self.loop, 
            NuanceClient.url,
            self.credentials['app_id'],
            binascii.unhexlify(self.credentials['app_key']),
            reco_model=reco_model,
            recorder=self.recorder))
        recstream.close()
    
    def synthesize(self, input_text, sr=16000):
        data = self.loop.run_until_complete(_do_synthesis(
            self.loop,
            NuanceClient.url,
            self.credentials['app_id'],
            binascii.unhexlify(self.credentials['app_key']),
            input_text=input_text,
            sr=sr))
        return data


def main():
    with open(sys.argv[1], 'r') as f:
        credentials = json.load(f)
    client = NuanceClient(credentials)
    if sys.argv[2] == 'understand':
        client.understand(sys.argv[3])
    elif sys.argv[2] == 'understand_text':
        client.understand_text(sys.argv[3], sys.argv[4])
    elif sys.argv[2] == 'recognize':
        client.recognize(sys.argv[3])
    elif sys.argv[2] == 'synthesize':
        pcm = client.synthesize(sys.argv[3])
        _save_wave(sys.argv[4], pcm)
    else:
        pass


if __name__ == '__main__':
    main()

