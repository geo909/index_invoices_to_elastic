## About 

This lambda function is triggered by an S3 PUT event on the S3 bucket where we put 
our invoices. The event trigger should filter only filenames that begin with 'FH', 
otherwise errors will occur.

For each such filename, the function parses the FH-code, queries the replica DB for
more info, like the booking datetime, calculates the time that elapsed between the
booking date and the invoice creation date and indexes this and a few other 
information in a document in an elasticsearch index 'invoices'.

This will help us identify problems with invoices taking too much time to be 
generated, or not being generated at all.

## Creating the mapping in elastic

We want to use the name *invoices* for our index. Because things may need to 
change on the way, the best practice is to create the index with a different
name, and then create an alias *invoices* to point to that index. Then, if 
we need to change the mapping or something, it is easy to do that on a new 
index and just change the alias *invoices* to point to that new index.

1. Create a mapping

```yaml
PUT /invoices_data
{
    "mappings" : {
      "_doc" : {
        "properties" : {
          "booking_date" : {
            "type" : "date",
            "ignore_malformed" : true,
            "format" : "yyyy-MM-dd'T'HH:mm:ss"
          },
          "sec_elapsed" : {
            "type" : "integer"
          },
          "fh_code" : {
            "type" : "keyword"
          },
          "filename" : {
            "type" : "text",
            "fields" : {
              "keyword" : {
                "type" : "keyword",
                "ignore_above" : 256
              }
            }
          },
          "is_succesful" : {
            "type" : "boolean"
          },
          "has_failed" : {
            "type" : "boolean"
          },
          "is_cancelled":{
            "type":"boolean"
          },
          "last_modified" : {
            "type" : "date",
            "format" : "yyyy-MM-dd'T'HH:mm:ss"
          },
          "full_amount" : {
            "type" : "float"
          }
        }
      }
    }
}
```

2. Create the alias

```yaml
POST /_aliases
{
  "actions": [
      { "add" : {"index" : "invoices_data", "alias": "invoices" } }
    ]
}
```


