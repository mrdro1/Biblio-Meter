{
"command" : "processFiles",
"papers" : "select id from papers where r_file_transaction is not null",

"http_contiguous_requests" : 20,
"limit_resp_for_one_code" : 5
}