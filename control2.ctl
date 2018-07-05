{
"command" : "getPDFs",
"papers" : "select * from papers where (not DOI is Null or not google_file_url is Null or not google_cluster_id is Null or not google_url is Null) and source_pdf is Null limit 1000",
"google_cluster_files" : false,
"sci_hub_files" : true,
"show_sci_hub_captcha" : false,

"http_contiguous_requests" : 5,
"limit_resp_for_one_code" : 1
 }