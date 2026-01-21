
path = 'backend/main.py'
with open(path, 'rb') as f:
    valid_data = f.read().replace(b'\x00', b'')

with open(path, 'wb') as f:
    f.write(valid_data)

print(f"Cleaned {path}")
