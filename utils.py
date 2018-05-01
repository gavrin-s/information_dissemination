import vk_api8
import networkx
from networkx.drawing.nx_agraph import graphviz_layout


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

    if fname is not None:
        networkx.write_graphml(g, fname)

    pos = graphviz_layout(g, prog='neato')
    networkx.draw(g, pos, node_size=30, with_labels=False, width=0.2)


if __name__ == '__main__':
    login = "+79081182712"
    password = "petia9379992"
    client = "6251514"  # VK App client id
    scope = "friends,messages,groups"  # OPTIONAL
    version = "5.69"  # Api version OPTIONAL

    api = vk_api8.VKApi(login, password, client, scope, version)

    graph_of_friends(api, 155128139, fname='graph.graphml')