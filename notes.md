# Notizen

*Ziemlich zufällige Notizen von Dingen die vorher im Quelltext standen die ich eventuell später noch einmal referenzieren möchte*

```sparksql
 DEFINE get:soft "replace"
    select * where 
    { <https://data.finc.info/resource/organisation/DE-15> 
      <http://purl.org/dc/elements/1.1/title> 
      ?o } 
    LIMIT 26

INSERT DATA
  { 
    GRAPH <https://data.finc.info/masterdata/>
      { 
        <https://data.finc.info/resource/organisation/DE-15> 
        <http://purl.org/dc/elements/1.1/title> 
        "This is a title 4" .
      } 
  }
```
Auslesen und Einfügen von Daten mittels Sparql für meine Testdaten

```python
    data = sparqlQuery(query2, "http://localhost:8890/sparql-auth/", "plaintext", auth="python", pwd="TheresaSechsNull")
    print(data)
    #data = QueryWrapper(query2)
    data = sparqlQuery(query, "http://localhost:8890/sparql")
    print("Retrieved data:\n" + json.dumps(data, sort_keys=True, indent=4))
```

## RDF Library Import JSON LD

```python
rdfdata = rdf_file.read()
graph = Graph().parse(data=rdfdata, format='n3')
print(graph.serialize(format='json-ld', indent=4))
```

## Other Code Snippets

```python
# traverses dict and shows type
for entry in data.items():
    print(type(entry), " ", entry)
# simply display of contents of a list but in bold
    for i in sparsql_queries:
        print(colored(i, "cyan", attrs=["bold"]))
```

