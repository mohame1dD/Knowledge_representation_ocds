# PPO ontology changelog

## 1.1.0
- Added `ppo:candidateSameAs` for entity resolution (step 5). Notified suppliers carry a hashed,
  per-process id and no identifier, so the only evidence is the name. `owl:sameAs` would merge
  the individuals and copy every fact across; a wrong guess would then contaminate the graph.
  The weaker property records the link without merging.

## 1.0.1
- **Fix found by the reasoner.** `ppo:bundleYear` had range `xsd:gYear`. HermiT refused to load the
  ontology: `xsd:gYear` is not in the OWL 2 datatype map, so an OWL 2 DL reasoner cannot use it.
  Changed the range (and the data) to `xsd:integer`. Lesson: a valid RDF datatype is not
  automatically a valid OWL 2 datatype.

## 1.0.0
- First version: 6 core classes, 3 defined role classes, 17 status classes, 9 object and
  18 datatype properties. Aligned to TBFY OCDS and ePO 5.2.0.
