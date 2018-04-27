from vk_api8 import VKApi

login = "+79081182712"
password = "petia9379992"
client = "6251514" #VK App client id
scope = "friends,messages,groups" #OPTIONAL
version = "5.69" #Api version OPTIONAL

api = VKApi(login, password, client, scope, version)
print(api.token)

id = 155128139
'''
user_friends = api.get_friends_ids(id)
friends_count = user_friends['count']
print(friends_count)
friends_ids = user_friends['items']
print(friends_ids)
'''
print(api.get_posts(id))
