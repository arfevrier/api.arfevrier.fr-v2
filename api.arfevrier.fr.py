#!/usr/bin/python3

from flask import Flask, request, jsonify, redirect, make_response, send_file
from flask_selfdoc import Autodoc
from flask_limiter import Limiter
from flask_cors import CORS

from anagramme import AnagrammeFinder
from google import GoogleBroker, YoutubeBroker, StringCache
from sncf import TimetablePrinter, SNCFBroker, RemoteAPIError, bold

import os
import re
import json
import socket
import datetime
import requests
import traceback
import subprocess
import urllib.parse
from lxml import html
from cryptography.fernet import Fernet
from multiprocessing.pool import ThreadPool

app = Flask(__name__)
app.config['SECRET_BYTE'] = bytes(os.environ.get("SECRET_BYTE"), 'utf-8')
CORS(app)
auto = Autodoc(app)

#Get original IP address:
def getIp():
    if request.headers.getlist("X-Forwarded-For"):
       return request.headers.getlist("X-Forwarded-For")[0]
    else:
       return request.remote_addr

#Define the limit of the API
limiter = Limiter(
    getIp,
    app=app,
    default_limits=["2000 per day", "100 per hour"]
)

#Define the anagramme finder class
APIanagramme = AnagrammeFinder("anagramme.txt")
#Define the google authentification class
GoogleAuth = GoogleBroker()
#Define the youtube interface class
YoutubeAPI = YoutubeBroker()
#Define cache for youtube ID video:
videoIDCache = StringCache()
#Define cache for youtube ID audio:
audioIDCache = StringCache()
#Define SNCF API class:
SNCFapi = SNCFBroker()
SNCFtimetable = TimetablePrinter()

@app.route('/')
@auto.doc()
def index():
    """API Documentation"""
    return auto.html(title='Documentation')

@app.route('/ping')
@auto.doc()
def ping():
    """Returns pong string."""
    return jsonify("pong")

@app.route('/ip')
@auto.doc()
def ip():
    """Returns a string containing your IP address."""
    return jsonify(getIp())

@app.route('/backup')
@auto.doc()
def backup_status():
    """Returns backup status of the server."""
    try:
        # For daily backup
        daily_backup_files = json.loads(subprocess.check_output(["rclone", "lsjson", "--no-mimetype", "--no-modtime", "OvhGRA:/afr-backup-daily"]))
        #> At least one backup present
        if len(daily_backup_files) == 0:
            return jsonify({'error':'Daily backup empty'}), 400
        for backup_files in daily_backup_files:
            #> Backup size is more than 100Mo
            if backup_files['Size'] < 100000000:
                return jsonify({'error':'Daily backup too small'}), 400
            #> Backup size is less than 10Go
            if backup_files['Size'] > 10000000000:
                return jsonify({'error':'Daily backup too big'}), 400
            #> Backup is not older than 72 hours
            if datetime.datetime.now()-datetime.datetime.strptime(backup_files['Name'], "backup-%Y-%m-%d-%H:%M:%S.tar.gz") > datetime.timedelta(hours=72):
                return jsonify({'error':'Daily backup not deleted'}), 400

        # For monthly backup
        monthly_backup_files = json.loads(subprocess.check_output(["rclone", "lsjson", "--no-mimetype", "--no-modtime", "OvhDE:/afr-backup-monthly"]))
        #> At least one backup present
        if len(monthly_backup_files) == 0:
            return jsonify({'error':'Montly backup empty'}), 400
        for backup_files in monthly_backup_files:
            #> Backup size is more than 10Go
            if backup_files['Size'] < 10000000000:
                return jsonify({'error':'Montly backup too small'}), 400
            #> Backup size is less than 60Go
            if backup_files['Size'] > 60000000000:
                return jsonify({'error':'Monthly backup too big'}), 400
            #> Backup is not older than 31 days
            if datetime.datetime.now()-datetime.datetime.strptime(backup_files['Name'], "backup-%Y-%m-%d-%H:%M:%S.tar.gz") > datetime.timedelta(days=31):
                return jsonify({'error':'Montly backup not deleted'}), 400
        return jsonify({'status':'ok'})
    except:
        return jsonify({'error':'Exception with Rclone'}), 400

