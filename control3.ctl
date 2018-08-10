{
"command" : "getReferences",
"papers" : "select * from papers where source_pdf is not null and r_file_transaction is not null limit 1000",

"google_max_papers" : 15,

"http_contiguous_requests" : 20,
"limit_resp_for_one_code" : 1
 }