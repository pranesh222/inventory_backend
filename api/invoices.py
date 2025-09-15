from pymongo import MongoClient
import json
import os

def handler(request):
    client = MongoClient(os.environ.get('MONGODB_URI'))
    db = client['inventory_db']
    invoice_collection = db['invoices']
    invoices = list(invoice_collection.find({}, {'_id': 0}))
    for inv in invoices:
        if 'timestamp' in inv:
            inv['timestamp'] = inv['timestamp'].isoformat() + 'Z'
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(invoices)
    }
