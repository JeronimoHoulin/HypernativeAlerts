from login import header
import requests
endpoint_notification = "https://api.hypernative.xyz/notification-channels"

notification_response = requests.get(endpoint_notification, headers=header).json()
notification_channels = notification_response["data"]["results"]

for channel in notification_channels:
    print(channel['name'])