@app.route('/subdomains/<string:domain>')
@auto.doc()
def subdomain(domain):
    """Returns a subdomain list for a specified domain name."""
    if re.fullmatch("^[a-zA-Z0-9.-]+", domain) is not None:
        try:
            subdomains = subprocess.check_output(["docker", "run", "--rm", "projectdiscovery/subfinder:latest", "-silent", "-d", domain], text=True)
            return jsonify({'size':len(subdomains),
                            'domain':domain,
                            'list':subdomains.split("\n")[:-1],
                            'credit':'Subfinder # github.com/projectdiscovery/subfinder',
                            })
        except:
            return jsonify({'error':'Exception with Subfinder'}), 400
    else:
        return jsonify({'error':'Incorrect domain'}), 400
        
@app.route('/data/<string:name>', methods = ['GET', 'POST', 'DELETE'])
@auto.doc()
def data(name):
    """Manage JSON string of named content ."""
    if re.fullmatch("^[a-zA-Z0-9]+", name) is not None:
        try:
            if request.method == 'GET':
                with open(f"data/{name}", "r") as reader:
                    return jsonify(json.load(reader))
                    
            if request.method == 'POST':
                data = json.loads(request.data)
                with open(f"data/{name}", "w") as writer:
                    json.dump(data, writer)
                return jsonify(data)

            if request.method == 'DELETE':
                os.remove(f"data/{name}")
                return '', 200
        except:
            return jsonify({'error':'Incorrect file'}), 400
    else:
        return jsonify({'error':'Incorrect name'}), 400

@app.route('/anagram/<string:sentence>')
@auto.doc()
def anagram(sentence):
    """Returns a list of anagrams matching the sentence."""
    content = sentence.upper()
    content = content.replace(" ", "").replace("É", "E").replace("È", "E").replace("Ê", "E").replace("Ô", "O")
    content = content.replace("'", "").replace("Â", "A").replace("Ç", "C").replace("Œ", "OE").replace("Ï", "I")
    content = content.replace("Ù", "U").replace("Ä", "A").replace("À", "A").replace("Û", "U").replace("Ü", "U")
    content = content.replace("Ë", "E").replace(")", "").replace("!", "").replace("-", "").replace(".", "")
    content = content.replace("\r", "").replace("\n", "")
    if re.fullmatch("^[A-Z]+", content) is not None:
        try:
            return jsonify(list(APIanagramme.find(content)))
        except:
            return jsonify({'error':'Anagramme too large'}), 400
    else:
        return jsonify({'error':'Incorrect sentence'}), 400

@app.route('/youtube/video/<string:id>')
@auto.doc()
def youtube_video(id):
    """Redirect to the mp4 file of a YouTube video."""
    if re.fullmatch("^[a-zA-Z0-9_-]+", id) is not None:
        try:
            #> First, get the video url
            if videoIDCache.inCache(id):
                r = videoIDCache.get(id)
            else:
                url = subprocess.check_output(["yt-dlp", "-g", "-f", "b", f"https://youtube.com/watch?v={id}"], text=True)
                # Skip last '\n' char
                r = url[:-1]
                videoIDCache.add(id, r)
            #> Second, return video or link
            if "url" in request.args:
                return jsonify(r)
            else:
                if "Range" in request.headers:
                    userHeaders = {"Range":request.headers["Range"]}
                else:
                    userHeaders = {}
                buffer = requests.get(r, headers=userHeaders, stream=True)
                response = make_response(send_file(buffer.raw, download_name=f"{id}.mp4"))
                for key, value in buffer.headers.items():
                    response.headers[key] = value
                return response, buffer.status_code
        except:
            return jsonify({'error':'Error with yt-dlp'}), 400
    else:
        return jsonify({'error':'Incorrect id'}), 400

