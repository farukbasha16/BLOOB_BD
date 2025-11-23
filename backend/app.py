from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv
from datetime import date, datetime

load_dotenv()

app = Flask(__name__)
CORS(app)

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'blood_bank_db'),
            user=os.getenv('DB_USER', 'blood_bank_user'),
            password=os.getenv('DB_PASSWORD', 'your_password')
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise e

def json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

# --- Auth & User Info ---

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    role = data.get('role')
    user_id = data.get('id')
    
    table_map = {
        'manager': {'table': 'bb_manager', 'pk': 'm_id', 'name': 'm_name'},
        'staff': {'table': 'recording_staff', 'pk': 'reco_id', 'name': 'reco_name'},
        'donor': {'table': 'blood_donor', 'pk': 'bd_id', 'name': 'bd_name'},
        'recipient': {'table': 'recipient', 'pk': 'reci_id', 'name': 'reci_name'},
        'doctor': {'table': 'disease_finder', 'pk': 'dfind_id', 'name': 'dfind_name'},
        'hospital': {'table': 'hospital_info_1', 'pk': 'hosp_id', 'name': 'hosp_name'}
    }
    
    if role not in table_map:
        return jsonify({'message': 'Invalid role'}), 400
    
    config = table_map[role]
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        query = f"SELECT * FROM {config['table']} WHERE {config['pk']} = %s"
        cur.execute(query, (user_id,))
        user = cur.fetchone()
        
        if user:
            return jsonify({
                'id': user[config['pk']],
                'name': user[config['name']],
                'role': role
            })
        return jsonify(None), 404
    finally:
        cur.close()
        conn.close()

@app.route('/api/user_info/<role>/<int:id>', methods=['GET'])
def get_user_info(role, id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    table_map = {
        'manager': 'bb_manager', 'staff': 'recording_staff',
        'donor': 'blood_donor', 'recipient': 'recipient',
        'doctor': 'disease_finder', 'hospital': 'hospital_info_1'
    }
    pk_map = {
        'manager': 'm_id', 'staff': 'reco_id',
        'donor': 'bd_id', 'recipient': 'reci_id',
        'doctor': 'dfind_id', 'hospital': 'hosp_id'
    }

    if role not in table_map:
        return jsonify({'message': 'Invalid role'}), 400

    try:
        query = f"SELECT * FROM {table_map[role]} WHERE {pk_map[role]} = %s"
        cur.execute(query, (id,))
        data = cur.fetchone()
        return jsonify(data) if data else (jsonify({'message': 'User not found'}), 404)
    except Exception as e:
        return jsonify({'message': str(e)}), 500
    finally:
        cur.close()
        conn.close()

# --- Generic CRUD ---

@app.route('/api/<table_name>', methods=['GET'])
def get_all(table_name):
    # Safety check for table names
    allowed_tables = ['city', 'bb_manager', 'recording_staff', 'disease_finder', 
                      'blood_donor', 'recipient', 'blood_specimen', 'hospital_info_1', 'hospital_info_2']
    if table_name not in allowed_tables:
         return jsonify({'message': 'Invalid table'}), 400

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(f"SELECT * FROM {table_name}")
        data = cur.fetchall()
        # Convert date objects to strings
        for row in data:
            for key, value in row.items():
                if isinstance(value, (date, datetime)):
                    row[key] = value.isoformat()
        return jsonify(data)
    except Exception as e:
        return jsonify({'message': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/<table_name>', methods=['POST'])
def add_item(table_name):
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        columns = data.keys()
        values = [data[col] for col in columns]
        insert_query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(values))}) RETURNING *"
        cur.execute(insert_query, values)
        new_item = cur.fetchone()
        conn.commit()
        return jsonify(new_item), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'message': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/<table_name>/<int:id>', methods=['PUT'])
