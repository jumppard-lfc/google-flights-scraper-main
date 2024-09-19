from datetime import datetime
import time
import pprint

from app.models import AppRun, FlightsSearchConfiguration, Report
from app.services import oxylabs_api_service, database_service

import playwright
from playwright.sync_api import sync_playwright


class CalendarMimicService:
    def __init__(self):
        timestamp = datetime.utcnow()
        
        # initialize services
        self.oxylabs_api_service = oxylabs_api_service.OxylabsApiService()
        self.db_service = database_service.DbService('sqlite:///./test.db')
        
        # init new app run
        self.db_service.insert(AppRun.AppRun, {'created_at': timestamp, 'started_at': timestamp, 'status': 'running'})
        self.new_app_run = self.__get_last_app() # returns the last app run id
        print(f'New app run id: {self.new_app_run.id}')
        

    # def main_temp(self):
    #     # update the app run status to 'completed'
    #     self.db_service.update(AppRun.AppRun, self.new_app_run.id, {'status': 'completed', 'ended_at': datetime.utcnow(), 'inserted_records': 13})    

    def main_temp(self):
         # get all active flights search configurations
        flights_search_configurations = self.__get_active_flights_search_configurations() # returns all active flights search configurations
        print(f'Active flights search configurations: {flights_search_configurations}')

        # group them by destination and days of stay
        destinations = self.__group_flights_by_destination(flights_search_configurations) # groups flights by destination and order them by days of stay
        print(f'Destinations: {destinations}')

        # iterate over `destinations` and for each destination, generate a set of cURLs
        result_curls = self.__generate_result_curls_temp(destinations)

    def main(self) -> dict:
        ''''
        This is MAIN function, which encapsulates the whole logic of the 
            -   calendar mimic, 
            -   generating cURLs, 
            -   sending then to Oxylabs 
            -   and processing the responses.
        '''

        # get all active flights search configurations
        flights_search_configurations = self.__get_active_flights_search_configurations() # returns all active flights search configurations
        pprint(f'Active flights search configurations: {flights_search_configurations}')

        # group them by destination and days of stay
        destinations = self.__group_flights_by_destination(flights_search_configurations) # groups flights by destination and order them by days of stay
        print(f'Destinations: {destinations}')

        # example of `destinations`
        # {
        #     "JFK":
        #     [
        #         FlightsSearchConfiguration(origin='BTS', destination='JFK', days_of_stay=2, is_active=True, created_at=datetime.datetime(2021, 9, 1, 0, 0), updated_at=datetime.datetime(2021, 9, 1, 0, 0)),
        #         FlightsSearchConfiguration(origin='BTS', destination='JFK', days_of_stay=3, is_active=True, created_at=datetime.datetime(2021, 9, 1, 0, 0), updated_at=datetime.datetime(2021, 9, 1, 0, 0))
        #     ],
        #     "LAX":
        #     [
        #         FlightsSearchConfiguration(origin='BTS', destination='LAX', days_of_stay=2, is_active=True, created_at=datetime.datetime(2021, 9, 1, 0, 0), updated_at=datetime.datetime(2021, 9, 1, 0, 0)),
        #         FlightsSearchConfiguration(origin='BTS', destination='LAX', days_of_stay=3, is_active=True, created_at=datetime.datetime(2021, 9, 1, 0, 0), updated_at=datetime.datetime(2021, 9, 1, 0, 0))
        #     ],
        #     ...
        # }


        # iterate over `destinations` and for each destination, generate a set of cURLs
        result_curls = self.__generate_result_curls(destinations)

        # send oxylabs API requests and retrieve oxylabs responses
        oxylabs_responses = self.__retrieve_oxylabs_responses(result_curls)
        
        # save the processed responses to the database
        self.__save_processed_responses_to_db(oxylabs_responses, self.new_app_run_id)

        # update the app run status to 'completed'
        self.db_service.update(AppRun.AppRun, self.new_app_run.id, {'status': 'completed', 'ended_at': datetime.utcnow(), 'inserted_records': len(oxylabs_responses)})    
        
    def __get_last_app(self):
        return self.db_service.select(AppRun.AppRun, filters=None, order_by='id', limit=1, desc=True)[0]

    def __get_active_flights_search_configurations(self):
        return self.db_service.select(FlightsSearchConfiguration.FlightsSearchConfiguration, {'is_active': True})
    
    def __group_flights_by_destination(self,flights_search_configurations: list):
        # Sort the dict by Destination first and convert it to a list
        sorted_flights = sorted(flights_search_configurations, key=lambda x: x.destination)

        # Group flights by destination and order them by days of stay
        from itertools import groupby
        destinations = {}
        for destination, flights in groupby(sorted_flights, key=lambda x: x.destination):
            destinations[destination] = sorted(flights, key=lambda x: x.days_of_stay)

        return destinations

    def __generate_result_curls_temp(self, destinations: dict):
        result = []
        for destination, flight_configurations in destinations.items():
            if len(flight_configurations) > 0:
                root_curl = self.__generate_root_curl(flight_configurations[0].origin, destination, flight_configurations[0].days_of_stay)
                print(f'Root cURL: {root_curl}')
            #     root_curl_obj = self.__parse_curl(root_curl) # parse the cURL to get the root cURL object with all cURL parts as attributes
            # for flight in flight_configurations:
            #     # Generate cURLs for each flight configuration. For example: all 7 days of stay roundtrips from BTS to JFK, for next 180 days
            #     curls = self.__generate_curls(root_curl_obj, flight.origin, flight.destination, flight.days_of_stay)
            #     result.extend(curls)
        return result

    def __generate_result_curls(self, destinations: dict):
        result = []
        for destination, flight_configurations in destinations.items():
            if len(flight_configurations) > 0:
                root_curl = self.__generate_root_curl(flight_configurations[0].origin, destination, flight_configurations[0].days_of_stay)
                root_curl_obj = self.__parse_curl(root_curl) # parse the cURL to get the root cURL object with all cURL parts as attributes
            for flight in flight_configurations:
                # Generate cURLs for each flight configuration. For example: all 7 days of stay roundtrips from BTS to JFK, for next 180 days
                curls = self.__generate_curls(root_curl_obj, flight.origin, flight.destination, flight.days_of_stay)
                result.extend(curls)
        return result
    
    def __generate_root_curl(self, origin: str, destination: str, days_of_stay: int):
        '''
        Mimic the real user behaviour to get the GetCalendarPicker's endpoint cURL:
        -   fill `origin` and `destination`
        -   click on calendar and capture the GetCalendarPicker's endpoint cURL
        -   return the cURL
        '''
        with sync_playwright() as playwright:
            page = playwright.chromium.launch(headless=False).new_page()
            page.goto('https://www.google.com/travel/flights?hl=en-US&curr=EUR')

            # type "From"
            from_place_field = page.query_selector_all('.lssxud')[0]
            from_place_field.click()
            time.sleep(1)
            from_place_field = page.query_selector_all('.e5F5td')[0]
            from_place_field.click()
            time.sleep(1)
            from_place_field.type(origin)
            time.sleep(1)
            page.keyboard.press('Enter')

            # type "To"
            to_place_field = page.query_selector_all('.e5F5td')[1]
            to_place_field.click()
            time.sleep(1)
            to_place_field.type(destination)
            time.sleep(1)
            page.keyboard.press('Enter')

            # click on the calendar & capture the cURL
            calendar_departure = page.query_selector_all('.TP4Lpb')[0] # click on the `Departure` date field
            self.curl_command = None # Variable to store the cURL command we are trying to capture
            self.__capture_calendar_picker_curl(page)
            calendar_departure.click()
            time.sleep(5) # Wait for a short period to ensure the request is captured

            # Close the browser
            page.close()

        return self.curl_command

    def __capture_calendar_picker_curl(self, page):
        
        '''
        To capture the HTTP request made by the website when the user clicks on the "Departure" date field, 
        you can use Playwright's request interception feature. 
        This allows you to listen for network requests and capture the details of the specific request you're interested in.

        Here's how you can modify your code to capture the cURL of the GetCalendarPicker request:
        1. Set up request interception: Use the page.on('request') event to listen for network requests.
        2. Filter the specific request: Check if the request URL matches the GetCalendarPicker endpoint.
        3. Capture the request details: Extract the necessary details to construct the cURL command.
        '''
        
        # Function to construct cURL command from request
        def construct_curl(request):
            headers = ' '.join([f"-H '{k}: {v}'" for k, v in request.headers.items()])
            data = request.post_data
            return f"curl -X {request.method} '{request.url}' {headers} --data-raw '{data}'"        

        # Listen for network requests
        def on_request(request):
            if 'GetCalendarPicker' in request.url:
                print(request.url)
                self.curl_command = construct_curl(request)

        page.on('request', on_request)

    def __parse_curl(curl: str):
        '''
        In this function, we will parse the cURL to get the root cURL object with all cURL parts as attributes.
        return the root cURL object
        '''
        pass

    def __generate_curls(root_curl_obj, origin: str, destination: str, days_of_stay: int):
        '''
        Generate cURLs for each flight configuration. For example: all `days_of_stay` days of stay roundtrips from `origin` to `destination`, for next 180 days.
        return the list of cURLs

        The logic of generating cURLs:
        1. start with today's date as the from date and add `days_of_stay` to get the to date
        2. iterate over the next 180 days
        3. for each day, generate a cURL. In each cURL, change following parts:
            -   increase URL's `_reqId`. For example from 1030783 to 1230783
            -   change the string of payload's `f.req` field, where we need to adjust `from_date` and `to_date`
            -   (we ignore the header cookies and header x-goog-batchexecute-bgr changes for now) 
        '''
        pass

    def __retrieve_oxylabs_responses(result_curls: list):
        result = []
        for curl in result_curls:
            # send cURLs to Oxylabs
            response = oxylabs_api_service.send_curl(curl)
            # process the response
            processed_response = oxylabs_api_service.process_response(response)
            result.append({'curl_request': curl, 'curl_response': processed_response, 'success': processed_response['success']})
        return result
    
    def __save_processed_responses_to_db(self, oxylabs_responses: list, new_app_run_id: int):
        for response in oxylabs_responses:
            data = {
                'new_app_run_id': new_app_run_id, 
                'destination': response['curl_response']['destination'], 
                'days_of_stay': response['curl_response']['days_of_stay'], 
                'best_price': response['curl_response']['best_price']
            }
            # save the processed response to the database
            self.db_service.insert(Report, data)