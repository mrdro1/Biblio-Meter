{
"command" : "getFiles",
"papers" : "select * from papers where (not DOI is Null or not google_file_url is Null or not google_cluster_id is Null or not google_url is Null) and source_pdf is null limit 1000",
"google_cluster_files" : true,

"sci_hub_files" : true,
"sci_hub_title_search" : true,
"sci_hub_show_captcha" : false,
"sci_hub_download_captcha" : true,
"sci_hub_timeout" : 3,
"sci_hub_capcha_autosolve" : 10,

"commit_iterations" : 1,

"http_contiguous_requests" : 5,
"limit_resp_for_one_code" : 1
 }