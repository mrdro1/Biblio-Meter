{
"command" : "getDOIbyTitle",
"papers" : "select * from papers where doi is null and length(title) > 20",
"crossref_max_papers": 5000000,

"http_contiguous_requests" : 20,
"limit_resp_for_one_code" : 1
}
