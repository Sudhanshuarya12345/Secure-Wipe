from supabase import create_client, Client
# import os
# url: str = os.environ.get("SUPABASE_URL")
# key: str = os.environ.get("SUPABASE_KEY")

# Replace with your own project values
url: str = "https://gvmsvgldvkgzfbzycsuw.supabase.co"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd2bXN2Z2xkdmtnemZienljc3V3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc3MDA3OTMsImV4cCI6MjA3MzI3Njc5M30.uq6FfXmhigFUuKlbBKy5kl8gyOfpncUXYzoT3mM0eDk"

supabase: Client = create_client(url, key)

def verify_product_key(email, product_key):
    response = supabase.table("users").select("*").eq("product_key", product_key).eq("email", email).execute()
    return response.data

























# data1 = {
#     "name": "John Doe",
#     "email": "john.doe@example.com",
#     "password_hash": "hashed_password_123",
#     "product_key": "PROD-KEY-987654"
# }
# data2 = {
#     "name": "Alice Smith",
#     "email": "alice.smith@example.com",
#     "password_hash": "hash_abc123",
#     "product_key": "PROD-KEY-1111"
#   }
# data3 = {
#     "name": "Bob Johnson",
#     "email": "bob.johnson@example.com",
#     "password_hash": "hash_def456",
#     "product_key": "PROD-KEY-2222"
#   }
# data4 = {
#     "name": "Charlie Brown",
#     "email": "charlie.brown@example.com",
#     "password_hash": "hash_ghi789",
#     "product_key": "PROD-KEY-3333"
#   }

# response1 = supabase.table("users").insert(data1).execute()
# response2 = supabase.table("users").insert(data2).execute()
# response3 = supabase.table("users").insert(data3).execute()
# response4 = supabase.table("users").insert(data4).execute()
