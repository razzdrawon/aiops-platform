# Non-secret dev configuration. Secrets come from TF_VAR_* / CI, never here.
project       = "aiops-platform"
environment   = "dev"
region        = "us-east-1"
desired_count = 1

# Keep the costly pieces off in dev.
enable_messaging = false
enable_cache     = false
