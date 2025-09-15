from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
import pandas as pd
import os
from werkzeug.utils import secure_filename
import json
from bson import ObjectId

app = Flask(__name__)
CORS(app)

# MongoDB connection
client = MongoClient('mongodb+srv://dguruteja:KjynNlNT3LoZtt9v@dgt.cusec.mongodb.net/?retryWrites=true&w=majority&appName=DGT')
db = client['inventory_db']
collection = db['items']
# Invoice collection
invoice_collection = db['invoices']

# Upload configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize with sample data
def init_sample_data():
    if collection.count_documents({}) == 0:
        sample_items = [
            {"itemID": "ABC123", "name": "Rice Bag", "quantity": 5},
            {"itemID": "XYZ789", "name": "Sugar Packet", "quantity": 20},
            {"itemID": "DEF456", "name": "Wheat Flour", "quantity": 15},
            {"itemID": "GHI789", "name": "Cooking Oil", "quantity": 8},
            {"itemID": "JKL012", "name": "Salt Pack", "quantity": 25}
        ]
        collection.insert_many(sample_items)
        print("Sample data initialized")

# Custom JSON encoder for MongoDB ObjectId
class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)

app.json_encoder = JSONEncoder

@app.route('/api/items', methods=['GET'])
def get_items():
    try:
        items = list(collection.find({}, {'_id': 0}))
        return jsonify(items)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file format. Please upload .xlsx or .xls files'}), 400

        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Parse Excel file
        try:
            df = pd.read_excel(filepath)
        except Exception as e:
            os.remove(filepath)
            return jsonify({'error': f'Error reading Excel file: {str(e)}'}), 400

        # Validate required columns
        required_columns = ['itemID', 'name', 'quantity']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            os.remove(filepath)
            return jsonify({'error': f'Missing required columns: {", ".join(missing_columns)}'}), 400

        # Get existing items for comparison
        existing_items = {item['itemID']: item for item in collection.find({}, {'_id': 0})}

        updates = []
        new_items = []
        errors = []

        # Process each row
        from datetime import datetime
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
                # Insert invoice record
                invoice_collection.insert_one({
                    'itemID': item_id,
                    'quantity': quantity,
                    'timestamp': timestamp
                })
                if item_id in existing_items:
                    # Add to existing quantity
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
                    # Create new item
                    collection.insert_one({
                        'itemID': item_id,
                        'name': name,
                        'quantity': quantity
                    })
                    new_items.append(update_data)
            except Exception as e:
                errors.append(f'Row {index + 2}: {str(e)}')

        # Clean up uploaded file
        os.remove(filepath)

        response = {
            'success': True,
            'message': f'Processed {len(updates) + len(new_items)} items successfully',
            'updates': updates,
            'newItems': new_items,
            'errors': errors
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/api/invoices', methods=['GET'])
def get_invoices():
    try:
        invoices = list(invoice_collection.find({}, {'_id': 0}))
        # Format timestamp as ISO string
        for inv in invoices:
            if 'timestamp' in inv:
                inv['timestamp'] = inv['timestamp'].isoformat() + 'Z'
        return jsonify(invoices)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_sample_data()
    app.run(debug=True, host='0.0.0.0', port=5000)