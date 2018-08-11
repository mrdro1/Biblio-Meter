{
"command" : "processGROBIDpapers",
"papers" : "select * from grobid_papers where google_cluster_id is not null",

"http_contiguous_requests" : 20,
"limit_resp_for_one_code" : 1
}
