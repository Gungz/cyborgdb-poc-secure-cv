from cyborgdb import Client

# Create a client
client = Client(
    base_url='http://localhost:8100', 
    api_key='<your_api_key>'
)

# Provide the same index key and config used when creating the index
key_file_path = "/Users/your-user/.cyborgdb/index_key"  # Must be the same key used originally

with open(key_file_path, "rb") as key_file:
    index_key = key_file.read().strip()

# Connect to the existing index
index = client.load_index(
    index_name="securehr_cv_vecs", 
    index_key=index_key
)

# Delete the index
index.delete_index()