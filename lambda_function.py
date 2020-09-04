from invoice import Invoice
import json

def lambda_handler(event, context):
    invoice = Invoice(event)
    es_response = invoice.send_to_elastic()
    print(es_response.text)
    return {
        'statusCode': 200,
        'doc': invoice.es_doc,
        'es_response': es_response.text
    }

if __name__=='__main__':
    # Invoke locally for testing
    event = json.load(open('events/event.json', 'rb'))
    lambda_handler(event, context=None)
