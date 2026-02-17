import math
from rag import ServerKnowledgeRAG


def test_rag_query_basic():
    rag = ServerKnowledgeRAG()
    # populate a small artificial index
    rag.documents = [
        {
            'id': 'd1',
            'source': 'test',
            'text': 'cpu memory disk high usage',
            'tf': {'cpu': 1, 'memory': 1, 'disk': 1, 'high': 1, 'usage': 1},
            'norm': math.sqrt(5),
            'excerpt': 'cpu memory disk high usage'
        },
        {
            'id': 'd2',
            'source': 'test',
            'text': 'database connection timeout error',
            'tf': {'database': 1, 'connection': 1, 'timeout': 1, 'error': 1},
            'norm': math.sqrt(4),
            'excerpt': 'database connection timeout error'
        }
    ]
    rag.indexed = True

    res = rag.query('high cpu usage', top_k=2)
    assert res, 'Expected non-empty results'
    assert res[0]['id'] == 'd1'
    # query for unrelated term
    res2 = rag.query('timeout database', top_k=1)
    assert res2 and res2[0]['id'] == 'd2'