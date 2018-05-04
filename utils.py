import vk_api8
import networkx
from networkx.drawing.nx_agraph import graphviz_layout
import matplotlib.pyplot as plt
from vk_api8 import ErrorApi
from collections import Counter


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
    const = 1
    count_ids = len(ids)
    graph_friends = {}
    graph_likes = {}
    graph_reposts = {}
    graph_comments = {}

    print('Reading info: ')
    for num, id in enumerate(ids):
        print(id)
        if num % const == 0:
            print('Reading {} from {}'.format(num, count_ids))
        try:
            graph_friends[id] = api.get_friends(id)
            print('got friends')
            posts = api.get_posts(id)
            print('got posts')
            graph_likes[id] = Counter(api.get_who_liked_of_posts(id, posts))
            print('got likes')
            graph_reposts[id] = Counter(api.get_who_reposted_of_posts(id, posts))
            print('got reposts')
            graph_comments[id] = Counter(api.get_who_commented_of_posts(id, posts))
            print('got comments')
        except ErrorApi as e:
            print(e)
            pass
    print('Info is readed!')

    print('Creating graph!')
    g = networkx.DiGraph()
    for num, i in enumerate(ids):
        if num % const == 0:
            print('Creating {} from {}'.format(num, count_ids))
        g.add_node(i)
        # friends
        for j in graph_friends[i]:
            if i != j and i in ids and j in ids:
                g.add_edge(i, j, weight=1)
        # reposts
        for j in graph_reposts[i]:
            if i != j and i in ids and j in ids:
                if (i, j) in g.edges:
                    g[i][j]['weight'] += 1
                else:
                    g.add_edge(i, j, weight=1)
        # comments
        for j in graph_comments[i]:
            if i != j and i in ids and j in ids:
                if (i, j) in g.edges:
                    g[i][j]['weight'] += 1
                else:
                    g.add_edge(i, j, weight=1)
        # likes
        for j in graph_likes[i]:
            if i != j and i in ids and j in ids:
                if (i, j) in g.edges:
                    g[i][j]['weight'] += 1
                else:
                    g.add_edge(i, j, weight=1)

    save_graphml(g, fname)
    return g


if __name__ == '__main__':
    login = "+79081182712"
    password = "petia9379992"
    client = "6251514"  # VK App client id
    scope = "friends,messages,groups"  # OPTIONAL
    version = "5.69"  # Api version OPTIONAL

    api = vk_api8.VKApi(login, password, client, scope, version)

    graph_of_friends(api, 155128139, fname='graph.graphml')