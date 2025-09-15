from pymongo import MongoClient
import json
import os

def handler(request):
    client = MongoClient(os.environ.get('MONGODB_URI'))
    db = client['inventory_db']
    collection = db['items']
    items = list(collection.find({}, {'_id': 0}))
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(items)
    }
