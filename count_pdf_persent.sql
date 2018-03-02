select 
 (
  select 
   count(*)
  from 
   papers
  ) "All",
 count(*) "PDF's",
 count(*) / (
  (
   select 
    count(*)
   from 
    papers
   ) * 1.0) * 100 "Percent"
from 
 papers
where 
 pdf_transaction is not NULL