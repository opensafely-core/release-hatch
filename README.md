# release-hatch

This provides a small API to authenicate and serve medium-privacy files in TRE
environments, as well as handle requesting a Release and the reviewing and
uploading.

It has no database, all state is derived from the directories and files found
on disk.

It is authenticated via a token signed by the configured `BACKEND_TOKEN`, which
is a shared key between job-server and all services for a backend, and it uses
the same token to authenticate against the job-server to upload files.


Please see the [additional information](DEVELOPERS.md) for developers.
