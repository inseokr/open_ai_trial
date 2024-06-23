# Import flask and datetime module for showing date and time
import json
import math
import os
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
import logging
import datetime
import openai
import sys
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import check_password_hash

import utils
import lsai


svr_start_time = datetime.datetime.now()

# Initializing flask app
app = Flask(__name__) 

app.config['JWT_SECRET_KEY'] = os.environ['JWT_SECRET_KEY']
app.config['JWT_IDENTITY_CLAIM'] = 'userId'
jwtx = JWTManager(app)

ls_app_url =  'https://pocketverse.herokuapp.com/LS_API'

CORS(app)
logger_level = logging.DEBUG
app.logger.setLevel(logger_level)

openai.api_key  = os.environ['OPENAI_API_KEY']

client = openai.OpenAI()
model_name = "gpt-3.5-turbo"

port = int(os.environ.get("PORT", 5000))



@app.route('/login', methods=['POST'])
def login():
    '''This function is for testing purposes only'''
    try:
        username = request.json.get('username', None)
        password = request.json.get('password', None)
    except:
        username = 'lkjfrn_Jc3'
    '''
    user = User.query.filter_by(username=username).first()  # Replace with your user retrieval logic

    if user and check_password_hash(user.password, password):
        access_token = create_access_token(identity=username)
        return jsonify(access_token=access_token), 200

    return jsonify({"msg": "Bad username or password"}), 401
    '''
    access_token = create_access_token(identity=username)
    return jsonify(token=access_token), 200

@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    return jsonify({"msg": "Access granted by lsagent to protected route"}), 200
  

@app.route("/")
@cross_origin()
def hello_ls():
    msg = {'message':"Hello, LinkedSpaces!", 'start': svr_start_time, 'port':port}
    return jsonify(msg)


def _ask_openai():
    data = request.get_json()
    app.logger.debug(data)
    question = data.get('question')
    
    if not question:
        return jsonify({'error': 'No question provided'}), 400
    
    response = client.chat.completions.create(
                model=model_name,
                temperature = 0,
                messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": question}
                        ]
                )
    answer = response.choices[0].message.content
    return jsonify({'answer': answer})

@app.route('/openai-direct', methods=['POST'])
@cross_origin()
def ask_openai():
        return _ask_openai()

@app.route('/openai-direct-protected', methods=['POST'])
@jwt_required()
def ask_protected():
    ''' Protected access to openia with a generic prompt'''
    return _ask_openai()

def get_model_name(content = '', params = {})->str:
    '''Returns the globally set openai model name'''
    return model_name

def req_ai(system_message, report_message, content):
    app.logger.debug(system_message)
    messages=[
            {"role": "system", "content": system_message},
            {"role": "system", "content": report_message}, 
            {"role": "user", "content": content}
            ]
    response = client.chat.completions.create(
            model=model_name,
            temperature = 0,
            seed = 1234,
            messages=messages
            )
    answer = response.choices[0].message.content    
    app.logger.debug(answer)
    try:
        ans = json.loads(answer)
    except:
        ans = {'text':answer}
    return ans
    

def sentiment_analysis( content , params):
    '''Defines a prompt for openai to perform sentiment analysis, sends request to openai and and 
    returns result in a structured format.
    Parameters:
    content: customer's input
    params: application specific object, optional   
    ''' 

    scale = params.get('scale',2)
    extra_stats = params.get('reportExtraStats', False)
    system_message = f'You perform a sentiment analysis and report the result graded on the scale from 0 to {scale}. '
    report_message = f'''
                      report result as a dictionary with "scale" being the key and the sentiment grade being the value
                      '''

    if extra_stats:
        system_message += 'Calculate a number of sentences with positive and negative sentiments. '
        report_message += '''
                           For the number of sentences with positive sentiment use key "positive", for the number of sentences 
                           with negative sentiment use key "negative"
                           '''
    ans = req_ai(system_message, report_message, content)
    ret = {'scale': ans.get('scale','unavailable')}
    if extra_stats:
        ret['extraStats'] = {'negative':ans.get('negative',0), 'positive':ans.get('positive', 0)}           
    return ret

