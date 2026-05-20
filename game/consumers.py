import json

from channels.generic.websocket import AsyncWebsocketConsumer


class GameConsumer(AsyncWebsocketConsumer):

    async def connect(self):

        self.room_code = self.scope['url_route']['kwargs']['room_code']

        self.room_group_name = f'room_{self.room_code}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        await self.send(text_data=json.dumps({
            'message': 'Connected to room',
            'room_code': self.room_code
        }))

    async def disconnect(self, close_code):

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):

        data = json.loads(text_data)

        # Start game event
        if data.get('start_game'):

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_start',
                    'start_game': True
                }
            )

            return

        # Move synchronization
        move = data.get('move')

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_move',
                'move': move
            }
        )

    async def game_move(self, event):

        move = event['move']

        await self.send(text_data=json.dumps({
            'move': move
        }))

    async def game_start(self, event):

        await self.send(text_data=json.dumps({
            'start_game': event['start_game']
        }))
        