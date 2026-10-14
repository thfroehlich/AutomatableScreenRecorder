import json
import urllib.request

body = json.dumps(
    {
        "request_id": "example-0001",
        "config": {
            "output_path": "C:\\Recordings\\http.mp4",
            "create_output_directory": True,
        },
    }
).encode()
request = urllib.request.Request(
    "http://127.0.0.1:8765/recordings/start",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
print(json.loads(urllib.request.urlopen(request).read()))