def categorization( content , params):
    '''Defines a prompt for openai to perform categorization analysis, sends request to openai and and 
    returns result in a structured format.
    Parameters:
    content: customer's input
    params: list of categories   
    ''' 
    cat_list = params['categoryList']
    system_message = f'''
               You are classifier of the content. You assign any or multiple categories from this list {cat_list}'''
    report_message = f'''
               Report result as a dictionary with "category" being the key and obtained list of applicable categories being the value.
               '''
    ans = req_ai(system_message, report_message, content)
    return ans

def grammar_correction(content, params):
    '''Defines a prompt for openai to perform grammar correction, sends request to openai and 
    returns as a string
    Parameters:
    content: customer's input
    params: application specific object, optional   
    ''' 
    style = params.get('style', None)
    system_message = f'''You are a grammar and spelling corrector. Correct the text received from the user and keep approximately the 
                         same amount of words. Preserve the number of sentences in the user's text. Preserve emoji'''
    if style:
        system_message += f''' Use {style} style. '''
    report_message = f'''Report result as a text. '''
    splt_content = content.strip().split('\n\n')
    ret = ''
    for spl in splt_content:
        ret += '\n\n'
        if spl != '':
            ret += req_ai(system_message, report_message, spl)['text']
    ret = {'text':ret.strip()}
    return ret

METERS_IN_MILE = 1609.34
DEFAULT_RADIUS = 10000

def get_user_preferences(params, url):
    '''Fetches user's preferences from a collection in an object database
    Parameters: 
    params: object containing userId and jwt_token
    url: route to the database    
    '''
    userId = params['userId']
    jwt_token = params['jwt_token']
    # first we request user preferences (profile)
    prof_params = {"userId":userId}
    route = 'lsagent/user/preferences'
    prof_res = utils.ls_get(route, url, params = prof_params, token = jwt_token)
    prefs = prof_res.json()['preferences']
    prefs_txt = f'{prefs}'
    return prefs_txt, jwt_token

    

def single_venue_itinerary(content, params):
    '''
    Generates a recommendation on a user request for a single point of interest based on user preferences and private recommendations of 
    the user's friends. 
    Parameters:
    content: customer's request
    params: object containing userID and approximate location 
    Return: returns a list of points of interest selected accoring to the user's preferences and user's friends' recommendations.
    '''     
    description = params['description']
    location_restriction = params['locationRestriction']
    # app.logger.debug(params)
    prefs_txt, jwt_token = get_user_preferences(params, ls_app_url)
    # app.logger.debug(prof_res.json()['preferences'])
    # second we are getting user stories
    params = {"searchScope": "FRIEND"}
    res = utils.ls_post(params, 'place/search', ls_app_url, token = jwt_token)
    places = res['foundPlaces']

    orig_value = {  'origin':(location_restriction['center']['latitude'], 
                        location_restriction['center']['longitude']), 
                    'radius_miles': location_restriction['radius']/METERS_IN_MILE
                }
    
    sel_dist = utils.select_places(places, orig_value, by = 'distance', logic = 'le')
    s_sel_places = json.dumps(sel_dist) 
    # Now preparing the AI request
    # model_name = "gpt-4"
    nrec = 3
    system_message = f'''You are a computerized advisor. Answer the user's request based on the user preferences and userStories in the 
                        structured content. Include the _id of the users who provided input for a particular 
                        recommendation in each recommendation. Include the id of the place for each of the places you recommend. 
                        Provide no more than {nrec} best recommendations. 
                        Keep only recommendations relevant to the user's request. 
                      '''
    content = f'''User request: {description}; User preferences: {prefs_txt}; structured content: {s_sel_places}'''

    report_message = '''Restructer user content as JSON object. The object should look as follows:
                        {
                        recommendations: [
                            {name: value,
                            name_id: value
                            description: value,
                            users: [{username:value} ]
                            }
                            ]
                        }
                    '''
    res, answer = lsai.req_ai2(client, model_name, model_name, system_message, report_message, content)
    recommended_places = []
    for rec in res['recommendations']:
        place_id = rec['name_id']
        place_name = rec['name']
        placesbyID = utils.select_places(sel_dist, place_id, by = 'place_id', logic = 'eq' )
        placesbyName = utils.select_places(sel_dist, place_name, by = 'place_name', logic = 'eq' )
        if placesbyID :
            places = placesbyID
        elif placesbyName:
            places = placesbyName
        else:
            places = []
        recommended_places.extend(places)
    if recommended_places:
        resp = {'result':'OK'}
    else:
        resp = {'result':'FAIL'}
        resp['reason'] = 'no places found'
    resp['foundPlaces'] = {'FRIENDS':recommended_places}
    return resp
    
