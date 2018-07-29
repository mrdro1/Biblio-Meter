{
"command" : "getCities",
"papers" : "select * from papers where google_cluster_id is not null",

"patents" : false, 
"citations" : false,
"start_paper" : 1,

"google_max_papers" : 1,

"commit_iterations" : 1,
"http_contiguous_requests" : 20,
"limit_resp_for_one_code" : 1
 }
