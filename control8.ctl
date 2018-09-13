{
"command" : "getDOIbyTitle",
"papers" : "select * from papers where r_file_transaction is null and doi <> '' and length(title) > 35",
"crossref_max_papers": 50,

"http_contiguous_requests" : 20,
"limit_resp_for_one_code" : 1
}