def single_venue_recommendations_public(content, params):
    '''
    Generates a recommendation on a user request for a single point of interest based on user preferences and publicly available sources
    Parameters:
    content: customer's request
    params: object containing userID and approximate location 
    Return: returns a list of points of interest selected accoring to the user's preferences and publicly available sources.
    '''     

    prefs_txt, _ = get_user_preferences(params, ls_app_url)
    user_request = params
    user_request['locationRestriction']['radius'] /= METERS_IN_MILE
    ur_string = f'''
                {user_request['description']}  located in the radius of {user_request['locationRestriction']['radius']} in miles from
                a location with the following coordinates {user_request['locationRestriction']['center']}
                '''
    nrec = 3

    system_message = f'''You are a computerized advisor. Answer the user's request based on the user preferences. 
    Provide geolocations and street address 
    for found places.
    Provide no more than {nrec} best 
    recommendations. Keep only recommendations relevant to the user's request. 
    '''
    content = f'''User request: {ur_string}; User preferences: {prefs_txt}'''

    report_message = '''Restructer user content as JSON object. The object should look as follows:
    {
    recommendations: [
        {name: value,
        location: {
                addressString: street address,
                coordinate: {latitude: value,
                            longitude: value}
                },
        additionalBusinessInformation: {
            operationHour: "hh:mm AM ~ hh:mm PM",
            price: "$|$$|$$$|$$$$",
            
        category: "Korean|Italian|French|American|Indian|Vietnamese|Chinese"
        },
        recommendedReason: value
        }
        ]
    }'''

    # recommended_places, answer = lsai.req_ai2(client, "gpt-4", "gpt-3.5-turbo", system_message, report_message, content)
    recommended_places, answer = lsai.req_ai2(client, "gpt-3.5-turbo", "gpt-3.5-turbo", system_message, report_message, content)
    #this is copy and paste:
    if recommended_places:
        resp = {'result':'OK'}
        try:
            for el in recommended_places['recommendations']:
                #app.logger.debug(f'Recommendation element: {el}')
                poi_info = utils.OSMPOIInfo(el['name'],el['location']['addressString'])
                coord = poi_info.get_coordinates()
                d_coord = {'latitude':coord[0], 'longitude':coord[1]}
                #app.logger.debug(f'OSM coords: {d_coord}')
                if coord[0] is not None and coord[1] is not None:
                    el['location']['coordinate']=d_coord
        except Exception as e:
            app.logger.debug(f'Cannot update coordinates: {str(e)}')
            pass
    else:
        resp = {'result':'FAIL'}
        resp['reason'] = 'no places found'
    resp['foundPlaces'] = {'PUBLIC':recommended_places}
    # make a separate function
    # app.logger.debug(answer)
    return resp

category_list = '''
'restaurant', 
    'hotel', 
    'lodging', 
    'attraction', 
    'sightseeing', 
    'golf', 
    'cafe', 
    'grocery', 
    'shopping', 
    'airport', 
    'transportation',
    'activity'
'''
model35 = 'gpt-3.5-turbo'
model4 = 'gpt-4-0125-preview'

