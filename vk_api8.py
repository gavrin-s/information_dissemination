import time
import random
import re
import itertools
import xml.etree.ElementTree as ET
import datetime
import pprint
from html.parser import HTMLParser
from urllib.parse import urlparse
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import requests
import pickle

user_fields = "id, photo_id, verified, sex, bdate, city, country," \
         " home_town, has_photo, photo_50, photo_100, photo_200_orig," \
         " photo_200, photo_400_orig, photo_max, photo_max_orig, online," \
         " domain, has_mobile, contacts, site, education, universities, schools," \
         " status, last_seen, followers_count, common_count, occupation, nickname," \
         " relatives, relation, personal, connections, exports, wall_comments," \
         " activities, interests, music, movies, tv, books, games, about, quotes," \
         " can_post, can_see_all_posts, can_see_audio, can_write_private_message," \
         " can_send_friend_request, is_favorite, is_hidden_from_feed, timezone," \
         " screen_name, maiden_name, crop_photo, is_friend, friend_status, career," \
         " military, blacklisted, blacklisted_by_me"


class ErrorApi(Exception):
    def __init__(self, message, code=0):
        super().__init__(message)
        self.code = code


class VKApi:
    def __init__(self, login, password, client, scope='',
                 version='5.69', session=requests.Session()):
        self.login = login
        self.password = password
        self.client = client
        self.scope = 'offline' + (',' if scope != '' else '') + scope

        #self.token = self.get_token(login, password, client,
        #                            'offline' + (',' if scope != '' else '') + scope)[0]
        self.token = self.get_token()[0]
        self.version = version
        self.session = session
        self.pp = pprint.PrettyPrinter(depth=3)

    def send_fake_request(self):
        _fake_requests_methods = {
            'database.getCities': 'country_id',
            'database.getChairs': 'faculty_id',
            'groups.getById': 'group_id'
        }
        rand = random.randint(0, len(_fake_requests_methods) - 1)
        method = list(_fake_requests_methods.keys())[rand]
        self.api_request(method, {_fake_requests_methods[method]: str(random.randint(1, 100))})

    def get_region(self, query, city_id):
        json_response = self.api_request('database.getCities', {'country_id': 1, 'q': query})
        if json_response.get('error'):
            print(json_response.get('error'))
            raise Exception("Error while getting region, error_code=".format(
                str(json_response['error']['error_code'])))
        if not json_response['response']['items']:
            return None
        for item in json_response["response"]["items"]:
            if 'region' in item:
                if item["id"] == city_id:
                    return item["region"]
        return json_response['response']['items'][0]["title"]

    def get_group_members(self, group_id, count=1000000):
        max_count = 1000
        method = 'groups.getMembers'
        data = {'group_id': group_id, 'count': max_count}

        if count <= max_count:
            data['count'] = count
            response = self.api_request(method, data)
            return response['response']['items']

        members_id = []
        offset = 0
        while True:
            data['offset'] = offset
            response = self.api_request(method, data)
            print('Got {} members out of {}'.format(offset, count))
            if not response['response']['items'] or offset >= count:
                break
            members_id.extend(response['response']['items'])
            offset += max_count
        return members_id

    def get_token(self):
        class FormParser(HTMLParser):
            def __init__(self):
                HTMLParser.__init__(self)
                self.url = None
                self.params = {}
                self.in_form = False
                self.form_parsed = False
                self.method = "GET"

            def handle_starttag(self, tag, attrs):
                tag = tag.lower()
                if tag == "form":
                    if self.form_parsed:
                        raise RuntimeError("Second form on page")
                    if self.in_form:
                        raise RuntimeError("Already in form")
                    self.in_form = True
                if not self.in_form:
                    return
                attrs = dict((name.lower(), value) for name, value in attrs)
                if tag == "form":
                    self.url = attrs["action"]
                    if "method" in attrs:
                        self.method = attrs["method"].upper()
                elif tag == "input" and "type" in attrs and "name" in attrs:
                    if attrs["type"] in ["hidden", "text", "password"]:
                        self.params[attrs["name"]] = attrs["value"] if "value" in attrs else ""

            def handle_endtag(self, tag):
                tag = tag.lower()
                if tag == "form":
                    if not self.in_form:
                        raise RuntimeError("Unexpected end of <form>")
                    self.in_form = False
                    self.form_parsed = True

        def split_key_value(kv_pair):
            kv = kv_pair.split("=")
            return kv[0], kv[1]

        # Authorization form
        def auth_user(email, password, client_id, scope, opener):
            response = opener.open(
                "https://oauth.vk.com/oauth/authorize?" + \
                "redirect_uri=http://oauth.vk.com/blank.html&response_type=token&" + \
                "client_id=%s&scope=%s&display=wap" % (client_id, ",".join(scope))
            )
            doc = response.read()
            parser = FormParser()
            parser.feed(doc.decode("utf-8"))
            parser.close()
            if not parser.form_parsed or parser.url is None or "pass" not in parser.params or \
                            "email" not in parser.params:
                raise RuntimeError("Something wrong")
            parser.params["email"] = email
            parser.params["pass"] = password
            if parser.method == "POST":
                response = opener.open(parser.url,
                                       urllib.parse.urlencode(parser.params).encode("utf-8"))
            else:
                raise NotImplementedError("Method '%s'" % parser.method)
            return response.read(), response.geturl()

        # Permission request form
        def give_access(doc, opener):
            parser = FormParser()
            parser.feed(doc.decode("utf-8"))
            parser.close()
            if not parser.form_parsed or parser.url is None:
                raise RuntimeError("Something wrong")
            if parser.method == "POST":
                response = opener.open(parser.url,
                                       urllib.parse.urlencode(parser.params).encode("utf-8"))
            else:
                raise NotImplementedError("Method '%s'" % parser.method)
            return response.geturl()

        email = self.login
        password = self.password
        client_id = self.client
        scope = self.scope

        if not isinstance(scope, list):
            scope = [scope]
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
            urllib.request.HTTPRedirectHandler())
        doc, url = auth_user(email, password, client_id, scope, opener)
        if urlparse(url).path != "/blank.html":
            # Need to give access to requested scope
            url = give_access(doc, opener)
        if urlparse(url).path != "/blank.html":
            raise RuntimeError("Expected success here")
        answer = dict(split_key_value(kv_pair) for kv_pair in urlparse(url).fragment.split("&"))
        if "access_token" not in answer or "user_id" not in answer:
            raise RuntimeError("Missing some values in answer")
        return answer["access_token"], answer["user_id"]

    def validate_users(self, user_ids, days_to_del=0, fields='', filter_func=None):
        fields += ',last_seen'
        ret_ids = []
        new_users = self.get_users_data(user_ids, fields)
        for user in new_users:
            if 'deactivated' not in user:
                if 'last_seen' in user:
                    days_since_last_seen = (int(time.time()) - user['last_seen']['time']) // 86400
                    if (days_since_last_seen >= days_to_del):
                        print('Abandoned')
                        continue
                if (filter_func and filter_func(user)):
                    ret_ids.append(user['id'])
                print('Filtered by custom filter')
            print('Banned')
        return ret_ids

    def get_users(self, user_ids):
        max_count = 1000
        method = 'users.get'
        data = {'fields': user_fields}

        offset = 0
        users = []
        while True:
            if not user_ids[offset: offset + max_count]:
                break
            data['user_ids'] = ','.join([str(user_id) for user_id in user_ids[offset: offset + max_count]])
            response = self.api_request(method, data)
            print('Got {} users out of {}'.format(offset + max_count, len(user_ids)))
            users.extend(response['response'])
            offset += max_count
        return users

    def get_users_sequence_generator(self, from_id, to_id, fields):
        _opti = 300
        iterations = (to_id - from_id) // _opti + 1
        for i in range(iterations):
            if i % 15 + 1 == 0:
                self.send_fake_request()
                time.sleep(1)
            print(str(i + 1) + " of " + str(iterations))
            ids = list(range(i * _opti + from_id, (i + 1) * _opti + from_id))
            if to_id - (i * _opti + from_id) < _opti:
                ids = ids[:to_id - (i * _opti + from_id)]
            response = self.api_request('users.get', {
                'user_ids': str(ids).replace("[", "").replace("]", ""),
                'fields': fields})
            if 'error' in response:
                raise Exception('''Error while getting users information,
                 error: {}''' + str(response['error']['error_code']))
            yield response['response']

    def _get_user_groups_by_offset(self, user_id, offset=0):
        json_response = self.api_request('groups.get',
                                         {'user_id': user_id, 'offset': offset, 'count': 1000})
        if 'error' in json_response:
            raise Exception('''Error while getting group members,
             error=''' + str(json_response['error']))
        return json_response['response']

    def get_user_groups(self, user_id):
        user_id = self.user_url_to_id(user_id)
        groups = self._get_user_groups_by_offset(user_id)
        if groups['count'] > 1000:
            iterations = int(groups['count'] / 1000) - int(groups['count'] % 1000 == 0)
            for i in range(iterations):
                groups['items'].extend(self._get_user_groups_by_offset(user_id, 1000 * i)['items'])
        return groups

    def execute(self, code):
        return self.api_request('execute', {'code': code})

    def api_request(self, method, data):
        data['access_token'] = self.token
        data['v'] = self.version
        resp = self.session.post('https://api.vk.com/method/{}'.format(method), data=data)
        time.sleep(0.34)

        if resp.status_code != 200:
            raise ErrorApi('''Network error while executing {} method,
                error code: {}'''.format(method, str(resp.status_code)))

        response = resp.json()
        if 'error' in response:
            pickle.dump(response, open('error.pkl', 'wb'))
            raise ErrorApi('Error: {}'.format(response['error']['error_msg']), response['error']['error_code'])
        return response

    def _get_25_users_subscriptions(self, ids):
        code = '''var ids = ''' + str(ids).replace('\'', '"') + ''';
        var i = 0;
        var ret = {};
        while (i < 25 && i < ids.length)
        {
            ret.push({"id":ids[i], "response":API.users.getSubscriptions({"user_id":ids[i], 
            "extended":0, "count":200})});
            i=i+1;
        }
        return ret;'''
        resp = self.execute(code)
        if 'error' in resp:
            raise Exception('''Error while getting 25_users_groups,
             error: ''' + str(resp['error']))
        users_data = {}
        for element in resp['response']:
            if not element['response'] or not element['response']:
                users_data[element['id']] = None
                continue
            users_data[element['id']] = element['response']
        return users_data

    def _get_25_users_groups(self, ids):
        code = '''var ids = ''' + str(ids).replace('\'', '"') + ''';
        var i = 0;
        var ret = {};
        while (i < 25 && i < ids.length)
        {
            ret.push({"id":ids[i], "response":API.groups.get({"user_id":ids[i], 
            "extended":1, "count":500})});
            i=i+1;
        }
        return ret;'''
        resp = self.execute(code)
        if 'error' in resp:
            raise Exception('''Error while getting 25_users_groups,
             error: ''' + str(resp['error']))
        users_data = {}
        for element in resp['response']:
            if not element['response'] or not element['response']:
                users_data[element['id']] = None
                continue
            user_groups = []
            for group in element['response']['items']:
                if group['type'] == 'group':
                    user_groups.append(group['id'])
            users_data[element['id']] = {'count': len(user_groups), 'items': user_groups}
        return users_data

    def _get_25_users_friends(self, ids):
        code = '''var ids = ''' + str(ids).replace('\'', '"') + ''';
        var i = 0;
        var ret = {};
        while (i < 25 && i < ids.length)
        {
            ret.push({"id":ids[i], "response":API.friends.get({"user_id":ids[i], 
            "count":1000})});
            i=i+1;
        }
        return ret;'''
        resp = self.execute(code)
        if 'error' in resp:
            raise Exception('''Error while getting 25_users_friends,
             error: ''' + str(resp['error']))
        users_data = {}
        for element in resp['response']:
            if not element['response'] or not element['response']:
                users_data[element['id']] = None
                continue
            if element['response']['count'] > 1000:
                users_data[element['id']] = self.get_friends_ids(element['id'])
            else:
                users_data[element['id']] = element['response']
        return users_data

    def _get_25_users_subs(self, ids):
        code = '''var ids = ''' + str(ids).replace('\'', '"') + ''';
        var i = 0;
        var ret = {};
        while (i < 25 && i < ids.length)
        {
            ret.push({"id":ids[i], 
            "response":API.users.getFollowers({"user_id":ids[i], "count":1000})});
            i=i+1;
        }
        return ret;'''
        resp = self.execute(code)
        if 'error' in resp:
            raise Exception('''Error while getting 25_users_subs,
             error: ''' + str(resp['error']))
        users_data = {}
        for element in resp['response']:
            if not element['response']:
                users_data[element['id']] = None
                continue
            if element['response']['count'] > 1000:
                users_data[element['id']] = self.load_all_subs(element['id'])
            else:
                users_data[element['id']] = element['response']
        return users_data

    def _get_25_users_videos(self, ids):
        code = '''var ids = ''' + str(ids).replace('\'', '"') + ''';
        var i = 0;
        var ret = {};
        while (i < 25 && i < ids.length)
        {
            ret.push({"id":ids[i], 
            "response":API.video.get({"owner_id":ids[i], "count":200})});
            i=i+1;
        }
        return ret;'''
        resp = self.execute(code)
        if 'error' in resp:
            raise Exception('''Error while getting 25_users_videos,
             error: ''' + str(resp['error']))
        users_data = {}
        for element in resp['response']:
            if not element['response']:
                users_data[element['id']] = None
                continue
            if element['response']['count'] > 200:
                users_data[element['id']] = self.load_5k_videos(element['id'])
            else:
                users_data[element['id']] = element['response']
        return users_data

    def get_users_extended_info(self, ids, infos):
        methods = {
            "friends": self._get_25_users_friends,
            "subs": self._get_25_users_subs,
            "publics": self._get_25_users_subscriptions,
            "groups": self._get_25_users_groups,
            "videos": self._get_25_users_videos
        }
        methods_to_apply = []
        for info in infos:
            if info in methods:
                methods_to_apply.append((info, methods[info]))
        i = iter(ids)
        ids_to_aggregate = list(itertools.islice(i, 0, 25))
        while ids_to_aggregate:
            yield_data = {}
            for agr_info, method in methods_to_apply:
                new_data = None
                while not new_data:
                    try:
                        new_data = method(ids_to_aggregate)
                    except:
                        print('Something wrong, waiting...')
                        time.sleep(3)
                for user, data in new_data.items():
                    try:
                        yield_data[user][agr_info] = data
                    except:
                        yield_data[user] = {agr_info: data}
            ids_to_aggregate = list(itertools.islice(i, 0, 25))
            yield yield_data

    def get_posts(self, user_id, offset=0, n_count=10000, domain=False, extended=1):
        max_count = 100
        method = 'wall.get'
        data = {'owner_id': user_id, 'domain': domain, 'offset': offset, 'count': max_count,
                'extended': extended}

        if n_count <= max_count:
            data['count'] = n_count
            response = self.api_request(method, data)
            return response['response']['items']

        posts_id = []
        while True:
            data['offset'] = offset
            response = self.api_request(method, data)
            # print('Got {} posts out of {}'.format(offset, n_count))
            if not response['response']['items'] or offset >= n_count:
                break
            posts_id.extend(response['response']['items'])
            offset += max_count
        return posts_id

    def get_who_reposted_of_posts(self, user_id, posts):
        repost_id = []
        method = 'wall.getReposts'
        data = {'owner_id': user_id, 'count': 1000}
        for post in posts:
            if post['reposts']['count'] > 0:
                data['post_id'] = post['id']
                response = self.api_request(method, data)
                repost_id.extend([profile['id'] for profile in response['response']['profiles']])
        return repost_id

    def get_who_liked_of_posts(self, user_id, posts):
        likes_id = []
        method = 'likes.getList'
        data = {'owner_id': user_id, 'count': 1000, 'type': 'post'}
        for post in posts:
            if post['likes']['count'] > 0:
                data['item_id'] = post['id']
                response = self.api_request(method, data)
                likes_id.extend([profile for profile in response['response']['items']])
        return likes_id

    def get_who_commented_of_posts(self, user_id, posts):
        comments_id = []
        method = 'wall.getComments'
        data = {'owner_id': user_id, 'count': 1000, 'extended': 1}
        for post in posts:
            if post['comments']['count'] > 0:
                data['post_id'] = post['id']
                response = self.api_request(method, data)
                comments_id.extend([profile['id'] for profile in response['response']['profiles']])
        return comments_id

    def get_groups_by_id(self, ids):
        iter_size = 500
        groups_data = {}
        for groups_chunk in [ids[pos:pos + iter_size] for pos in range(0, len(ids), iter_size)]:
            resp = self.api_request('groups.getById', \
                                    {'group_ids': str(groups_chunk).replace('[', '').replace(']', '').replace(' ', '')})
            if 'error' in resp:
                raise Exception('Error while getting groups by id')
            group_data = resp['response']
            for group in group_data:
                groups_data[group['id']] = {'name': group['name']}
        return groups_data

    def group_url_to_id(self, group_url):
        group_url = str(group_url)
        parts = group_url.split("/")
        if len(parts) != 1:
            group_url = parts[-1:][0]
        group_id = group_url.strip()
        if re.match(r'(club|public)\d', group_id) != None:
            group_id = re.search(r'\d.*', group_id).group(0)
        return group_id

    def user_url_to_id(self, user_url):
        user_url = str(user_url)
        parts = user_url.split('/')
        if len(parts) != 1:
            user_url = parts[-1:]
        user_id = user_url.strip()
        if re.match(r'id\d*', user_id) is not None:
            user_id = re.search(r'\d.*', user_id).group(0)
        return user_id

    def get_user_id(self, link):
        domain = link.split("/")[-1]
        resp = self.api_request('users.get', {'user_ids': domain})
        if resp.get('error'):
            raise Exception('''Error while getting user_id,
             error: {}'''.format(str(resp['error'])))
        return resp['response'][0]['id']

    def _load_25k_subs(self, user_id, offset=0):
        code = '''var user = ''' + str(user_id) + ''';
        var i = 0;
        var ret = [];
        var count = 25000;
        var data = {};
        while (i*1000 < count &&  i<25)
        {
            data = API.users.getFollowers({"user_id":user,
            "count":1000, "offset":i*1000 + ''' + str(offset) + '''});
            count = data["count"];
            ret.push(data["items"]);
            i=i+1;
        }
        return {"count":count, "items":ret};'''
        resp = self.execute(code)
        if resp['response']['count'] is None:
            return {'count': None, 'items': None}
        if 'error' in resp:
            raise Exception('''Error while getting 25k subs,
             error: ''' + str(resp['error']))
        subs = []
        for array in resp['response']['items']:
            subs.extend(array)
        if 'execute_errors' in resp:
            pass
        return {'count': resp['response']['count'], 'items': subs}

    def load_all_subs(self, user_id):
        user_id = self.user_url_to_id(user_id)
        subs = self._load_25k_subs(user_id)
        count = subs['count']
        if count is None:
            return None
        for i in range(count // 25000 - int(count % 25000 == 0)):
            subs['items'].extend(self._load_25k_subs(user_id, i * 25000))
        return subs

    def load_5k_videos(self, user_id):
        code = '''var user = ''' + str(user_id) + ''';
        var i = 0;
        var ret = [];
        var count = 5000;
        var data = {};
        while (i*200 < count &&  i<25)
        {
            data = API.videos.get({"user_id":user, 
            "count":200, "offset":i*200});
            count = data["count"];
            ret.push(data["items"]);
            i=i+1;
        }
        return {"count":count, "items":ret};'''
        resp = self.execute(code)
        if resp['response']['count'] is None:
            return {'count': None, 'items': None}
        if 'error' in resp:
            raise Exception('''Error while getting 5k subs,
             error: ''' + str(resp['error']))
        subs = []
        for array in resp['response']['items']:
            subs.extend(array)
        if 'execute_errors' in resp:
            pass
        return {'count': resp['response']['count'], 'items': subs}

    def get_friends(self, user_id, count=10000):
        max_count = 1000
        method = 'friends.get'
        data = {'user_id': user_id, 'count': max_count, 'offset': 0}

        if count <= max_count:
            data['count'] = count
            response = self.api_request(method, data)
            return response['response']['items']

        friends_id = []
        offset = 0
        while True:
            data['offset'] = offset
            response = self.api_request(method, data)
            # print('Got {} friends out of {}'.format(offset, count))
            if not response['response']['items'] or offset >= count:
                break
            friends_id.extend(response['response']['items'])
            offset += max_count

        return friends_id

    def _get_10k_messages(self, peer_id, date=time.strftime("%d%m%Y"), _offset=0):
        messages = {}
        filtered = 0
        for i in range(4):
            code = '''var peer_id = ''' + str(peer_id) + ''';
            var i = 0;
            var ret = [];
            var count = 10000;
            var data = [];
            var date = ''' + date + ''';
            while (i*100 + {offset} < count && i<25)
            {{
                data = API.messages.search({{"peer_id":peer_id, 
                "date":date, "count":100, "offset":i*100 + {offset}}});
                count = data["count"];
                ret.push(data["items"]);
                if(data["items"].length == 0){{
                    return {{"count":count, "items":ret}};
                }}
                i=i+1;
            }}
            return {{"count":count, "items":ret}};'''.format(offset=i * 2500 + _offset)
            resp = self.execute(code)
            if 'error' in resp:
                raise Exception('''Error while getting all friends,
                 error: ''' + str(resp['error']))
            for arrray in resp['response']['items']:
                for message in arrray:
                    if 'body' in message and message['body'] != '':
                        messages[message['id']] = {'body': message['body'],
                                                   'date': message['date'],
                                                   'user_id': message['user_id']}
                    else:
                        filtered += 1
            if not resp['response']['items'] or not resp['response']['items'][0]:
                break
            self.send_fake_request()
        return {"count": resp['response']['count'], "filtered": filtered, "items": messages}

    def get_dialog_messages(self, peer_id, count=100, date=time.strftime("%d%m%Y")):
        resp = self.api_request('messages.search', {'peer_id': peer_id, 'date': date, 'count': count})
        if 'error' in resp:
            raise Exception('''Error while getting dialog messages,
             error: {}'''.format(str(resp['error'])))
        return resp['response']

    def get_all_messages_generator(self, peer_id, opti=7500, limit=7500):
        count = 10000
        j = 0
        date = time.strftime("%d%m%Y")
        while j < count and j * opti < limit:
            i = 0
            messages = {}
            while len(messages) < opti and i < count and i < opti:
                new_messages = self._get_10k_messages(peer_id, date, i)
                if not new_messages['items']:
                    j = count
                    break
                count = new_messages['count']
                i += len(new_messages['items']) + new_messages['filtered']
                messages.update(new_messages['items'])
            if not messages:
                yield {}
                break
            time.sleep(1)
            self.send_fake_request()
            date = datetime.datetime.fromtimestamp(messages[min(list(messages.keys()))]['date']).strftime('%d%m%Y')
            j += i
            yield messages

    def search_dialogs(self, unread=False, offset=0):
        resp = self.api_request('messages.getDialogs',
                                {'offset': offset,
                                 'unread': int(unread),
                                 'count': 200})
        if 'error' in resp:
            raise Exception('''Error while getting dialogs,
             error: {}'''.format(str(resp['error'])))
        return resp['response']

    def accept_friend_request(self, id):
        resp = self.api_request('friends.add', {'user_id': id}).json()
        if 'error' in resp:
            raise Exception('''Error while checking for new requests,
             error: {}'''.format(str(resp['error'])))
        return resp

    def check_for_new_friend_requests(self):
        resp = self.api_request('friends.getRequests', {'count': 1000}).json()
        if 'error' in resp:
            raise Exception('''Error while checking for new requests,
             error: {}'''.format(str(resp['error'])))
        return resp['response']['items']

    def accept_all_friend_requests(self):
        for request in self.check_for_new_friend_requests():
            self.accept_friend_request('id')

    def get_unread_messages(self):
        unread_dialogs = self.search_dialogs(unread=True)['items']
        unread_messages = {}
        for dialog in unread_dialogs:
            msg = dialog['message']
            peer_id = (msg['chat_id'] + 2000000000) if ('chat_id' in msg) else msg['user_id']
            unread = self.get_dialog_messages(peer_id, dialog['unread'])
            unread_messages[peer_id] = unread['items']
        return unread_messages

    def join_public(self, group_id):
        resp = self.api_request('groups.join', {'group_id': group_id})
        if 'error' in resp:
            raise Exception('''Error while joining group,
             error: {}'''.format(str(resp['error'])))
        return resp

    # post_id = string 'wall134643_101' or 'wall-1_123453456'
    def repost_post(self, post_id, message=''):
        resp = self.api_request('wall.repost', {'object': post_id, 'message': message})
        if 'error' in resp:
            raise Exception('''Error while reposting,
             error: {}'''.format(str(resp['error'])))
        return resp
