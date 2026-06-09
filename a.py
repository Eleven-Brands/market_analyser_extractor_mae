import requests

url = "https://api.clickup.com/api/v3/workspaces/31030239/chat/channels/xjyyz-50913/messages"
headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "Authorization": "pk_82190071_Z5JOWZO2BU5942T8DA7F4X4L53WZPWML"
}

# Testa cada bandeira individualmente
tests = [
    ("Teste US Flag 1", "[US]")
]

for title, emoji in tests:
    payload = {
        "type": "message",
        "content_format": "text/md",
        "content": f"{title}: {emoji}"
    }
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"{title}: Status {response.status_code}")