def itinerary_public_text(content, params):
    '''Generates travel itinerary as a travel agent. Defines and schedules activities, meals and accomodations based on user's request
    Parameters:
        content: user's request
        params: object containing userId, user's preferences and approximate location
    Return:
        text response in Markdown format
    '''
    prefs_txt, _ = get_user_preferences(params, ls_app_url)
    user_request = params
    cat_list = params.get('categories', category_list)
    model_ai = params.get('modelAI', model35)
    app.logger.debug(f'model: {model_ai}')

    user_request['locationRestriction']['radius'] /= METERS_IN_MILE
    ur_string = f'''
                {user_request['description']}  located in the radius of {user_request['locationRestriction']['radius']} in miles from
                a location with the following coordinates {user_request['locationRestriction']['center']}
                '''
    nrec = 1
    system_message = f'''You are a computerized advisor and scheduler. Generate a travel schedule based on the user request. 
    Recommend points of interest,  dining and lodging based on user preferences. Give recommendations for breakfast, lunch and dinner.
    When user is in the same town for more than one day select the same  accomodation for all nights spent there. 
    Provide {nrec} options for each recommendation. Provide a reason for each recommendaion. Add explanation that ties back to 
    the user's preferences or notable features of the recommendation.
    Provide street address for the location of every suggested option. Provide names for all activities. 
    Give a description of about 2 sentences for every recommendation. Identify a category for each recommended item from this list:
    {cat_list}
    
    Provide the answer in a Markdown format using this as an example:
    
    Example: **Day 1: Exploring Downtown Vancouver**
- **Morning:** Start your day with a visit to Stanley Park. Enjoy a leisurely walk or bike ride along the Seawall, 
offering stunning views of the city skyline and surrounding nature.
- **Lunch:** Head to a local restaurant known for its great food. Since you have a preference for Korean foods, 
you can try a Korean barbecue or bibimbap spot in downtown Vancouver.
- **Afternoon:** Explore the vibrant neighborhoods of Gastown and Chinatown. Discover hidden gems like hidden alleyways, unique shops, and street art.
- **Evening:** Visit historic landmarks such as the Vancouver Lookout or the Vancouver Art Gallery. Enjoy dinner 
at a restaurant specializing in local cuisine, where you can sample fresh seafood and other regional delights..
    '''
    content = f'''User request: {ur_string}; User preferences: {prefs_txt}'''

    try:
        response = lsai.unstruct_req(client, content, system_message, model = model_ai)
        # response = 'blababla'
        resp = {'result':'OK'}
        resp['itinerary'] = response
    except Exception as e:
        resp = {'result':'FAIL'}
        resp['reason'] = f'{e}'               
    return resp   

def itinerary_object(content, params):
    '''Generates a structured JSON object for a travel itinerary from an unstructured travel itinerary description.
    Parameters:
        content: unstructured travel itinerary
    Return:
        JSON object representing itinerary according to a defined scheme. 
    '''
    report_message = '''Restructer user content as JSON object using the following scheme:
    {
        itinerary: [day]
        day == {"day":number,
               "dayItinerary": dayItinerary,
               "lodging": lodging,
               "daySummary: daySummary}
        dayItinerary == [activity]
        activity == {"agenda": "lunch",
                     "time": "9:00AM" | morning,
                     "placeRecommendations": [recommendation]
                     }
        recommendation == {"name": name,
                           "description" description,
                           "location" : {
                               "addressString": address
                               "coordinate": {"latitude": value,
                                               "longitude": value}
                                }
                            "additionalBusinessInformation": {
                            "operationHour": timerange,
                            "rating": value,
                            "price": value,
                            "category": category
                          },
                          "recommendedReason": reason
                        }
        lodging == {"name": name,
                           "location" : {
                               "addressString": address
                               "coordinate": {"latitude": value,
                                               "longitude": value}
                                }
                            "additionalBusinessInformation": {
                            "rating": value,
                            "price": value,
                          },
                          "description": description
                          "recommendedReason": reason
                        }
    }
    category is the one from the list below:
    {category_list}
    '''
    try:
        response = lsai.struct_req(client, content, report_message)
        resp = response
        resp['result']='OK'
    except Exception as e:
        resp = {'result':'FAIL'}
        resp['reason'] = f'{e}'               
    return resp   

