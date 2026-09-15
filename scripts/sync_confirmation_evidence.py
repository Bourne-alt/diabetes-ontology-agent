"""Sync only confirmation provenance; patient facts and diagnostic rules are untouched."""
from pathlib import Path

from rdflib import Graph, Namespace

from dmo.config import load
from dmo.graph.client import GraphDBClient
from dmo.rdf.canonical import collapse, passage_hash


def main():
    root = Path(__file__).resolve().parents[1]
    dmo = Namespace('https://example.org/dmo#')
    passage = Namespace('https://example.org/dmo/id/sourcePassage/')['DIABETES-CONFIRMATION-Q']
    seed = Graph().parse(root / 'ontology/src/dmo-threshold-seed.ttl')
    quote = str(seed.value(passage, dmo.quote))
    assert quote in (root / 'ontology/knowledges/niddk-tests-diagnosis.txt').read_text()
    assert passage_hash(quote) == str(seed.value(passage, dmo.contentHash))
    patch = Graph()
    for triple in seed:
        if triple[0] in (passage, dmo.confirmationCitesPassage) or triple[2] == passage:
            patch.add(triple)
    client = GraphDBClient(load())
    graph_uri = 'urn:dmo:confirmation-evidence'
    existing = Graph().parse(data=client.construct_ttl(
        f'CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{graph_uri}> {{ ?s ?p ?o }} }}'), format='turtle')
    if any(t not in patch for t in existing):
        raise RuntimeError('Target graph contains unrelated triples; refusing replacement')
    client.put_graph(graph_uri, patch.serialize(format='turtle'))
    rows = client.sparql_csv('''PREFIX dmo:<https://example.org/dmo#>
        SELECT ?quote WHERE { ?th dmo:thresholdId "A1C-DIABETES-NONPREG";
        dmo:confirmationCitesPassage ?p . ?p dmo:quote ?quote }''')
    assert any(collapse(r['quote']) == collapse(quote) for r in rows)
    print(f'Verified {len(patch)} confirmation provenance triples in {graph_uri}')


if __name__ == '__main__':
    main()
