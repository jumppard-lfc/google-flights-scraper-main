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
                    curls = self.__generate_curls(root_curl_obj, flight.days_of_stay)
                    result.extend(curls)
        return result

    def __generate_result_curls(self, destinations: dict):
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
        result = {}
        for destination, flight_configurations in destinations.items():
            if len(flight_configurations) > 0:
                origins = flight_configurations[0].origin.split(',')
                root_curl = self.__generate_root_curl(origins, destination, flight_configurations[0].days_of_stay)
                root_curl_obj = self.__parse_curl(root_curl) # parse the cURL to get the root cURL object with all cURL parts as attributes
                for flight in flight_configurations:
                    # Generate cURLs for each flight configuration. For example: all 7 days of stay roundtrips from BTS to JFK, for next 180 days
                    curls = self.__generate_curls(root_curl_obj, flight.days_of_stay)
                    result[destination][flight.days_of_stay].extend(curls)
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

    def __generate_curls(self, root_curl_obj, days_of_stay: int):
        '''
        Generate cURLs for each flight configuration. For example: all `days_of_stay` days of stay roundtrips from `origin` to `destination`, for next 180 days.
        To get prices for next 180 days for the specific `day_of_stay` days of stay, we need to generate only around 3-4 cURLs, because in calendar picker we see prices for curernt month and the following month. 
        return the list of cURLs.

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
        to_date_template_str = self.__get_last_date_of_next_month(datetime.now()).strftime('%Y-%m-%d')
        number_of_necessary_clicks = self.__calculate_next_page_clicks()
        for i in list(range(0, number_of_necessary_clicks)):
            # generate cURL
            curl = self.__generate_curl(root_curl_obj, from_date_template_str, to_date_template_str, i, days_of_stay)
            print(f'Generated cURL: {curl}')
            curls.append(curl)

        return curls

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
        

        # region covering 1st page in Calendar (today month + following month)
        ##############################################################
        # covering the 1st and 2nd months in 1st page in Calendar
        ##############################################################
        
        # get the last date of the current month
        last_day_of_current_month = self.__get_last_date_of_current_month(today)
        
        # get the number of active dates in current month (including today)
        active_dates_in_current_month = last_day_of_current_month.day - today.day + 1

        # get the last date of the next month
        last_day_of_next_month = self.__get_last_date_of_next_month(today)

        # get the number of active dates in next month
        active_dates_in_next_month = last_day_of_next_month.day

        # calculate the number of active dates in both months (current month + next month)
        covered_days = active_dates_in_current_month + active_dates_in_next_month 
        # endregion covering 1st page in Calendar (current month + next month)

        # region next months coverage
        ##############################################################
        # covering the 1st and 2nd months in next pages in Calendar
        ##############################################################
        number_of_neccessary_clicks = 0
        next_month_cnt = 2 # we start with the 2nd next month (2nd page in Calendar). So for example if today is January, we start with March (because March is first month in next page in Calendar).
        while covered_days < 180:
            # get the number of active dates for the 1st month
            today_current = self.__get_increased_today(today, next_month_cnt) 
            last_day_of_first_month = self.__get_last_date_of_current_month(today_current)
            # get the number of active dates for the 2nd month
            last_day_of_second_month = self.__get_last_date_of_next_month(today_current)
            # increase the counter by the number of active dates in current and next months
            covered_days += (last_day_of_first_month.day + last_day_of_second_month.day)
            # increase the counter for the next 2 months so we land on a next Calendar page
            next_month_cnt += 2
            # increase the number of necessary clicks
            number_of_neccessary_clicks += 1
        # endregion next months coverage

        # return the number of necessary clicks on calendar (next page) to get the prices for next 180 days
        return number_of_neccessary_clicks

    def __get_last_date_of_current_month(self, current_date: datetime):
        
        # result
        last_day_of_current_month = None
        
        # Calculate the first day of the next month
        first_day_of_next_month = None
        if current_date.month == 12:
            first_day_of_next_month = current_date.replace(day=1, month=1, year=current_date.year + 1)
        else:
            first_day_of_next_month = current_date.replace(day=1, month=current_date.month + 1)

        # Subtract one day to get the last day of the current month
        last_day_of_current_month = first_day_of_next_month - timedelta(days=1)

        return last_day_of_current_month

    def __get_last_date_of_next_month(self, current_date: datetime):
        
        # Calculate the first day of the month after the next month
        if current_date.month == 12:
            first_day_of_month_after_next = current_date.replace(day=1, month=1, year=current_date.year + 1)
        elif current_date.month == 11:
            first_day_of_month_after_next = current_date.replace(day=1, month=1, year=current_date.year + 1)
        else:
            first_day_of_month_after_next = current_date.replace(day=1, month=current_date.month + 2)
        
        # Subtract one day to get the last day of the next month
        last_day_of_next_month = first_day_of_month_after_next - timedelta(days=1)
        
        return last_day_of_next_month

    def __get_increased_today(self, current_date: datetime, months_to_add: int):
        
        if months_to_add == 0:
            return current_date
        
        # Calculate the new month and year
        new_month = current_date.month + months_to_add
        new_year = current_date.year + (new_month - 1) // 12
        new_month = (new_month - 1) % 12 + 1
        
        # Create a new datetime object with the calculated year and month, and set the day to 1
        first_day_new_month = current_date.replace(year=new_year, month=new_month, day=1)

        return first_day_new_month
    
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
        
        # Increase URL's `_reqid`. Increase the 2nd number in the URL's `_reqid` by +1. So for example from 1030783 to 1130783.
        final_req_id = self.__increase_req_id(int(req_id), iteration)
        
        # Change the string of payload's `f.req` field, where we need to adjust `from_date` and `to_date`
        from_date_datetime = self.__get_increased_today(datetime.now(), 2*iteration) # 2 is a constant, because in 1 calendar page, there are 2 months
        from_date_str = from_date_datetime.strftime('%Y-%m-%d')
        to_date_str = self.__get_last_date_of_next_month(from_date_datetime).strftime('%Y-%m-%d')

        payload = root_curl_obj['data']
        payload = payload.replace(from_date_template_str, from_date_str)
        payload = payload.replace(to_date_template_str, to_date_str)

        # Change the string of payload's `f.req` field, where we need to change the default 7 days stay to `days_of_stay`
        payload = payload.replace('%5B7%2C7', '%5B' + str(days_of_stay) + '%2C' + str(days_of_stay))
        
        # Create the result cURL
        result_curl = copy.deepcopy(root_curl_obj) # deep copy the root cURL object, so we do not modify the original object. We will return the modified object
        result_curl['data'] = payload
        result_curl['url'] = re.sub(r"_reqid=\d+", f"_reqid={final_req_id}", result_curl['url'])

        # create a headers string
        headers_str = ' '.join([f"-H '{k}: {v}'" for k, v in result_curl['headers'].items()])

        return f"curl -X POST '{result_curl['url']}' {headers_str} --data-raw '{result_curl['data']}'"

    def __increase_req_id(self, req_id: int, iteration: int):
        '''
        Increase URL's `_reqid`. Increase the URL's `_reqid` by + `iteration` * google flights increasor constant. 
        So for example if `iteration` is 1, increate `req_id` from 1030783 to 1130783.
        '''
        req_id_increase_constant = 100000 # this constant is defined by google flights itself. I discovered it by testing the google flights calendar picker.
        return req_id + (iteration * req_id_increase_constant)
        

    def __retrieve_oxylabs_responses(result_curls: list):

        # todo: decide if we want to send 1 by 1, or in batch

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