@app.route('/youtube/audio/<string:id>')
@auto.doc()
def youtube_audio(id):
    """Redirect to the mp3 file of a YouTube video."""
    if re.fullmatch("^[a-zA-Z0-9_-]+", id) is not None:
        try:
            #> First, get the audio url
            if audioIDCache.inCache(id):
                r = audioIDCache.get(id)
            else:
                url = subprocess.check_output(["yt-dlp", "-g", "-x", f"https://youtube.com/watch?v={id}"], text=True)
                # Skip last '\n' char
                r = url[:-1]
                audioIDCache.add(id, r)
            #> Second, return audio or link
            if "url" in request.args:
                return jsonify(r)
            else:
                if "Range" in request.headers:
                    userHeaders = {"Range":request.headers["Range"]}
                else:
                    userHeaders = {}
                buffer = requests.get(r, headers=userHeaders, stream=True)
                response = make_response(send_file(buffer.raw, download_name=f"{id}.mp3"))
                for key, value in buffer.headers.items():
                    response.headers[key] = value
                return response, buffer.status_code
        except:
            return jsonify({'error':'Error with yt-dlp'}), 400
    else:
        return jsonify({'error':'Incorrect id'}), 400

@app.route('/twitter/video/<string:id>')
@auto.doc()
def twitter_video(id):
    """Redirect to the mp4 file of a Twitter video."""
    if re.fullmatch("^[0-9]+", id) is not None:
        try:
            url = subprocess.check_output(["yt-dlp", "-g", "-f", "b", f"https://twitter.com/i/status/{id}"], text=True)
            # Skip last '\n' char
            r = url[:-1]
            if "url" in request.args:
                return jsonify(r)
            else:
                return redirect(r)
        except:
            return jsonify({'error':'Error with yt-dlp'}), 400
    else:
        return jsonify({'error':'Incorrect id'}), 400
    
@app.route('/twitch/<string:username>')
@auto.doc()
def twitch(username):
    """Returns the m3u8 (mpeg url) file of a Twitch livestream."""
    if re.fullmatch("^[a-zA-Z0-9_]+", username) is not None:
        try:
            url = subprocess.check_output(["streamlink", "--stream-url", f"twitch.tv/{username}"], text=True)
            # Skip last '\n' char
            r = requests.get(url[:-1], allow_redirects=True)
            return r.content, 200, {'Content-Type': 'application/vnd.apple.mpegurl'}
        except:
            return jsonify({'error':'Error with Streamlink'}), 400
    else:
        return jsonify({'error':'Incorrect username'}), 400

@app.route('/twitch/video/<string:id>')
@app.route('/twitch/video/<string:id>/<string:quality>')
@auto.doc()
def twitch_video(id, quality="chunked"):
    """Returns the m3u8 (mpeg url) file of a Twitch vod. Quality: chunked (default), 720p60, 480p30, 360p30, audio_only, etc..."""
    if re.fullmatch("^[0-9]+", id) is not None and re.fullmatch("^[a-zA-Z0-9_]+", quality) is not None:
        try:
            url = subprocess.check_output(["bash", "-c", f"twitch-dl info {id} --json 2>/dev/null| jq -r '.playlists[] | select(.group_id == \"{quality}\") | .url'"], text=True)
            # Skip last '\n' char
            r = url[:-1]
            if "url" in request.args:
                return jsonify(r)
            else:
                return f'<video controls="" autoplay="" width="100%" height="100%" name="media"><source src="{r}" type="application/vnd.apple.mpegurl"></video>', 200
        except:
            return jsonify({'error':'Error with Streamlink'}), 400
    else:
        return jsonify({'error':'Incorrect username'}), 400

@app.route('/nmap/<string:ipv4>')
@auto.doc()
def nmap(ipv4):
    """Returns a list of open ports for a given IP."""
    if re.fullmatch("^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?).){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$", ipv4) is not None:
        #try:
            xml = subprocess.check_output(["nmap", "-oX", "-", ipv4])
            xml_tree = html.fromstring(xml)
            ports = xml_tree.xpath(".//port")
            return jsonify({'ip': ipv4, 'ports': [int(port.get("portid")) for port in ports]})
        #except:
        #    return jsonify({'error':'Error with nmap'}), 400
    else:
        return jsonify({'error':'Incorrect ipv4'}), 400

