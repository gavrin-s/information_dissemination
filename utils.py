import vk_api8
import networkx
from networkx.drawing.nx_agraph import graphviz_layout
import matplotlib.pyplot as plt
from collections import Counter
import pickle
import sys
import numpy as np


def save_graphml(g, fname):
    if fname is not None:
        networkx.write_graphml(g, fname)


def graph_of_friends(api, user_id, fname=None):
    graph = {}
    friends_ids = api.get_friends(user_id)

    for friend in friends_ids:
        print('Processing id: {}'.format(friend))
        try:
            graph[friend] = api.get_friends(friend)
        except Exception as error:
            print(error)

    g = networkx.Graph()
    for i in graph:
        g.add_node(i)
        for j in graph[i]:
            if i != j and i in friends_ids and j in friends_ids:
                g.add_edge(i, j)

    save_graphml(g, fname)

    pos = graphviz_layout(g, prog='neato')
    networkx.draw(g, pos, node_size=30, with_labels=False, width=0.2)
    plt.show()


def weighted_graph(api, ids, fname=None):
    count_ids = len(ids)
    graph_friends = {}
    graph_likes = {}
    graph_reposts = {}
    graph_comments = {}

    print('Reading info: ')
    for num, id in enumerate(ids):
        print('Reading {} from {}.'.format(num, count_ids-1))
        print('-----{}-----'.format(id))
        try:
            graph_friends[id] = api.get_friends(id)
            print('     got friends')
            posts = api.get_posts(id)
            print('     got posts')
            graph_likes[id] = Counter(api.get_who_liked_of_posts(id, posts))
            print('     got likes')
            graph_reposts[id] = Counter(api.get_who_reposted_of_posts(id, posts))
            print('     got reposts')
            graph_comments[id] = Counter(api.get_who_commented_of_posts(id, posts))
            print('     got comments')
        except vk_api8.ErrorApi as e:
            print(e)
            break
    print('Info is red!')

    data = {'ids': ids, 'count_ids': count_ids, 'graph_likes': graph_likes,
            'graph_friends': graph_friends, 'graph_reposts': graph_reposts,
            'graph_comments': graph_comments}

    with open('data.pickle', 'wb') as f:
        pickle.dump(data, f)
    '''
    print('Creating graph!')
    g = networkx.DiGraph()
    for num, i in enumerate(ids):
        if num % const == 0:
            print('Creating {} from {}'.format(num, count_ids - 1))
        g.add_node(i)
        # friends
        for j in graph_friends.get(i, []):
            if i != j and i in ids and j in ids:
                g.add_edge(i, j, weight=1)
        # reposts
        for j in graph_reposts.get(i, []):
            if i != j and i in ids and j in ids:
                if (i, j) in g.edges:
                    g[i][j]['weight'] += 1
                else:
                    g.add_edge(i, j, weight=1)
        # comments
        for j in graph_comments.get(i, []):
            if i != j and i in ids and j in ids:
                if (i, j) in g.edges:
                    g[i][j]['weight'] += 1
                else:
                    g.add_edge(i, j, weight=1)
        # likes
        for j in graph_likes.get(i, []):
            if i != j and i in ids and j in ids:
                if (i, j) in g.edges:
                    g[i][j]['weight'] += 1
                else:
                    g.add_edge(i, j, weight=1)

    save_graphml(g, fname)
    '''
    return data


if __name__ == '__main__':
    login = "+79081182712"
    password = "petia9379992"
    client = "6251514"  # VK App client id
    scope = "friends,messages,groups"  # OPTIONAL
    version = "5.69"  # Api version OPTIONAL

    begin, end = sys.argv[1], sys.argv[2]
    ids = np.load('TSU.npy')

    api = vk_api8.VKApi(login, password, client, scope, version)

    data = weighted_graph(api, ids[begin: end]) # что нужно вернуть
