import cyborgdb_core as cyborgdb
import base64

# Example setup
index_location = cyborgdb.DBConfig(location='postgres', connection_string="postgresql://securehr:securehr_password@localhost:5432/securehr")
config_location = cyborgdb.DBConfig(location='postgres', connection_string="postgresql://securehr:securehr_password@localhost:5432/securehr")
items_location = cyborgdb.DBConfig(location='postgres', connection_string="postgresql://securehr:securehr_password@localhost:5432/securehr")
client = cyborgdb.Client(
    api_key="<your_api_key>",
    index_location=index_location,
    config_location=config_location,
    items_location=items_location
)

# Example index configuration
index_config = cyborgdb.IndexIVFFlat()
index_name = "test_index"

# Load the encryption key
with open("index_key.txt", "rb") as key_file:
    key_b64 = key_file.read().strip()
    index_key = base64.b64decode(key_b64)

# Use the encryption key
client.create_index(
    index_name=index_name,
    index_key=index_key,
    index_config=index_config
)