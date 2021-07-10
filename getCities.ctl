{
"command" : "getCities",
"papers" : "select * from papers where google_cluster_id is not null limit 1",

"patents" : false, 
"citations" : false,
"start_paper" : 203,

"google_max_papers" : 1000,

"commit_iterations" : 1,
"http_contiguous_requests" : 20,
"limit_resp_for_one_code" : 1
 }
