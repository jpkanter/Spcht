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