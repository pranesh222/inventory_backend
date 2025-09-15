from pymongo import MongoClient
import json
import os
import pandas as pd
from datetime import datetime
from base64 import b64decode

def handler(request):
    # Only allow POST
    if request['method'] != 'POST':
        return {
            'statusCode': 405,
            'body': 'Method Not Allowed'
        }
    try:
        # Expect JSON body with base64-encoded file
        body = json.loads(request['body'])
        file_content = b64decode(body['file'])
        df = pd.read_excel(file_content)
    except Exception as e:
        return {'statusCode': 400, 'body': f'Error reading Excel file: {str(e)}'}

    client = MongoClient(os.environ.get('MONGODB_URI'))
    db = client['inventory_db']
    collection = db['items']
    invoice_collection = db['invoices']

    required_columns = ['itemID', 'name', 'quantity']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        return {'statusCode': 400, 'body': f'Missing required columns: {", ".join(missing_columns)}'}

    existing_items = {item['itemID']: item for item in collection.find({}, {'_id': 0})}
    updates = []
    new_items = []
    errors = []

    for index, row in df.iterrows():
        try:
            item_id = str(row['itemID']).strip()
            name = str(row['name']).strip()
            quantity = int(row['quantity'])
            timestamp = datetime.utcnow()
            if not item_id or not name or quantity < 0:
                errors.append(f'Row {index + 2}: Invalid data')
                continue
            update_data = {
                'itemID': item_id,
                'name': name,
                'oldQuantity': existing_items.get(item_id, {}).get('quantity', 0),
                'newQuantity': quantity,
                'isNew': item_id not in existing_items
            }
            invoice_collection.insert_one({
                'itemID': item_id,
                'quantity': quantity,
                'timestamp': timestamp
            })
            if item_id in existing_items:
                old_quantity = existing_items[item_id]['quantity']
                new_quantity = old_quantity + quantity
                collection.update_one(
                    {'itemID': item_id},
                    {'$set': {'name': name, 'quantity': new_quantity}}
                )
                update_data['oldQuantity'] = old_quantity
                update_data['newQuantity'] = new_quantity
                updates.append(update_data)
            else:
                collection.insert_one({
                    'itemID': item_id,
                    'name': name,
                    'quantity': quantity
                })
                new_items.append(update_data)
        except Exception as e:
            errors.append(f'Row {index + 2}: {str(e)}')

    response = {
        'success': True,
        'message': f'Processed {len(updates) + len(new_items)} items successfully',
        'updates': updates,
        'newItems': new_items,
        'errors': errors
    }
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(response)
    }
