from openai import OpenAI
import socket

SYSTEM_PROMPT = """
You are a toy http web server. 
You will receive raw http requests to which you will 
respond with well formatted and valid http responses according to the following website prompt.
You must only respond with a http request. Do not include anything else except the request!
The websites should be fun including links to other pages under the same domain.

Try not to produce 404 pages. 404 pages ruin the fun.

Any persistent must be stored in the url parameters. Url parameters are the only
way to persist data across LLM requests.

DO NOT GENERATE IMAGES. IF YOU NEED TO DO ANYTHING IMAGE RELATED USE JAVASCRIPT TO
GENERATE THEM ON THE CLIENT OR USE ASCII ART / CSS. I REPEAT DO NOT GENERATE IMAGES.

IF YOU RECIEVE A REQUEST FOR AN IMAGE JUST 404!! BUT IN GENERAL DO NOT USE IMAGES!!

Please include headers that disable cache. Caching seems to break the client.

Please produce minified code to reduce network usage.
DISPITE THE CODE BEING MINIFIED YOU MUST PRODUCE FULLY WORKING CODE.
THE WEBSITE DEPENDS ON EVERYTHING BEING FULLY FUNCTIONAL.
ENSURE ALL CODE IS MINIFIED: THIS INCLUDES HTML, CSS, AND JAVASCRIPT!.

TRY TO KEEP THE CODE SIZE MINIMAL BUT STILL FULLY FUNTIONAL AND PRETTY.

YOU MUST PRODUCE THE ENTIRE HTTP RESPONSE.
THIS INCLUDES THE CONTENT SECTION. ANY HALF PRODUCED RESPONSE BREAKS
THE SYSTEM.

Website Prompt: A tumbler clone but for ASCII art. Please make it have a fully functional infinite scroll.
For the infinite scroll all requests to '/scroll'' should be return a batched lot ascii art text to be embedded.
The format for the /scroll requests will be a raw ASCII art followed by <br> for batching.
Try to keep requests to a minimum for the infinite scroll.
"""

# A hackernews clone.

# Website Prompt: A tumbler clone but for ASCII art. Please make it have a fully functional infinite scroll.
# For the infinite scroll all requests to '/scroll'' should be return a batched lot ascii art text to be embedded.
# The format for the /scroll requests will be a raw ASCII art followed by <br> for batching.
# Try to keep requests to a minimum for the infinite scroll.

AICLIENT = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="",
)

def read_line(sock):
    """Read a single line ending in \r\n"""
    line = b""
    while not line.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            break
        line += chunk
    return line


def read_headers(sock):
    """Read all headers until \r\n\r\n"""
    data = b""
    while b"\r\n\r\n" not in data:
        data += sock.recv(1)
    header_text = data.decode()
    headers = {}
    lines = header_text.split("\r\n")
    for line in lines[1:]:  # skip status line
        if line == "":
            break
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers, data


def read_fixed_body(sock, length):
    """Read a fixed-length body"""
    body = b""
    while len(body) < length:
        chunk = sock.recv(length - len(body))
        if not chunk:
            raise ConnectionError("Connection closed early")
        body += chunk
    return body


def read_chunked_body(sock):
    """Read a chunked transfer-encoded body"""
    body = b""
    while True:
        size_line = read_line(sock)
        chunk_size = int(size_line.strip(), 16)
        if chunk_size == 0:
            break
        chunk = b""
        while len(chunk) < chunk_size:
            chunk += sock.recv(chunk_size - len(chunk))
        sock.recv(2)  # skip \r\n after chunk
        body += chunk
    sock.recv(2)  # skip final \r\n after last chunk
    return body


def read_until_close(sock):
    """Read until socket closes"""
    body = b""
    while True:
        chunk = sock.recv(1024)
        if not chunk:
            break
        body += chunk
    return body


def handle_client(conn):
    headers, headers_data = read_headers(conn)

    if "content-length" in headers:
        body = conn.recv(int(headers["content-length"]))
    elif headers.get("transfer-encoding", "").lower() == "chunked":
        body = read_chunked(conn)
    else:
        body = b""

    completion = AICLIENT.chat.completions.create(
        extra_body={},
        model="meta-llama/llama-4-maverick:free",
        # model="google/gemini-2.0-flash-001",
        # model="anthropic/claude-3.7-sonnet",
        messages=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (headers_data + body).decode("utf-8")
                    }
                ]
            }
        ]
    )

    print(completion.choices[0].message.content)
    print(completion.choices[0].finish_reason)

    conn.sendall(completion.choices[0].message.content.encode("utf-8"))
    conn.close()


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", 8080))
    server.listen()
    print("Listening on port 8080...")
    while True:
        conn, addr = server.accept()
        handle_client(conn)


start_server()
