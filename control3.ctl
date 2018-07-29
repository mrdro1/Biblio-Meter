{
"command" : "getReferences",
"papers" : "select * from papers where source_pdf is not null limit 1000",

"google_max_papers" : 10,

"commit_iterations" : 1,
"http_contiguous_requests" : 20,
"limit_resp_for_one_code" : 1
 }