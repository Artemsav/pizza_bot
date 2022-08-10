import json

with open('./data/addresses.json', 'r') as file:
    print(json.load(file))

with open('./data/menu.json', 'r') as file:
    print(json.load(file))
