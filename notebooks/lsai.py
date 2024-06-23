import openai
import json

def unstruct_req(client, content, system_message, model = 'gpt-4'):    
    messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": content}
            ]
    response = client.chat.completions.create(
            model=model,
            temperature = 0,
            seed = 1234,
            messages=messages,
            )
    answer = response.choices[0].message.content 
    return answer

def struct_req(client, content, report_schema, model = 'gpt-3.5-turbo'):
    messages=[
            {"role": "system", "content": report_schema}, 
            {"role": "user", "content": content}]        
    response = client.chat.completions.create(
            model=model,
            temperature = 0,
            seed = 1234,
            messages=messages,
            response_format={ "type": "json_object" }
            )
    jobject = response.choices[0].message.content
    try:
        ret = json.loads(jobject)
    except:
        ret = {'text':jobject}  
    return ret
      


def req_ai2(client, model_name_system, model_name_report, system_message, report_message, content):
    '''
    Makes a call to OpenAI and, optionally, a second call to format the first answer
    Parameters:
        client: OpenAI client object
        model_name_system: version of the openai model (gpt-3.5-turbo, gpt-4, etc.) used for the firts openai substantitive call
        model_name_report: as above but for the formatting part
        system_message: instruction to the model of what to do with the content
        report_message: description of a JSON schema or formatting instructions
        content: user's input
    Return:
        ret:    JSON object or formatted response
        answer: response to the first AI call
    '''
 

    messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": content}
            ]
    response = client.chat.completions.create(
            model=model_name_system,
            temperature = 0,
            seed = 1234,
            messages=messages,
            )
    # unstructured response
    answer = response.choices[0].message.content  
    # print(answer)

    if len(report_message) >0 : #format and enhance the answer above
        messages=[
                {"role": "system", "content": report_message}, 
                {"role": "user", "content": answer}]
        
        response = client.chat.completions.create(
                model=model_name_report,
                temperature = 0,
                seed = 1234,
                messages=messages,
                response_format={ "type": "json_object" }
                )
        jobject = response.choices[0].message.content
    else: # do not format
        jobject = answer
    # jobject = answer
    try: # in case formatted respons is a JSON object
        ret = json.loads(jobject)
    except: # just make a JSON object 
        ret = {'text':answer}     
    return ret, answer # ret is always an object. 

