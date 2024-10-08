import os
import requests
from dotenv import load_dotenv
import base64

from oxylabs import RealtimeClient
from app.services import misc_service

# Load environment variables from .env file
load_dotenv()

class OxylabsApiService:
    def __init__(self):
        # Initialize the SERP Realtime client with your credentials.
        self.oxylabs_api_client = RealtimeClient(os.environ['OXYLABS_USERNAME'], os.environ['OXYLABS_PASSWORD'])
        

    def send_request(self, curl):
        
        ''''
        This method sends retrieves a cURL request and transforms it to the format supported by Oxylabs API.
        It returns the response of Oxylabs API call.
        '''
        
        # Get URL, headers, and payload from cURL.
        parsed_curl = misc_service.parse_curl(curl)

        # Base64 encode the POST body content
        base64_encoded_data = self.base64_encode_string(parsed_curl['data'])

        # Structure payload.
        payload = {
            "context": 
            [
                {
                    "key": "http_method",
                    "value": "post"
                },
                {
                    "key": "content",
                    "value": base64_encoded_data
                },
            ],
            'source': 'google',
            'url': parsed_curl['url'],
        }

        # Get response.
        response = requests.request(
            'POST',
            'https://realtime.oxylabs.io/v1/queries',
            auth=('USERNAME', 'PASSWORD'), # Your credentials go here
            json=payload,
        )
        
        return response.json()

    def base64_encode_string(self, input_string):
        input_bytes = input_string.encode('utf-8')
        encoded_bytes = base64.b64encode(input_bytes)
        return encoded_bytes.decode('utf-8')

    def process_response(self, response):
        '''
        This method processes the response from the Oxylabs API and returns the data.
        '''

        # TODO: Implement this method
        
        result = {
            'success': False, # this is just a mock value, for testing purposes. todo implement this method
            'data': response['data']
        }

        return result