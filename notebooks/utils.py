import requests
import certifi
from geopy import distance
import urllib
from geopy.geocoders import Nominatim

def ls_get (route, url, params = {}, token=''):
    """ Function to access unprotected and protected route using the JWT token. """
    url = f'{url}/{route}'
    print (f'url: {url}')
    headers = {'Authorization': f'Bearer {token}'}
    rsp = requests.get(url, params = params, headers = headers, verify=certifi.where())
    return rsp

def ls_post (data_out: dict, route: str, url, token=''):
    headers = {
    "Content-Type": "application/json",
    'Authorization': f'Bearer {token}'
    }
    url = f'{url}/{route}'
    response = requests.post(url, json=data_out, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        raise Exception(f"post to {url} failed")
    return

def make_stories(pl):
    user_stories = pl['userStories']
    location =  pl['place']['locationString']
    user_st_text = ''
    for us in user_stories:
        user = us['user']['username']
        story = ''
        for st in us['stories']:
            t = st['timestamp']
            s = st['story']
            if t:
                story += f' on {t} '
            story += s                      
        user_st_text += f'Visitor {user} told the following stories: {story}' + '\n-------------------\n'
    return user_st_text

def select_places(places, value, by = 'user', logic = 'eq' ):
    ret = []
    match by:
        case 'user':
            for pl in places:
                user_stories = pl['userStories']
                for us in user_stories:
                    user = us['user']['username']
                    match logic:
                        case 'eq':
                            if user == value:
                                ret.append(pl)
                        case 'neq':
                            if user != value:
                                ret.append(pl)
                                
        case 'distance':
            orig_lat, orig_long = value['origin']
            orig = (orig_lat, orig_long)
            rad = value['radius_miles']
            for pl in places:
                coor = pl['place']['coordinates']
                lat = coor['lat']
                lng = coor['lng']
                pl_coor = (lat, lng)
                dist = distance.distance(orig, pl_coor).miles
                if (dist <= rad):
                    ret.append(pl)
                
        case 'place_id':
            place_id = value
            for pl in places:
                if pl['place']['_id']==value:
                    ret.append(pl)
        case 'place_name':
            place_name = value
            for pl in places:
                if pl['place']['listingSummary'] == place_name:
                    ret.append(pl)
        case _:
            ret = []
    return ret

def make_all_stories(places):
    all_stories = ''# f'A number of tourists visited {location} and left their stories.\n'
    for pl in places:
        all_stories += make_stories(pl)
    return all_stories
    
### Coordinates and hours of operations
class BasePOIInfo:
    DEFAULT_UNAVAILABLE = "Not available"
    def __init__(self, poi_name, poi_address):
        self.poi_name = poi_name
        self.poi_address = poi_address
    def get_coordinates (self):
        return(None, None)
#     def validate_poi (self):
#         print('Not implemented yet')
#         return False
    def get_operation_hours (self):
        return self.DEFAULT_UNAVAILABLE
    
class OSMPOIInfo(BasePOIInfo):
    def __init__(self, poi_name, poi_address):
        super().__init__(poi_name, poi_address)
        self.info_raw = self._get_poi_info_raw (self.poi_address)
    def _get_poi_info_raw (self, query):
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://nominatim.openstreetmap.org/search?q={encoded_query}&format=json"
            response = requests.get(url)
            data = response.json()
        except:
            data = list()
        return data  
    
    def get_coordinates (self):
        try:
            coord = (float(self.info_raw[0]['lat']), float(self.info_raw[0]['lon']))
        except:
            coord = (None, None)
        return coord
    
    def get_operation_hours (self):
        try:
            coord = (float(self.info_raw[0]['lat']), float(self.info_raw[0]['lon']))
        except:
            return self.DEFAULT_UNAVAILABLE
        overpass_url = "http://overpass-api.de/api/interpreter"
        overpass_query = f"""
        [out:json];
        (
          node(around:500,{coord[0]},{coord[1]})["opening_hours"];
        );
        out body;
        """
        hours_out = self.DEFAULT_UNAVAILABLE
        try:
            response = requests.get(overpass_url, params={'data': overpass_query})
            data = response.json()
            if data and data.get('elements'):
                 for element in data['elements']:
#                     if 'name' in element['tags']:
#                         print(element['tags']['name'])
                    if 'name' in element['tags'] and self.poi_name.lower() in element['tags']['name'].lower():
                        if 'opening_hours' in element['tags']:
                            hours_out = element['tags']['opening_hours']
        except:
            hours_out = self.DEFAULT_UNAVAILABLE
        return hours_out
    
class GeoPOIInfo(BasePOIInfo):
    def __init__(self, poi_name, poi_address):
        super().__init__(poi_name, poi_address)
    def get_coordinates (self):
        geolocator = Nominatim(user_agent="myApp")
        try:
            location = geolocator.geocode(self.poi_address)
            coord = (location.latitude, location.longitude)
        except:
            coord = (None, None)
        return coord
   
