import copy
from datetime import datetime, timedelta
import json
import re
import time
import pprint
from typing import List

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
                origins = flight_configurations[0].origin.split(',')
                root_curl = self.__generate_root_curl(origins, destination, flight_configurations[0].days_of_stay)
                print(f'Root cURL: {root_curl}')
                root_curl_obj = self.__parse_curl(root_curl) # parse the cURL to get the root cURL object with all cURL parts as attributes
                for flight in flight_configurations:
                    # Generate cURLs for each flight configuration. For example: all 7 days of stay roundtrips from BTS to JFK, for next 180 days
                    curls = self.__generate_curls(root_curl_obj, flight.origin, flight.destination, flight.days_of_stay)
                    result.extend(curls)
        return result

    def __generate_result_curls(self, destinations: dict):
        result = []
        for destination, flight_configurations in destinations.items():
            if len(flight_configurations) > 0:
                origins = flight_configurations[0].origin.split(',')
                root_curl = self.__generate_root_curl(origins, destination, flight_configurations[0].days_of_stay)
                root_curl_obj = self.__parse_curl(root_curl) # parse the cURL to get the root cURL object with all cURL parts as attributes
                for flight in flight_configurations:
                    # Generate cURLs for each flight configuration. For example: all 7 days of stay roundtrips from BTS to JFK, for next 180 days
                    curls = self.__generate_curls(root_curl_obj, flight.origin, flight.destination, flight.days_of_stay)
                    result.extend(curls)
        return result
    
    def __generate_root_curl(self, origins: List[str], destination: str, days_of_stay: int):
        '''
        Mimic the real user behaviour to get the GetCalendarPicker's endpoint cURL:
        -   fill `origin` and `destination`
        -   click on calendar and capture the GetCalendarPicker's endpoint cURL
        -   return the cURL
        '''
        with sync_playwright() as playwright:
            page = playwright.chromium.launch(headless=False).new_page()
            page.goto('https://www.google.com/travel/flights?hl=en-US&curr=EUR')

            # click "Reject" cookies ... todo: analyse this later, if this is really necessary. Currently I do not have an exact opinion.
            from_place_field = page.query_selector_all('.lssxud')[0]
            from_place_field.click()
            time.sleep(1)
            
            ###############################
            # type "From" - the first origin
            ###############################
            from_place_field = page.query_selector_all('.e5F5td')[0]
            from_place_field.click()
            time.sleep(1)
            from_place_field.type(origins[0])
            time.sleep(1)
            page.keyboard.press('Enter')
            time.sleep(1)

            ###############################
            # type "From" - the second origin
            ###############################
            origins.pop(0) # removes the second origin, because we already typed it
            from_place_field = page.query_selector_all('.e5F5td')[0]
            from_place_field.click()
            time.sleep(1)

            # click on a '+' button to add another origin. The button is inside 2nd occurence of class="rrg5je C2Kvyf"
            add_origin_button = page.query_selector_all('.rrg5je.C2Kvyf')[-1]
            add_origin_button.click()
            time.sleep(1)

            from_place_field.type(origins[0])
            time.sleep(1)
            from_place_field_selected = page.query_selector(f'li[data-code="{origins[0]}"]') # ul class=DFGgtd --> li data-code=origin
            from_place_field_selected.click()
            time.sleep(1)

            ###############################
            # type "From" - all remaining origins
            ###############################
            origins.pop(0) # removes the third origin, because we already typed it
            for origin in origins:
                from_place_field = page.query_selector_all('.lJj3Hd.PuaAn')[-1]
                # from_place_field.click()
                time.sleep(1)
                from_place_field.type(origin)
                time.sleep(1)
                from_place_field_selected = page.query_selector(f'li[data-code="{origin}"]') # li data-code=<origin>
                from_place_field_selected.click()
                time.sleep(1)

            # after all origins are typed, click on the "Done" button (class=rrg5je FAN8Zb)
            done_button = page.query_selector_all('.rrg5je.FAN8Zb')[-1]
            done_button.click()

            ###############################
            # type "To"
            ###############################
            to_place_field = page.query_selector_all('.e5F5td')[-1]
            to_place_field.click()
            time.sleep(1)
            to_place_field.type(destination)
            time.sleep(1)
            to_place_field = page.query_selector(f'li[data-code="{destination}"]') # li data-code=<destination>
            to_place_field.click()
            time.sleep(1)

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

    def __parse_curl(self, curl: str):
        
        '''
        In this function, we will parse the cURL to get the root cURL object with all cURL parts as attributes.
        return the root cURL object
        '''
        
        # Extract the URL
        url_match = re.search(r"curl -X POST '(.*?)'", curl)
        url = url_match.group(1) if url_match else None

        # Extract the headers
        headers = {}
        header_matches = re.findall(r"-H '(.*?)'", curl)
        for header in header_matches:
            key, value = header.split(": ", 1)
            headers[key] = value

        # Extract the data
        data_match = re.search(r"--data-raw '(.*?)'", curl)
        data = data_match.group(1) if data_match else None

        return {
            "url": url,
            "headers": headers,
            "data": data
        }

    def __generate_curls(self, root_curl_obj, origin: str, destination: str, days_of_stay: int):
        '''
        Generate cURLs for each flight configuration. For example: all `days_of_stay` days of stay roundtrips from `origin` to `destination`, for next 180 days.
        To get prices for next 180 days, we need to generate only around 4 cURLs, because in calendar picker we see prices for curernt month and the following month. 
        return the list of cURLs

        The logic for generating cURLs:
        1. calculate the neccessary number of clicks on calendar (next page) to get the prices for next 180 days, according to the current date
        2. iterate over the `number_of_necessary_clicks`
        3. for each iteration, generate a cURL. In each cURL, change following parts:
            -   increase URL's `_reqid`. For example from 1030783 to 1230783
            -   change the string of payload's `f.req` field, where we need to adjust `from_date` and `to_date`
            -   change the string of payload's `f.req` field, where we need to change the default 7 days stay to `days_of_stay`
            -   (we ignore the header cookies and header x-goog-batchexecute-bgr changes for now)
        '''
        curls = []
        from_date_template_str = datetime.now().strftime('%Y-%m-%d')
        to_date_template_str = self.__get_last_date_of_next_month().strftime('%Y-%m-%d')
        number_of_necessary_clicks = self.__calculate_next_page_clicks()
        for i in number_of_necessary_clicks:
            # generate cURL
            curl = self.__generate_curl(root_curl_obj, from_date_template_str, to_date_template_str, i, days_of_stay)
            curls.append(curl)

        return curls
    
    def __get_last_date_of_next_month(self):
        return datetime.now().replace(day=1, month=datetime.now().month+1) - timedelta(days=1)

    def __calculate_next_page_clicks(self):
        ''''
        Calculate the number of necessary clicks on calendar (next page) to get the prices for next 180 days.
        On the left side of calendar, there is a current month. On the right side of calendar, there is a following month.
        On the left side of calendar, the dates are active and non-active. The active dates are clickable. The non-active dates are not clickable.
        We are interested only in the active dates, because we can get the prices only for active dates.
        =========================================================================================================
        So we need to calculate the number of necessary clicks on calendar (next page) to get the prices for next 180 days.
        '''
        today = datetime.now()
        
        # region current month coverage
        # get the last date of the current month
        last_day_of_current_month = today.replace(day=1, month=today.month+1) - timedelta(days=1)
        
        # get the number of active dates in current month (including today)
        active_dates_in_current_month = last_day_of_current_month.day - today.day
        # endregion current month coverage

        # region next months coverage
        covered_days = active_dates_in_current_month # so far, there are `active_dates_in_current_month` covered days. In the following while loop, we will increase this counter
        number_of_neccessary_clicks = 0
        while covered_days < 180:
            # get the number of active dates in next month
            last_day_of_next_month = last_day_of_current_month.replace(day=1, month=last_day_of_current_month.month+2) - timedelta(days=1)
            # increase the counter by the number of active dates in next month
            covered_days += last_day_of_next_month.day
            # increase the number of necessary clicks
            number_of_neccessary_clicks += 1
        # endregion next months coverage

        # return the number of necessary clicks on calendar (next page) to get the prices for next 180 days
        return number_of_neccessary_clicks

    def __generate_curl(self, root_curl_obj, from_date_template_str: str, to_date_template_str: str, iteration: int, days_of_stay: int):
        '''
        Generate a cURL. Take a `root_curl_obj` as input "default" cURL and modify a deep copy of it accordingly:
            -   increase URL's `_reqid` according to the `iteration` parameter. For example if `iteration` = 2, then change it from 1030783 to 1230783.
            -   change the string of payload's `f.req` field, where we need to adjust `from_date` and `to_date`
            -   change the string of payload's `f.req` field, where we need to change the default 7 days stay to `days_of_stay`
            -   (we ignore the header cookies and header x-goog-batchexecute-bgr changes for now) 
        return the modified deep copy cURL
        '''
        
        # Get the URL's `_reqid`
        req_id_match = re.search(r"_reqid=(\d+)", root_curl_obj['url'])
        req_id = req_id_match.group(1) if req_id_match else None
        
        # Replace the first two numbers from original string with value calculated as first two numbers from original string + iterations.
        new_req_id_first_two_characters = int(req_id[0:2]) + iteration
        first_character = str(new_req_id_first_two_characters)[0]
        second_character = str(new_req_id_first_two_characters)[1]
        remaining_characters = str(new_req_id_first_two_characters)[2:]

        # Increase URL's `_reqid`. Increase the 2nd number in the URL's `_reqid` by +1. So for example from 1030783 to 1130783.
        final_req_id = None
        if second_character == '9':
            final_req_id = f"{int(first_character) + 1}0{remaining_characters}"
        else:
            final_req_id = f"{first_character}{int(second_character) + 1}{remaining_characters}"

        # Change the string of payload's `f.req` field, where we need to adjust `from_date` and `to_date`
        if iteration == 0:
            # get today's date
            from_date_raw = datetime.now()
            from_date_str = datetime.now().strftime('%Y-%m-%d')
            # get last date of a next month
            to_date_str = datetime.now().replace(day=1, month=datetime.now().month+1) - timedelta(days=1).strftime('%Y-%m-%d')
        else:
            # get the first date of a next month
            from_date_raw = datetime.now()
            from_date_str = from_date_raw.replace(day=1, month=datetime.now().month+iteration).strftime('%Y-%m-%d')
            # get the last date of a second next month
            to_date_str = from_date_raw.replace(day=1, month=from_date_raw.month+iteration+1) - timedelta(days=1).strftime('%Y-%m-%d')
        
        payload = root_curl_obj['data']
        payload = payload.replace(from_date_template_str, from_date_str)
        payload = payload.replace(to_date_template_str, to_date_str)

        # Change the string of payload's `f.req` field, where we need to change the default 7 days stay to `days_of_stay`
        payload = payload.replace('%5B7%2C7', '%5B' + str(days_of_stay) + '%2C' + str(days_of_stay))
        
        # Create the result cURL
        result_curl = copy.deepcopy(root_curl_obj) # deep copy the root cURL object, so we do not modify the original object. We will return the modified object
        result_curl['data'] = json.dumps(payload)
        result_curl['url'] = re.sub(r"_reqid=\d+", f"_reqid={final_req_id}", result_curl['url'])

        return f"curl -X POST '{result_curl['url']}' -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Accept-Encoding: gzip, deflate, br' -H 'Accept-Language: en-US,en;q=0.9,sk;q=0.8' -H 'Connection: keep-alive' -H 'Host: www.google.com' -H 'Origin: https://www.google.com' -H 'Referer: https://www.google.com/travel/flights?hl=en-US&curr=EUR' -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36' --data-raw '{result_curl['data']}'"

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