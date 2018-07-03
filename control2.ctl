{
"command" : "getPDFs",
"papers" : "select * from papers where not DOI is Null or not google_file_url is Null or not google_cluster_url is Null or not google_url is Null limit 50",
"google_cluster_files" : true,
"sci_hub_files" : true,
"show_sci_hub_captcha" : true,

"http_contiguous_requests" : 20,
"limit_resp_for_one_code" : 1
 }