def update_item(table_name, id):
    data = request.json
    pk_map = {
        'blood_donor': 'bd_id', 'recipient': 'reci_id', 'blood_specimen': 'specimen_no',
        'city': 'city_id', 'bb_manager': 'm_id', 'recording_staff': 'reco_id',
        'disease_finder': 'dfind_id', 'hospital_info_1': 'hosp_id'
    }
    pk = pk_map.get(table_name)
    if not pk:
        return jsonify({'message': 'Update not supported for this table via generic API'}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        set_clause = ', '.join([f"{key} = %s" for key in data.keys()])
        values = list(data.values())
        values.append(id)
        update_query = f"UPDATE {table_name} SET {set_clause} WHERE {pk} = %s RETURNING *"
        cur.execute(update_query, values)
        updated_item = cur.fetchone()
        conn.commit()
        return jsonify(updated_item)
    except Exception as e:
        conn.rollback()
        return jsonify({'message': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/<table_name>/<int:id>', methods=['DELETE'])
def delete_item(table_name, id):
    pk_map = {
        'blood_donor': 'bd_id', 'recipient': 'reci_id', 'blood_specimen': 'specimen_no',
        'city': 'city_id', 'bb_manager': 'm_id', 'recording_staff': 'reco_id',
        'disease_finder': 'dfind_id', 'hospital_info_1': 'hosp_id'
    }
    pk = pk_map.get(table_name)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"DELETE FROM {table_name} WHERE {pk} = %s", (id,))
        conn.commit()
        return '', 204
    except Exception as e:
        conn.rollback()
        return jsonify({'message': str(e)}), 500
    finally:
        cur.close()
        conn.close()

# --- Views ---

@app.route('/api/views/<view_name>', methods=['GET'])
def get_view_data(view_name):
    allowed_views = ['matched_pairs', 'pure_samples', 'donor_summary', 'hospital_blood_demand']
    if view_name not in allowed_views:
        return jsonify({'message': 'Invalid view'}), 400
        
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(f"SELECT * FROM {view_name}")
        data = cur.fetchall()
        for row in data:
            for key, value in row.items():
                if isinstance(value, (date, datetime)):
                    row[key] = value.isoformat()
        return jsonify(data)
    except Exception as e:
        return jsonify({'message': str(e)}), 500
    finally:
        cur.close()
        conn.close()

# --- Specialized Operations ---

@app.route('/api/lookup_data', methods=['GET'])
def get_lookup_data():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    data = {}
    try:
        tables = ['city', 'bb_manager', 'recording_staff', 'disease_finder', 'blood_donor']
        for table in tables:
            cur.execute(f"SELECT * FROM {table}")
            data[table if table != 'blood_donor' else 'donors'] = cur.fetchall() # map blood_donor to donors key for frontend
        
        # Add blood groups manually if not in DB table
        data['blood_groups'] = [
            {'value': 'A+', 'label': 'A+'}, {'value': 'A-', 'label': 'A-'},
            {'value': 'B+', 'label': 'B+'}, {'value': 'B-', 'label': 'B-'},
            {'value': 'O+', 'label': 'O+'}, {'value': 'O-', 'label': 'O-'},
            {'value': 'AB+', 'label': 'AB+'}, {'value': 'AB-', 'label': 'AB-'}
        ]
        return jsonify(data)
    finally:
        cur.close()
        conn.close()

@app.route('/api/issue_blood', methods=['POST'])
def issue_blood():
    data = request.json
    specimen_no = data.get('specimen_no')
    recipient_id = data.get('recipient_id')
    quantity = data.get('quantity')

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Call the PostgreSQL stored function
        cur.execute("SELECT issue_blood(%s, %s, %s)", (specimen_no, recipient_id, quantity))
        result_message = cur.fetchone()[0]
        conn.commit()
        return jsonify({'message': result_message})
    except Exception as e:
        conn.rollback()
        # Return the specific error from the database (e.g., "City mismatch")
        return jsonify({'message': str(e).split('\n')[0]}), 400 
    finally:
        cur.close()
        conn.close()

@app.route('/api/hospital_needs/<int:hosp_id>', methods=['GET'])
def get_hospital_needs(hosp_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SELECT * FROM hospital_info_2 WHERE hosp_id = %s", (hosp_id,))
        return jsonify(cur.fetchall())
    finally:
        cur.close()
        conn.close()

@app.route('/api/hospital_needs', methods=['POST'])
def upsert_hospital_need():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = """
            INSERT INTO hospital_info_2 (hosp_id, hosp_needed_bgrp, hosp_needed_qnty)
            VALUES (%s, %s, %s)
            ON CONFLICT (hosp_id, hosp_needed_bgrp) 
            DO UPDATE SET hosp_needed_qnty = EXCLUDED.hosp_needed_qnty
        """
        cur.execute(query, (data['hosp_id'], data['hosp_needed_bgrp'], data['hosp_needed_qnty']))
        conn.commit()
        return jsonify({'message': 'Saved'})
    except Exception as e:
        conn.rollback()
        return jsonify({'message': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/hospital_needs', methods=['DELETE'])
def delete_hospital_need():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = "DELETE FROM hospital_info_2 WHERE hosp_id = %s AND hosp_needed_bgrp = %s"
        cur.execute(query, (data['hosp_id'], data['hosp_needed_bgrp']))
        conn.commit()
        return '', 204
    except Exception as e:
        conn.rollback()
        return jsonify({'message': str(e)}), 500
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)