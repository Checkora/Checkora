from channels.generic.websocket import AsyncWebsocketConsumer
import json


class StatusConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope["user"]

        await self.accept()

        if user.is_authenticated:
            await self.channel_layer.group_add(
                "online_users",
                self.channel_name
            )

            await self.channel_layer.group_send(
                "online_users",
                {
                    "type": "status_update",
                    "username": user.username,
                    "status": "online"
                }
            )

    async def disconnect(self, close_code):
        user = self.scope["user"]

        if user.is_authenticated:
            await self.channel_layer.group_send(
                "online_users",
                {
                    "type": "status_update",
                    "username": user.username,
                    "status": "offline"
                }
            )

    async def status_update(self, event):
        await self.send(text_data=json.dumps({
            "username": event["username"],
            "status": event["status"]
        }))