@app.route('/whois/<string:request>')
@auto.doc()
def whois(request):
    """Return the WHOIS content of a Domain/IP/AS."""
    request = request.encode("idna").decode("utf-8")
    if re.fullmatch("^[a-zA-Z0-9.-]+", request) is not None:
        try:
            content = subprocess.check_output(["whois", request], text=True)
            return jsonify({'request': request, 'content': content})
        except:
            return jsonify({'error':'Error with whois'}), 400
    else:
        return jsonify({'error':'Invalid request'}), 400

@app.route('/host/ipv4/<string:ipv4>')
@auto.doc()
def host_ipv4(ipv4):
    """Return the hostname using the IPv4."""
    if re.fullmatch("^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?).){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$", ipv4) is not None:
        try:
            result = socket.gethostbyaddr(ipv4)
            return jsonify({'request': ipv4, 'hostname': result[0]})
        except:
            return jsonify({'error':'Unknown host'}), 400
    else:
        return jsonify({'error':'Incorrect ipv4'}), 400

@app.route('/host/domain/<string:domain>')
@auto.doc()
def host_domain(domain):
    """Return IPv4 address of the host name provided."""
    domain = domain.encode("idna").decode("utf-8")
    if re.fullmatch("^[a-zA-Z0-9.-]+", domain) is not None:
        try:
            result = socket.gethostbyname(domain)
            return jsonify({'request': domain, 'ipv4': result})
        except:
            return jsonify({'error':'Unknown host'}), 400
    else:
        return jsonify({'error':'Incorrect domain name'}), 400

@app.route('/dig/<string:domain>')
@app.route('/dig/<string:domain>/<string:server>')
@auto.doc()
def dig(domain, server=""):
    """Return the result of a DNS ALL request to the domain."""
    domain = domain.encode("idna").decode("utf-8")
    if re.fullmatch("^[a-zA-Z0-9.-]+", domain) is not None:
        try:
            if re.fullmatch("^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?).){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$", server) is None:
                server = "8.8.8.8"
            content = subprocess.check_output(["dig", domain, "ANY", f"@{server}", "+noidnout"], text=True)
            # Skip first '\n' char
            return jsonify({'request': domain, 'content': content[1:]})
        except:
            return jsonify({'error':'Error with dig'}), 400
    else:
        return jsonify({'error':'Incorrect domain name'}), 400

@app.route('/youtube/login')
@auto.doc()
def youtube_login():
    """Redirect to the login Google page for YouTube permission."""
    try:
        r = GoogleAuth.getRedirectUrl("https://api.arfevrier.fr/v2/youtube/redirect", "https://www.googleapis.com/auth/youtube.readonly")
        return redirect(r)
    except:
        return jsonify({'error':'Error'}), 400

@app.route('/youtube/redirect')
@auto.doc()
def youtube_redirect():
    """Get the access token and redirect to youtube player page."""
    try:
        if 'code' in request.args:
            yt_token = GoogleAuth.getToken(request.args['code'], "https://api.arfevrier.fr/v2/youtube/redirect")
            if yt_token is not None:
                enc_yt_token = Fernet(app.config['SECRET_BYTE']).encrypt(bytes(yt_token,'utf-8'))
                return redirect(f"https://apps.arfevrier.fr/youtube_player/#subscriptions={urllib.parse.quote_from_bytes(enc_yt_token)}")
            else:
                return jsonify({'error':'Invalid code'}), 400
        else:
            return jsonify({'error':'No authorization code'}), 400
    except:
        return jsonify({'error':'Invalid code'}), 400

