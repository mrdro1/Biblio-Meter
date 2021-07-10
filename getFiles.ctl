{
"command" : "getFiles",
"papers" : "select * from papers where source_pdf is null",

"google_get_files" : true,
"google_cluster_files" : true,
"google_get_files_through_proxy" : ["researchgate.net", "citeseerx.ist.psu.edu"],

"sci_hub_files" : true,
"sci_hub_title_search" : true,
"sci_hub_show_captcha" : false,
"sci_hub_download_captcha" : false,
"sci_hub_timeout" : 3,
"sci_hub_capcha_autosolve" : 10,

"http_contiguous_requests" : 10,
"limit_resp_for_one_code" : 1,
"disconnection_timeout" : 300

}