def remind_me(content, params):
    '''Answers  user's question on names and places they documented over time. 
    Parameters: 
        content: user request
    Return:
        best guess of the name and location of the place user is asking about
    '''
    resp = {}
    
    td = datetime.datetime.today()
    td = datetime.date.isoformat(td)
    model_ai = params.get('modelAI', model35)
    system_message = f'''Idendtify what the user is asking about by assigning one of the categories from the following list
                    [{category_list}]. Identify the name of geographical entity the user is asking about.  If there is no reference 
                    to time in the user's request, assign "none" to variable "time", otherwise identify the year the user is asking about.
                    Estimate the approximate area in squared miles of the identified geographical entity and assign the number to the variable named Area
                     '''
    report_message = '''Present the input as JSON object according to the following schema:
            { category: category, 
            location: { 
                        name: name, 
                        center: {latitude: value, 
                                longitude: value}, 
                        area:value (miles**2)},
                        time: time in ISO format
            }
            '''    
    obj, answer = lsai.req_ai2(client, model_ai, model35, system_message, report_message, content)
    # app.logger.debug(obj)
    if 'text' in obj.keys():
        # failure to build an object for the initial request
        resp['result'] = 'FAIL'
        resp['reason'] = f'failed to create an object from {answer}'
        return resp
    # Validating the response
    # building the filter for MDB
    try:
        center = obj['location']['center']
        radius2 = obj['location']['area']
        radius = math.sqrt(radius2)
        radius = radius*METERS_IN_MILE*2
        if radius < 1:
            radius = DEFAULT_RADIUS
        try:
            tm = datetime.datetime.fromisoformat(obj['time'][:-1])
            year = tm.year
            ts = datetime.datetime(year,1,1).timestamp()*1000
        except:
            ts = None
    except Exception as e:
        resp = {'result':'FAIL'}
        resp['reason'] = f'{e}, in processing {obj}' 
        return resp
    
    user = params['users'][0]              
    token = params['jwt_token']

    filters ={
            "userName": user,
            "filters": {
                "location": {'center':center, 
                            'radius':radius
                            },
                "categories": [obj['category']],
                "time": {
                "timestamp": ts, 
                "window": 365*2
                        }
                        }
            }
    # app.logger.debug(filters)
    route = 'lsagent/user/places'
    resp['filters'] = filters
    places = utils.ls_post(filters, route, ls_app_url, token = token)
    if len(places) == 0:
        resp['result'] = 'FAILURE'
        resp['reason'] = 'No matching place found in DB'
        return resp

    # Second call
    system_message = f'''find two locations from this list {places} that match best the user's request. 
                     Report placeName and corresponding placeIndex for the found match. '''
    report_message = '''Present input as JSON object according to the following schema:
                    {"matching_places":[{"placeIndex": placeIndex, "placeName": placeName}]}'''
    try:
        resp, text = lsai.req_ai2(client, model_ai, model35, system_message, report_message, content)
        resp['result'] = 'OK'
    except Exception as e:
        resp['result'] = 'FAIL'
        resp['reason'] = f'{e}, failure in the second call'
    resp['initialRequestStructured'] = obj
    resp['MDBfilters'] = filters
    resp['placedCount'] = len(places['placeList'])
    # resp['places'] = places
    return resp

