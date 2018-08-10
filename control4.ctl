{
"command" : "getCities",
"papers" : "select * from papers where google_cluster_id is not null limit 1000",

"patents" : false, 
"citations" : false,
"start_paper" : 1,

"google_max_papers" : 1000,

"http_contiguous_requests" : 20,
"limit_resp_for_one_code" : 1
 }
