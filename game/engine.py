    def to_dict(self):
        return {
            'key': self.key,
            'value': self.value,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            key=data['key'],
            value=data['value'],
        )
