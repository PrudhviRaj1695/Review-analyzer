# app/utils.py
import uuid


def generate_product_id():
    x = uuid.uuid4()
    y = str(x)
    return y


# TODO: add validation
