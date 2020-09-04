from requests_aws4auth import AWS4Auth
from urllib.parse import unquote_plus
import dateutil.parser
import hashlib
import json
import os
import pymysql
import pymysql.cursors
import requests

if os.path.isfile('.env'): 
    # in development; use environmental variables from .env file
    from dotenv import load_dotenv
    load_dotenv(verbose=True)

ES_URL = os.environ['ES_URL']
ES_INDEX = 'invoices_data'
ES_TYPE = '_doc'

def get_hash(string, num_digits = 8):
    md5 = hashlib.md5()
    md5.update(string.encode('utf-8'))
    return md5.hexdigest()[:num_digits] 

class Booking:
    def __init__(self, fh_code):
        self.order_id = fh_code
        self.created_at = None
        self.full_amount = None
        self.has_failed = None
        self.is_cancelled = None
        self.is_succesful = None
        self.response_statuses = None

    def get_db_info(self):
        print('- Getting info from replica for', self.order_id, end = ': ')
        columns = [
            'orderId', 
            'createdAt',
            'fullAmount',
            'hasFailed',
            'isCancelled',
            'isSuccesful',
            'responseStatuses'
        ]

        query = f'''SELECT {', '.join(columns)}
                    FROM reservations_bookings 
                    WHERE orderId = "{self.order_id}";'''

        print('connecting to db.. ', end = '')
        conn = pymysql.connect(
                    os.environ['FH_DB_REPLICA_HOST'], 
                    port = 3306,
                    user = os.environ['FH_DB_REPLICA_USER'], 
                    password = os.environ['FH_DB_REPLICA_PSWD'],
                    db = os.environ['FH_DB_REPLICA_DB']
               )

        with conn.cursor() as cursor:
            print('querying.. ', end = '')
            cursor.execute(query)
            response = cursor.fetchone()
            cursor.close()
            print('done.')
        conn.close()

        r = dict(zip(columns, response))
        self.created_at = r['createdAt']
        self.full_amount = r['fullAmount']
        self.has_failed = r['hasFailed']
        self.is_cancelled = r['isCancelled']
        self.is_succesful = r['isSuccesful']
        self.response_statuses = r['responseStatuses']
        return True

class Invoice:
    ''' To be initiated with an S3 PUT event 
        Important: add a condition in the event to filter for files that 
        start with 'FH', otherwise there will be errors
    '''
    def __init__(self, event):
        # Attributes to get from S3 event
        self.filename = None
        self.last_modified = None
        self.fh_code = None
        
        # Attributes that require db info
        self.booking = None
        self.elapsed_sec = None
        self.elapsed_min = None
        self.es_doc = None

        # Populate fields
        print('Populating fields')
        self._parse_s3_event(event)
        self._get_booking_db_info()
        self._create_elastic_doc()

    def _parse_s3_event(self, event):
        print('- Parsing S3 PUT event..', end = ' ')
        event_time = event['Records'][0]['eventTime']
        self.last_modified = event_time.split('.')[0]
        source_key = event['Records'][0]['s3']['object']['key']
        filename = os.path.basename(source_key)
        # unquote_plus: replace greek %xx escape characters with normal text
        self.filename = unquote_plus(filename)
        # Assumes we filter filenames with FH prefix in the S3 put event:
        self.fh_code = self.filename[:12]
        print('done')
        return True

    def _get_booking_db_info(self):
        self.booking = Booking(self.fh_code)
        self.booking.get_db_info()
        elapsed = dateutil.parser.parse(self.last_modified)-self.booking.created_at
        self.elapsed_sec = round(elapsed.total_seconds())
        self.elapsed_min = int(self.elapsed_sec/60)

    def _create_elastic_doc(self):
        es_doc = {
            'filename': self.filename,
            'last_modified': self.last_modified,
            'fh_code': self.fh_code,
            'booking_date': self.booking.created_at.strftime('%Y-%m-%dT%H:%m:%S'),
            'is_succesful': bool(self.booking.is_succesful),
            'has_failed': bool(self.booking.has_failed),
            'is_cancelled': bool(self.booking.is_cancelled),
            'full_amount': self.booking.full_amount,
            'elapsed_sec': self.elapsed_sec,
            'elapsed_min': self.elapsed_min
         }
        self.es_doc = json.dumps(es_doc, indent = 4)

    def send_to_elastic(self, use_local_es=False):
        es_id = get_hash(self.filename)
        url = f'{ES_URL}/{ES_INDEX}/{ES_TYPE}/{es_id}'
        auth = AWS4Auth(
            os.environ['GEORGE_AWS_ACCESS_KEY_ID'],
            os.environ['GEORGE_AWS_SECRET_ACCESS_KEY'],
            'eu-central-1',
            'es' # The aws service abbreviation, for elasticsearch here
        )
        response = requests.post(
                        url, 
                        data = self.es_doc,
                        headers = {'Content-Type':'application/json'},
                        auth = auth
                   )
        return response
