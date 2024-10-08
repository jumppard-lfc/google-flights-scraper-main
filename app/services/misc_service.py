import re

def parse_curl(curl: str):
        
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