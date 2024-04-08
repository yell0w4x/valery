from money import Money


class TokenPriceCalculator:
    def __init__(self, token_price):
        self.__token_price = Money(token_price)


    def calc(self, tokens_num):
        return self.__token_price * tokens_num


class TransriptionPriceCalculator:
    def __init__(self, minute_price):
        self.__minute_price = Money(minute_price)

    
    def calc(self, duration_seconds):
        duration_min = duration_seconds / 60
        return self.__minute_price * duration_min


class AccountingProvider:
    def __init__(self, config):
        self.__calcs = calcs = dict()
        for model, options in config['models'].items():
            price = options['price']
            calcs[model] = TokenPriceCalculator(price)

    
    def __getitem__(self, model_name):
        return self.__calcs[mode]


    def __contains__(self, model_name):
        return model_name in self.__calcs
