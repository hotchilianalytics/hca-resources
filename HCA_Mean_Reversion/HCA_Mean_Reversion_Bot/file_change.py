#  https://stackoverflow.com/questions/42594618/python-checking-if-user-changed-file
import hashlib

def hash_file(filename, block_size=2**20):
    md5 = hashlib.md5()
    with open(filename, "rb") as f:
        while True:
            data = f.read(block_size)
            if not data:
                break
            md5.update(data)
    return md5.digest()

if not os.path.exists(out_path) or hash_file(in_path) != hash_file(out_path):
    print("Modified")
else:
    print("Not Modified")

In total you can combine the if statement like this:

if not os.path.exists(out_path) \
        or os.path.getmtime(in_path) > os.path.getmtime(out_path) \
        or hash_file(in_path) != hash_file(out_path):
    print("Modified")
else:
    print("Not Modified")