########################################################################################
def structure_request(content, params):
    '''Identifies location of a point of interest, such as a restaurant, museum, vista point, etc. and a category it belongs to in an unstractured request and presents result 
    as a structured object
    Parameters: 
    content: user's unstructured request
    Return: object with a location and a category
    '''
    resp = {}
    user = content
    cat_list = params.get('categories', category_list)
    model_ai = params.get('modelAI', model35)


    assistant = '''You are a computer program that presents result following the 
                Example of the output:{"location": location, "category": category, "uniqueLocation": uniqueLocation}.
            '''
    system_0 = f'''identify a location and a category from the list of categories [{cat_list}] provided in the user request. If there 
          is no location information in the user request report null as the location. If there is no category identified report null 
          as the category'''
    system_1 = '''If the ilocation is not null, determine if it is a unique location world-wide. Report true if it is unique and false if it is not unique'''
    # system_1 = '''If the ilocation is not null, determine if there are multiple locations world-wide with this name. Report a list of locations with this name, not more than five, sorted in the 
    # order of decreased population.'''
    messages=[
        {"role": "assistant", "content": assistant},
        {"role": "system", "content": system_0},
        {"role": "system", "content": system_1},
        {"role": "user", "content": user},
        ]
    try:
        response = client.chat.completions.create(
                model=model_ai,
                temperature = 0,
                seed = 1234,
                messages=messages,
                )
        answer = response.choices[0].message.content
    except Exception as e:
        resp['result'] = 'FAIL'
        resp['reason'] = f'{e}, failure in the AI call'
        return resp
    try:
        obj = json.loads(answer)
        resp['result'] = 'OK'
        resp['initialRequestStructured'] = obj
        return resp
    except Exception as e:
        resp['result'] = 'FAIL'
        resp['reason'] = f'{e}, cannot create an object from {answer}'
        return resp
    
########################################################################################

def select_ai_task_function(task_name : str):
    ''' Selects an appropriate func tion for a given task_name.
    For now (2023/12/17) it finds a matching function from the dictionary ai_functions below.
    Every new task that requires a function should be added the along with the function to the dictionary
    In future that can be replaced with more sophisticated methods.
    '''
    def default_ai_fun(content, params):
        return {'error':f'no function defined matching {task_name}'}
    
    ai_functions = {'get_model_name': get_model_name,
                'sentiment_analysis': sentiment_analysis,
                    'categorization': categorization,
                    'grammar_correction':grammar_correction,
                    'single_venue_itinerary':single_venue_itinerary,
                    'single_venue_recommendations_public':single_venue_recommendations_public,
                    'itinerary_public_text':itinerary_public_text,
                    'itinerary_object': itinerary_object,
                    'remind_me': remind_me,
                    'structure_request': structure_request,
                } 

    ret = ai_functions.get(task_name, default_ai_fun)
    return ret



@app.route('/ai-task', methods=['POST'])
@jwt_required()
def ai_task_handler():
    '''General AI task handler. Finds an appropriate function from ai_functions dictionary and passes 
       the text and parameters to it'''
    # Accessing JWT token from the request headers
    try:
        jwt_token = request.headers.get('Authorization').split(" ")[1]
        # Decode user name from JWT token
        userId = get_jwt_identity()
        
        data = request.get_json()
        tasks = data['task']
        # app.logger.debug(json.dumps(data))
        content = data['text']
        task_type = data['type']
        task_name = tasks['task_name']
        app.logger.debug(f'task type: {task_type}, task name:{task_name}')
        if task_type == 'ai_single_task':
            task = tasks
            fnct = select_ai_task_function(task_name)
            params = task.get('params', {})
            params['userId'] = userId
            params['jwt_token'] = jwt_token
            result = fnct(content, params)
            ret = result 
        elif task_type == 'ai_batch_task': # no use case for this so far 2023-12-12. 
            results = []
            for task in tasks:
                task_name = task['task_name']
                fnct = select_ai_task_function(task_name)
                params = task['params']
                result = fnct(content, params)
                rec = {task_name: result}
                results.append(rec)
            ret = results
        else:
            ret = f'task type {task_type} is not supported'
        return jsonify({'answer':ret}), 200
    except Exception as e:
        return jsonify(f'{e}'), 400



# Running app
if __name__ == '__main__':
    app.run(debug=True, host = '0.0.0.0', port = port)
