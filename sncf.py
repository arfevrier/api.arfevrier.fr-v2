import os
import requests
from multiprocessing.pool import ThreadPool
from datetime import datetime

class RemoteAPIError(Exception):
    "Raised when a remote error appear in SNCF internal API"
    pass

class SNCFBroker:
    def __init__(self):
        self.apiURL = "https://api.sncf.com/v1"
        # 2025 Appli Gares APK:
        # https://garesetconnexions-online.azure-api.net/API/PIV/Departures/*******?uicDestination=************&departureDateTime=
        # Ocp-Apim-Subscription-Key: SNCF_WEBAPIKEY
        # ---
        # Old 2025
        # https://sncf-appligares-qualification-slot303d.azurewebsites.net/API/PIV
        self.webApiURL = "https://garesetconnexions-online.azure-api.net/API/PIV"
        self.webApiKey = os.environ.get('SNCF_WEBAPIKEY')
        self.api_count = 0
        self.api_keys = [os.environ.get('SNCF_API_KEY_1'),
                         os.environ.get('SNCF_API_KEY_2'),
                         os.environ.get('SNCF_API_KEY_3')
                         ]
    
    def getKey(self):
        if self.api_count%10 == 0:
            print(f"[SNCFBroker] API keys have been used {self.api_count} times.")
        self.api_count += 1
        return self.api_keys[self.api_count%len(self.api_keys)]
        
    def requestGet(self, url):
        r = requests.get(url, auth=(self.getKey(), '')).json()
        if 'error' in r:
            raise RemoteAPIError
        else:
            return r

    def requestWebApi(self, url):
        r = requests.get(url, headers={'Ocp-Apim-Subscription-Key': self.webApiKey})
        assert r.status_code == 200
        return r.json()

    def getTrainsPlatform(self, gare):
        urlD = f"{self.webApiURL}/Departures/00{gare}"
        urlA = f"{self.webApiURL}/Arrivals/00{gare}"
        with ThreadPool(2) as p:
            departures, arrivals = p.map(self.requestWebApi, [urlD, urlA])
        return {platform['trainNumber']:{'delay':platform['informationStatus']['delay'],'platform':platform['platform']['track']} for platform in departures},\
                {platform['trainNumber']:{'delay':platform['informationStatus']['delay'],'platform':platform['platform']['track']} for platform in arrivals}

    def getDeparturesDisruptionsArrivals(self, stop_area, count=200):
        urlD = f"{self.apiURL}/coverage/sncf/stop_areas/{stop_area}/departures?count={count}"
        urlA = f"{self.apiURL}/coverage/sncf/stop_areas/{stop_area}/arrivals?count={count}"
        with ThreadPool(2) as p:
            departures, arrivals = p.map(self.requestGet, [urlD, urlA])
            arrivals = [arrival['display_informations']['headsign'] for arrival in arrivals['arrivals']]
            disruptions = [SNCFDisruption(disruption) for disruption in departures['disruptions']]
            departures = [SNCFDeparture(departure) for departure in departures['departures']]            
            return departures, disruptions, arrivals

    def getDepartures(self, stop_area, count=20):
        url = f"{self.apiURL}/coverage/sncf/stop_areas/{stop_area}/departures?count={count}"
        for departure in self.requestGet(url)['departures']:
            yield SNCFDeparture(departure)

    def getDisruptions(self, stop_area, count=20):
        url = f"{self.apiURL}/coverage/sncf/stop_areas/{stop_area}/departures?count={count}"
        for disruption in self.requestGet(url)['disruptions']:
            yield SNCFDisruption(disruption)

class SNCFDisruption:
    def __init__(self, SNCFobject):
        self.message = SNCFobject['messages'][0]['text'] if 'messages' in SNCFobject else ""
        self.effect = SNCFobject['severity']['effect']
        self.name = SNCFobject['severity']['name']

    def __repr__(self):
        return f"{self.effect} {self.name} {self.message}"

    def __str__(self):
        return self.__repr__()

class SNCFDeparture:
    def __init__(self, SNCFobject):
        self.timeFormat = '%Y%m%dT%H%M%S'
        self.direction = SNCFobject['display_informations']['direction']
        self.network = SNCFobject['display_informations']['network']
        self.headsign = SNCFobject['display_informations']['headsign']
        self.name = SNCFobject['display_informations']['name']
        self.stop = SNCFobject['stop_point']['name']
        self.platform = None
        self.delay = None

        if 'base_departure_date_time' in SNCFobject['stop_date_time']:
            self.base_departure_date_time = datetime.strptime(SNCFobject['stop_date_time']['base_departure_date_time'], self.timeFormat)
        else:
            self.base_departure_date_time = None
        
        self.departure_date_time = datetime.strptime(SNCFobject['stop_date_time']['departure_date_time'], self.timeFormat)

        if self.base_departure_date_time is not None:
            self.retard_departure = self.departure_date_time-self.base_departure_date_time
        else:
            self.retard_departure = None
        self.data_freshness = SNCFobject['stop_date_time']['data_freshness']

    def __repr__(self):
        return f"{self.direction} {self.network} {self.headsign} {self.name} {self.base_departure_date_time} {self.departure_date_time} {self.retard_departure} {self.data_freshness} {self.platform} {self.delay}"

    def __str__(self):
        return self.__repr__()


class TimetablePrinter:
    def departure_line(self, departure):
        direction = departure.direction.split(" ")[0]
        depart = departure.departure_date_time.strftime('%H:%M')
        base_depart = ""
        
        if departure.retard_departure is not None:
            retard = int(departure.retard_departure.total_seconds()/60)
            if retard > 0:
                base_depart = f"{strike(departure.base_departure_date_time.strftime('%H:%M'))} "
            info = ""
            if departure.delay is not None:
                info += f"| ⚠️ Retard {departure.delay} min!"
        else:
            info = f"| ⚠️ Train non prévue!"
        # ➔➜➝➞➡➤➨➩➭➯➾
        if departure.platform is not None:
            addon = f" ➔ {departure.platform} "
        else:
            addon = ""
        return f"  ▧ {base_depart}{depart} ➔ {direction}{addon}{info}"

    def disruption_line(self, disruption):
        return f" 🚨 {italic(disruption.effect)}: {disruption.message}"

def strike(text):
    return '\u0336'.join(text) + '\u0336'

def italic(text):
    char1 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    char2 = '𝘈𝘉𝘊𝘋𝘌𝘍𝘎𝘏𝘐𝘑𝘒𝘓𝘔𝘕𝘖𝘗𝘘𝘙𝘚𝘛𝘜𝘝𝘞𝘟𝘠𝘡'
    return text.translate(str.maketrans(char1, char2))

def bold(text):
    char1 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    char2 = '𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇'
    return text.translate(str.maketrans(char1, char2))
