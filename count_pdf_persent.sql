with t as (
  select 
   source_pdf as pdf
  from 
   papers
   where id <= 200
  )
select 
 (
  select 
   count(*)
  from 
   t
  ) "All",
  (
  select 
   count(*)
  from 
   t
  where pdf is not null 
  ) "good",
 count(*) "PDF's",
 pdf,
 count(*) / (
  (
   select 
    count(*)
   from 
    t
   ) * 1.0) * 100 "Percent"
from 
 t
group by pdf
