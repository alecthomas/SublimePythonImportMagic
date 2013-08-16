import pytest
from index import SymbolIndex


@pytest.fixture(scope='session')
def index(request):
    with open('test_index.json') as fd:
        return SymbolIndex.deserialize(fd)