@app.route('/sncf/<int:stop_area1>/<int:stop_area2>')
@auto.doc()
def sncf(stop_area1, stop_area2):
    """Returns the 3 next departures on the stop area 1 from/to 2."""
    try:
        SPACE = "\t"
        content = [f"{SPACE*27}{datetime.datetime.now().strftime('%H:%M')}",""] #12 lines in total
        TITLE = '🚆 SNCF 🚅'

        with ThreadPool(4) as p:
            wait = p.map_async(SNCFapi.getTrainsPlatform, [stop_area1, stop_area2])
            rA, rB = p.map(SNCFapi.getDeparturesDisruptionsArrivals, [f"stop_area:SNCF:{stop_area1}", f"stop_area:SNCF:{stop_area2}"])
            departuresA, disruptionsA, arrivalsA = rA
            departuresB, disruptionsB, arrivalsB = rB
            try:
                rA, rB = wait.get()
                departuresPlatA, arrivalsPlatA = rA
                departuresPlatB, arrivalsPlatB = rB
            except:
                TITLE = '⚠️ API 📉 dégradé'
                departuresPlatA, arrivalsPlatA, departuresPlatB, arrivalsPlatB = [], [], [], []
                print("Warning: API not available")
        departures_AtoB = [departure for departure in departuresA if departure.headsign in arrivalsB][:3]
        departures_BtoA = [departure for departure in departuresB if departure.headsign in arrivalsA][:3]
        for i in range(len(departures_AtoB)):
            if departures_AtoB[i].headsign in arrivalsPlatB:
                departures_AtoB[i].platform = arrivalsPlatB[departures_AtoB[i].headsign]['platform']
            if departures_AtoB[i].headsign in departuresPlatA:
                departures_AtoB[i].delay = departuresPlatA[departures_AtoB[i].headsign]['delay']
        for i in range(len(departures_BtoA)):
            if departures_BtoA[i].headsign in departuresPlatB:
                departures_BtoA[i].platform = departuresPlatB[departures_BtoA[i].headsign]['platform']
            if departures_BtoA[i].headsign in departuresPlatB:
                departures_BtoA[i].delay = departuresPlatB[departures_BtoA[i].headsign]['delay']

        for disruption in disruptionsA[:1]:
            content.append(SNCFtimetable.disruption_line(disruption))
        if len(departures_AtoB) > 0:
            content.append(f" Depuis {bold(departures_AtoB[0].stop)}:")
        for departure in departures_AtoB[:3]:
            content.append(SNCFtimetable.departure_line(departure))
        if len(departures_BtoA) > 0:
            content.append(f" Depuis {bold(departures_BtoA[0].stop)}:")
        for departure in departures_BtoA[:3]:
            content.append(SNCFtimetable.departure_line(departure))
        print(content)
        return jsonify({'title':TITLE,'content':"\n".join(content)})
    except RemoteAPIError:
        return jsonify({'title':TITLE,'content':f"\n\n{SPACE*6} 🌏 𝘙𝘦𝘮𝘰𝘵𝘦 𝘈𝘗𝘐 𝘳𝘦𝘵𝘶𝘳𝘯 𝘦𝘳𝘳𝘰𝘳 🌏"}), 210
    except:
        traceback.print_exc()
        return jsonify({'error':'Error with SNCF API'}), 400

@app.route('/jules/<string:product>/<string:size>')
@auto.doc()
def jules_taille(product, size):
    """Returns the presence of the item in stock."""
    if re.fullmatch("^[0-9]+", product) is not None and re.fullmatch("^[A-Z]+", size) is not None:
        try:
            htmlTree = html.fromstring(requests.get(f"https://www.jules.com/fr-fr/p/{product}.html").content)
            stock = json.loads(htmlTree.xpath('//script[@type="application/ld+json"]/text()')[0])
            sizes = [measurement["value"] for measurement in stock["sizeSpecification"]["hasMeasurement"]]
            if size in sizes:
                return jsonify({'sizes':sizes, 'stock':'ok'})
            else:
                return jsonify({'sizes':sizes, 'stock':'no'}), 400
        except:
            return jsonify({'error':'Exception with requests'}), 500
    else:
        return jsonify({'error':'Incorrect product reference'}), 400

if __name__ == '__main__':
    app.run(host="127.0.0.1", port=1230) #debug=True
