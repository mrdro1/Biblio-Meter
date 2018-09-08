{
"command" : "getFiles",
"papers" : "select * from papers where not ignore and r_file_transaction is null and google_file_url like '%researchgate.net%' and id between 20000 and 45000",

"google_get_files" : true,
"google_cluster_files" : false,
"google_get_files_through_proxy" : ["researchgate.net", "citeseerx.ist.psu.edu"],

"sci_hub_files" : false,
"sci_hub_title_search" : true,
"sci_hub_show_captcha" : false,
"sci_hub_download_captcha" : true,
"sci_hub_timeout" : 15,
"sci_hub_capcha_autosolve" : 10,

"http_contiguous_requests" : 10,
"limit_resp_for_one_code" : 1
 }