import json
from flask import Flask, jsonify, request, url_for, render_template
from flask import render_template, Blueprint, make_response
import logging
from logdna import LogDNAHandler
import datetime
from urllib import request as rq
import io
import os
import random
import speech_recognition as sr
from gtts import gTTS
import ffmpeg

app = Flask(__name__)

class PrefixMiddleware(object):
#class for URL sorting 
    def __init__(self, app, prefix=''):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        #in this line I'm doing a replace of the word flaskredirect which is my app name in IIS to ensure proper URL redirect
        if environ['PATH_INFO'].lower().replace('/stt','').startswith(self.prefix):
            environ['PATH_INFO'] = environ['PATH_INFO'].lower().replace('/stt','')[len(self.prefix):]
            environ['SCRIPT_NAME'] = self.prefix
            return self.app(environ, start_response)
        else:
            start_response('404', [('Content-Type', 'text/plain')])            
            return ["This url does not belong to the app.".encode()]

# Make the WSGI interface available at the top level so wfastcgi can get it.
# wsgi_app = app.wsgi_app
app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix='/api')

ingestionKey = 'b7c813e09f26938d8bcd7c4f38be2a40'
logdna_options = {
  'app': 'stt',
  'level': 'Debug',
  'index_meta': True
}
logging.basicConfig(
    handlers=[
        logging.FileHandler(filename='log.log', encoding='utf-8', mode='a+'),
        LogDNAHandler(ingestionKey, logdna_options)
    ],
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y%m%d.%H%M%S'
)

class SttDTO:
    # Constructor
    def __init__(self, tipo, url, mensaje, lang = "es-es", respuesta = "", path = ""):
        self.tipo = tipo
        self.url = url
        self.mensaje = mensaje
        self.lang = lang
        self.respuesta = respuesta
        self.path = path

    # Parser
    @classmethod
    def from_json(cls, json_string):
        json_dict = json.loads(json_string)
        return cls(**json_dict)
    
    # Function that return when print(class) without attribute
    def __repr__(self):
        return f'<SttDTO message: {self.mensaje}>'

def fn_generate_random_name():
    a = str(random.randint(101,999))
    b = str(random.randint(101,999))
    c = str(random.randint(101,999))
    d = str(random.randint(101,999))
    today = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    return '{}_{}{}{}{}'.format(today,c,d,a,b)

def fn_get_audio_from_folder(filename):
    AUDIO_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)),filename)
    return AUDIO_FILE

def fn_get_path():
    try:
        return os.path.dirname(os.path.realpath(__file__))
    except:
        raise Exception('ERROR/PATH/')

def fn_decode_audio(in_filename, **input_kwargs):
    fnc = 'fn_decode_audio'
    try:
        logging.debug('{} --> Audio decoding'.format(fnc))
        out, err = (ffmpeg
            .input(in_filename, **input_kwargs)
            .output('-', f='wav', ab='160k', ac=2, ar=44100)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return io.BytesIO(out)
    except FileNotFoundError as e:
        raise e
    except ffmpeg.Error as e:
        raise ValueError(e.stderr.decode('utf-8').splitlines()[-1])
    except Exception as e:
        raise e

def fn_speech_to_text(sttDTO):
    fnc = 'fn_speech_to_text'
    try:
        r = sr.Recognizer()
        audioReceived = fn_decode_audio(sttDTO.url)
        logging.debug('{} --> Audio received {}'.format(fnc, audioReceived.__sizeof__()))
        with sr.AudioFile(audioReceived) as source:
            logging.debug('{} --> Bytes to AudioFile'.format(fnc))
            audio = r.record(source)
        try:
            logging.debug('{} --> AudioFile to Google Speech Recognition'.format(fnc))
            response = r.recognize_google(audio, language=sttDTO.lang)
            logging.info('{} --> Google Speech Recognition Response: {}'.format(fnc, response))
            return response
            # pip install google-api-python-client
            # nanocred = open("googleAI-Harima.json").read()
            # return r.recognize_google_cloud(audio,language=sttDTO.lang,credentials_json=nanocred)
        except sr.UnknownValueError:
            raise ValueError('{} --> Unrecognizable audio'.format(fnc))
        except sr.RequestError as e:
            logging.exception('{} --> {}'.format(fnc, e))
            raise Exception(e)
    except Exception as e:
        raise e

def fn_text_to_speech(sttDTO):
    fnc = 'fn_text_to_speech'
    try:
        gTTS_obj = gTTS(text=sttDTO.mensaje, lang=sttDTO.lang, slow=False)
        # path = 'C:\\APPS\\PUBLIC\\STTaudio'
        dirpath = fn_get_path()
        subdirpath = os.path.join(dirpath, 'files', '')
        if not os.path.exists(subdirpath):
            os.makedirs(subdirpath)
        filename = '{}.mp3'.format(fn_generate_random_name())
        logging.debug('{} --> filename: {}'.format(fnc, filename))
        gTTS_obj.save(os.path.join(subdirpath, filename))
        logging.info('{} --> filename: {} Saved'.format(fnc, filename))
        return filename
    except Exception as e:
        raise e

@app.route('/voiceprocess', methods=['GET','POST'])
def voiceprocess_controller():
    endpoint = request.endpoint
    try:
        if (request.method == 'POST'):
            if (request.is_json):
                request_json = request.get_json() # request -> json
                json_string = json.dumps(request_json) # json -> string
                logging.debug('{} --> REQUEST: {}'.format(endpoint, json_string))
                sttDTO = SttDTO.from_json(json_string) # string -> object
                if sttDTO.tipo.lower() == 'speechtotext':
                    logging.debug('{} --> {}'.format(endpoint, sttDTO.tipo))
                    sttDTO.respuesta = 'speech -> text'
                    sttDTO.mensaje = fn_speech_to_text(sttDTO)
                elif sttDTO.tipo.lower() == 'texttospeech':
                    logging.debug('{} --> {}'.format(endpoint, sttDTO.tipo))
                    sttDTO.respuesta = "text -> speech"
                    sttDTO.url = fn_text_to_speech(sttDTO)
                    sttDTO.url = '{}{}'.format(sttDTO.path, sttDTO.url)
                else:
                    raise ValueError('Valid type are speechtotext or texttospeech')
                logging.info('{} --> RESULT: {}'.format(endpoint, json.dumps(sttDTO)))
                return jsonify(sttDTO.__dict__), 200
            else:
                raise TypeError('The body is not a valid json')
        else:
            return 'Method not allowed', 400
    except KeyError as e:
        logging.exception(e)
        return '{} parameter not found'.format(str(e)), 400
    except (AttributeError, AssertionError, TypeError, ValueError) as e:
        logging.exception(e)
        return str(e), 400
    except Exception as e:
        logging.exception(e)
        return 'Please contact with support', 400

@app.route('/values')
def values_controller():
    return 'Api is running'

if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=8082) # waitress-serve --port=8082 app:app
    # app.run(host='0.0.0.0') # flask run