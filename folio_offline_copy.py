import sys

import requests
import json
import logging
import json

import urllib3.exceptions

import folio_secrets  # ! contains private data not for public

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))


folio_header = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "X-Okapi-Tenant": folio_secrets.XOkapiTenant,
    "X-Okapi-Token": folio_secrets.XOkapiToken
}

folio_url = folio_secrets.folio_url
append = "?limit=1000"

endpoints = {
    "library": "/location-units/libraries",
    "campus": "/location-units/campuses",
    "institution": "/location-units/institutions",
    "service": "/service-points",
    "locations": "/locations"
}

sub_points = {
    "library": "loclibs",
    "campus": "loccamps",
    "institution": "locinsts",
    "service": "servicepoints"
}

if __name__ == "__main__":
    dumping_dict = {}

    for key, endpoint in endpoints.items():
        try:
            url = folio_url + endpoint + append
            r = requests.get(url,  headers=folio_header)
            if r.status_code != 200:
                if key == "locations":
                    print(r.text)
                logging.critical(f"Status Code was not 200, {r.status_code} instead")
                exit(1)
            try:
                data = json.loads(r.text)
                dumping_dict.update(data)
                logging.info(f"{key} retrieved ")
            except urllib3.exceptions.NewConnectionError:
                logging.error(f"Connection could be establish")
                continue
            except json.JSONDecodeError as e:
                logging.warning(f"JSON decode Error: {e}")
                continue
        except SystemExit as e:
            exit(e.code)
        except Exception as e:
            logging.critical(f"Surprise error [{e.__class__.__name__}] {e}")
            exit(1)

    try:
        with open("folio_dump.json", "w") as jsoned_file:
            dumping_dict.pop("totalRecords")
            json.dump(dumping_dict, jsoned_file, indent=3)
    except FileNotFoundError:
        logging.warning("Cannot save file")
        print(json.dumps(dumping_dict))
    except Exception as e:
        logging.critical(f"Surprise error [{e.__class__.__name__}] {e}")
