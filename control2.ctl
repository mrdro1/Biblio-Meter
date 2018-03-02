{"command":"getPDFs",
 "papers":"select * from papers where not rg_id is Null or not DOI is Null and r_transaction == 21 and id>200 limit 50"
 }