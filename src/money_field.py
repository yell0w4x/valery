import mongoengine.fields

import money

class MoneyField(mongoengine.fields.BaseField):
    """An 64-bit integer field containing 1/1000000th of a dollar
    """

    def __init__(self, min_value=None, max_value=None, **kwargs):
        self.min_value, self.max_value = min_value, max_value
        super(MoneyField, self).__init__(**kwargs)

    def to_python(self, value):
        try:
            if isinstance(value, money.Money):
                return value
            else:
                value = money.Money(value)
        except ValueError:
            pass
        return value


    def to_mongo(self, value):
        """Convert a Python type to a MongoDB-compatible type.
        """
        return int(value)


    def validate(self, value):
        if self.min_value is not None and value < self.min_value:
            self.error('Money value is too small')

        if self.max_value is not None and value > self.max_value:
            self.error('Money value is too big')
