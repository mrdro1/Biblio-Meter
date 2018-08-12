{
"command" : "getReferences",
"papers" : "select * from papers where source_pdf is not null and r_file_transaction is not null limit 4",

"google_max_papers" : 15,

"max_references_per_paper" : 40,

"http_contiguous_requests" : 20,
"limit_resp_for_one_code" : 1
 }