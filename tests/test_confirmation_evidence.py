from pathlib import Path

from rdflib import Dataset, Namespace, URIRef

from dmo.rdf.canonical import passage_hash
from dmo.simulate.tree import _threshold_node

ROOT = Path(__file__).resolve().parents[1]
DMO = Namespace('https://example.org/dmo#')


def test_confirmation_is_a_distinct_verbatim_source_not_the_numeric_cutoff():
    ds = Dataset(default_union=True)
    ds.default_graph.parse(ROOT / 'ontology/src/dmo-threshold-seed.ttl')
    ds.default_graph.parse(ROOT / 'ontology/dist_v1/sources.ttl')
    assessment = URIRef('urn:test:assessment')
    ds.default_graph.add((assessment, DMO.appliesThreshold, URIRef('https://example.org/dmo/id/threshold/A1C-DIABETES')))
    node = _threshold_node(ds, str(assessment))
    sources = {s['citationRole']: s for s in node['sources']}
    assert node['confirmationRequired'] is True
    assert sources['threshold']['quote'] == '6.5% or above'
    confirmation = sources['confirmation']
    assert confirmation['quote'] == 'Usually, your doctor will use a second test to confirm you have diabetes.'
    assert confirmation['quote'] in (ROOT / confirmation['localFile']).read_text()
    assert confirmation['sha256'] == passage_hash(confirmation['quote'])
    assert '项目' in confirmation['interpretation']
    assert '不同日期' not in confirmation['quote']


def test_normal_threshold_does_not_acquire_confirmation_citation():
    ds = Dataset(default_union=True)
    ds.default_graph.parse(ROOT / 'ontology/src/dmo-threshold-seed.ttl')
    assessment = URIRef('urn:test:normal')
    ds.default_graph.add((assessment, DMO.appliesThreshold, URIRef('https://example.org/dmo/id/threshold/A1C-NORMAL')))
    node = _threshold_node(ds, str(assessment))
    assert node['confirmationRequired'] is False
    assert all(s['citationRole'] == 'threshold' for s in node['sources'])
