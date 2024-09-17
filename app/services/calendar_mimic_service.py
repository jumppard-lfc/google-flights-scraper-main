from datetime import datetime
from app.models import AppRun, FlightsSearchConfiguration, Report
from app.services import oxylabs_api_service, calendar_mimic_service, database_service


class CalendarMimicService:
    def __init__(self):
        timestamp = datetime.utcnow()
        
        # initialize services
        self.calendar_mimic_service = calendar_mimic_service.CalendarMimicService() 
        self.oxylabs_api_service = oxylabs_api_service.OxylabsApiService()
        self.db_service = database_service.DbService("sqlite:///./test.db")
        
        # get last app run id
        last_app_run_id = self.get_last_app_id() # returns the last app run id
        self.new_app_run_id = last_app_run_id + 1
        # init new app run
        self.db_service.insert('app_run', {'created_at': timestamp, 'started_at': timestamp, 'status': 'running'})

    def main(self) -> dict:
        ''''
        This is MAIN function, which encapsulates the whole logic of the 
            -   calendar mimic, 
            -   generating cURLs, 
            -   sending then to Oxylabs 
            -   and processing the responses.
        '''

        # get all active flights search configurations
        flights_search_configurations = self.get_active_flights_search_configurations() # returns all active flights search configurations

        # group them by destination and days of stay
        destinations = self.group_flights_by_destination(flights_search_configurations) # groups flights by destination and order them by days of stay

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
        result_curls = self.generate_result_curls(destinations)

        # send oxylabs API requests and retrieve oxylabs responses
        oxylabs_responses = self.retrieve_oxylabs_responses(result_curls)
        
        # save the processed responses to the database
        self.save_processed_responses_to_db(oxylabs_responses, self.new_app_run_id)

        # update the app run status to 'completed'
        self.db_service.update(AppRun, self.new_app_run_id, {'status': 'completed', 'ended_at': datetime.utcnow(), 'inserted_records': len(oxylabs_responses)})    
        
    def get_last_app_id(self):
        return self.db_service.select(AppRun, filters=None, order_by='id', limit=1, desc=True)[0].id

    def get_active_flights_search_configurations(self):
        return self.db_service.select(FlightsSearchConfiguration, {'is_active': True})
    
    def group_flights_by_destination(flights_search_configurations: list):
        # Sort the list by Destination first
        sorted_flights = sorted(flights_search_configurations, key=lambda x: x.destination)

        # Group flights by destination and order them by days of stay
        from itertools import groupby
        destinations = {}
        for destination, flights in groupby(sorted_flights, key=lambda x: x.destination):
            destinations[destination] = sorted(flights, key=lambda x: x.days_of_stay)

        return destinations

    def generate_result_curls(destinations: dict):
        result = []
        for destination, flight_configurations in destinations.items():
            if len(flight_configurations) > 0:
                root_curl = calendar_mimic_service.generate_root_curl(flight.origin, flight.destination, flight.days_of_stay)
                root_curl_obj = calendar_mimic_service.parse_curl(root_curl) # parse the cURL to get the root cURL object with all cURL parts as attributes
            for flight in flight_configurations:
                # Generate cURLs for each flight configuration. For example: all 7 days of stay roundtrips from BTS to JFK, for next 180 days
                curls = calendar_mimic_service.generate_curls(root_curl_obj, flight.origin, flight.destination, flight.days_of_stay)
                result.extend(curls)
        return result
    
    def retrieve_oxylabs_responses(result_curls: list):
        result = []
        for curl in result_curls:
            # send cURLs to Oxylabs
            response = oxylabs_api_service.send_curl(curl)
            # process the response
            processed_response = oxylabs_api_service.process_response(response)
            result.append({'curl_request': curl, 'curl_response': processed_response, 'success': processed_response['success']})
        return result
    
    def save_processed_responses_to_db(self, oxylabs_responses: list, new_app_run_id: int):
        for response in oxylabs_responses:
            data = {
                'new_app_run_id': new_app_run_id, 
                'destination': response['curl_response']['destination'], 
                'days_of_stay': response['curl_response']['days_of_stay'], 
                'best_price': response['curl_response']['best_price']
            }
            # save the processed response to the database
            self.db_service.insert(Report, data)