# Schema of the graph (from void.ttl)

PREFIX ppo: <https://ul.edu.lb/kr/ont/ppo#>  PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>  PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

## Rules
- Status classes are subclasses: every ppo:ClosedContract is also a ppo:Contract, and so on (listed below).
- OCDS code "terminated" = ppo:ClosedContract: the contract ran and closed. It does NOT mean failed.
- There is no Supplier, Buyer or Tenderer class in the data. Use the links: ?award ppo:awardedTo ?org,
  ?process ppo:hasBuyer ?org, ?tender ppo:hasTenderer ?org.
- Names: rdfs:label on organisations, skos:prefLabel on procurement methods. Amounts come with
  ppo:currency (mostly "PYG"). Data IRIs: https://ul.edu.lb/kr/id/py/{process|tender|award|contract|org}/...

## Classes (how many things)
ppo:ProcurementProcess (63,178 things)
ppo:Tender (63,178 things)
ppo:Award (52,512 things)
ppo:ActiveAward (52,276 things)  (a kind of ppo:Award)
ppo:Contract (50,090 things)
ppo:CompleteTender (41,823 things)  (a kind of ppo:Tender)
ppo:Organization (34,660 things)
ppo:ActiveContract (28,469 things)  (a kind of ppo:Contract)
ppo:ClosedContract (21,584 things)  (a kind of ppo:Contract)
ppo:PlanningTender (17,042 things)  (a kind of ppo:Tender)
ppo:CancelledTender (2,179 things)  (a kind of ppo:Tender)
ppo:UnsuccessfulTender (2,128 things)  (a kind of ppo:Tender)
ppo:CancelledAward (222 things)  (a kind of ppo:Award)
ppo:CancelledContract (37 things)  (a kind of ppo:Contract)
ppo:ProcurementMethod (27 things)

## Properties (from class, to class or datatype)
ppo:Award ppo:amount xsd:decimal
ppo:Award ppo:awardDate xsd:dateTime
ppo:Award ppo:awardedTo ppo:Organization
ppo:Award ppo:currency xsd:string
ppo:Award ppo:statusCode xsd:string
ppo:Contract ppo:amount xsd:decimal
ppo:Contract ppo:basedOnAward ppo:Award
ppo:Contract ppo:currency xsd:string
ppo:Contract ppo:dateSigned xsd:dateTime
ppo:Contract ppo:periodEnd xsd:dateTime
ppo:Contract ppo:periodStart xsd:dateTime
ppo:Contract ppo:statusCode xsd:string
ppo:Organization ppo:country xsd:string
ppo:Organization ppo:identifier xsd:string
ppo:Organization ppo:identifierScheme xsd:string
ppo:Organization rdfs:label xsd:string
ppo:ProcurementMethod skos:prefLabel xsd:string
ppo:ProcurementProcess ppo:bundleYear xsd:integer
ppo:ProcurementProcess ppo:hasAward ppo:Award
ppo:ProcurementProcess ppo:hasBuyer ppo:Organization
ppo:ProcurementProcess ppo:hasContract ppo:Contract
ppo:ProcurementProcess ppo:hasTender ppo:Tender
ppo:ProcurementProcess ppo:ocid xsd:string
ppo:Tender ppo:category xsd:string
ppo:Tender ppo:currency xsd:string
ppo:Tender ppo:datePublished xsd:dateTime
ppo:Tender ppo:estimatedAmount xsd:decimal
ppo:Tender ppo:hasTenderer ppo:Organization
ppo:Tender ppo:numberOfTenderers xsd:integer
ppo:Tender ppo:resultsInAward ppo:Award
ppo:Tender ppo:statusCode xsd:string
ppo:Tender ppo:tenderPeriodEnd xsd:dateTime
ppo:Tender ppo:tenderPeriodStart xsd:dateTime
ppo:Tender ppo:title xsd:string
ppo:Tender ppo:usesMethod ppo:ProcurementMethod
