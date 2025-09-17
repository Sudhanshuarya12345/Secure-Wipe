# from supabase import create_client, Client
# from dotenv import load_dotenv
# import os

# load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# url: str = os.getenv("SUPABASE_URL")
# key: str = os.getenv("SUPABASE_KEY")

# if not url or not key:
#     raise ValueError("SUPABASE_URL or SUPABASE_KEY is missing. Check your .env file.")


# try:
#     supabase: Client = create_client(url, key)
# except Exception as e:
#     print(f"Error creating Supabase client: {e}")

# def verify_product_key(product_key):
#     response = supabase.table("users").select("*").execute()
#     print(response.data)
    
product_key = "PROD-KEY-3333"


print("Verifying product key:", "")

import requests
import json

# Insert your product key here
product_key = "Secure-SXLU0IRC86K-wipe"

# Build URL
url = f"https://secure-wipe-2gyy.onrender.com/api/key/key-verify/{product_key}"

try:
    # Send GET request
    response = requests.get(url, timeout=10)

    print("Status code:", response.status_code)


except requests.exceptions.RequestException as e:
    print("Error while making request:", e)

















# [{'id': 'fc85792a-2857-42ae-85b8-a3cb5c134c41', 'name': 'testdev1', 'email': 'test@test.com', 'password_hash': '$2b$10$C8OorTcyYaMyz4Z4ungitO0kmv4V.bHXwy54xpjltRW5ovPze1Yei', 'product_key': 'Secure-SXLU0IRC86K-wipe', 'created_at': '2025-09-12T18:59:39.554655'}, 
#  {'id': 'aad129ed-8d31-444e-a4fb-ae1eac51d76f', 'name': 'John Doe', 'email': 'john.doe@example.com', 'password_hash': 'hashed_password_123', 'product_key': 'PROD-KEY-987654', 'created_at': '2025-09-15T21:04:54.973673'}, 
#  {'id': '2f214331-3d67-4cbc-b324-0283b61bcf9f', 'name': 'Alice Smith', 'email': 'alice.smith@example.com', 'password_hash': 'hash_abc123', 'product_key': 'PROD-KEY-1111', 'created_at': '2025-09-15T21:04:55.223449'}, 
#  {'id': '4c33c1f1-5180-4b24-a04c-94efb7e7c1b5', 'name': 'Bob Johnson', 'email': 'bob.johnson@example.com', 'password_hash': 'hash_def456', 'product_key': 'PROD-KEY-2222', 'created_at': '2025-09-15T21:04:55.360788'},
#  {'id': '3efe9bea-0715-4de0-93d2-22662cc0ff47', 'name': 'Charlie Brown', 'email': 'charlie.brown@example.com', 'password_hash': 'hash_ghi789', 'product_key': 'PROD-KEY-3333', 'created_at': '2025-09-15T21:04:55.499962'}, 
#  {'id': 'aa133dbd-ef46-4818-a40a-7555ac9e5e56', 'name': 'founder', 'email': 'founder@test.com', 'password_hash': '$2b$10$EpeTqgcIhPGPoUAKkl7aXOUC19sAhJSbyCf6QsFa.lfnC1wJJoqK2', 'product_key': 'Secure-SFLGEBBEM5P-wipe', 'created_at': '2025-09-17T13:34:09.504851'}, 
#  {'id': '54d978a9-caf2-4e80-8e73-9014eb2542c0', 'name': 'Niko Bellic', 'email': 'niko@test.com', 'password_hash': '$2b$10$mCak23GGObn57gtr/0kb2e3HrON2GDN/rnCa3weAvVa1oPJXQ5zii', 'product_key': 'Secure-815ZXCRMZAJ-wipe', 'created_at': '2025-09-17T13:37:00.633811'}]