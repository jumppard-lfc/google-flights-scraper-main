import os
import requests
from dotenv import load_dotenv

from oxylabs import RealtimeClient

# Load environment variables from .env file
load_dotenv()

class OxylabsApiService:
    def __init__(self):
        # Initialize the SERP Realtime client with your credentials.
        self.oxylabs_api_client = RealtimeClient(os.environ['OXYLABS_USERNAME'], os.environ['OXYLABS_PASSWORD'])
        

    def send_request(self, curl):
        ''''
        This method sends a cURL request to the Oxylabs API and returns the response.
        '''
        
        # Structure payload.
        payload = {
            'source': 'universal',
            'url': 'https://sandbox.oxylabs.io/',
            # 'render': 'html', # If page type requires
        }

        # Get response.
        response = requests.request(
            'POST',
            'https://realtime.oxylabs.io/v1/queries',
            auth=('USERNAME', 'PASSWORD'), # Your credentials go here
            json=payload,
        )
        
        print(f'Sending cURL request to Oxylabs API: {curl}')
        return {
            'status': 'success',
            'response': 'response'
        }

